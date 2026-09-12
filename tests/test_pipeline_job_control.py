"""Exercise pipeline job control through a real controlling terminal and outer shell."""

import codecs
import contextlib
import os
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pyte
import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX job control")


@pytest.mark.parametrize("finish", ["q", "\x03"])
def test_pipeline_stops_with_cmd2_and_returns_terminal(tmp_path, finish) -> None:
    import fcntl
    import pty
    import struct
    import termios

    shell = shutil.which("bash")
    if shell is None:
        pytest.skip("requires an interactive bash shell")
    pager = tmp_path / "pager.py"
    pager_pid = tmp_path / "pager.pid"
    pager.write_text(
        "import os, pathlib, signal, sys, termios, tty\n"
        f"pathlib.Path({str(pager_pid)!r}).write_text(str(os.getpid()))\n"
        "sys.stdin.read()\n"
        # Like less, use an inherited terminal descriptor for keyboard input when
        # stdin is a pipe. This also works in the broken detached-session case.
        "with os.fdopen(os.dup(sys.stderr.fileno()), 'rb', buffering=0) as terminal:\n"
        "    saved = termios.tcgetattr(terminal)\n"
        "    def resume(*args):\n"
        "        tty.setcbreak(terminal)\n"
        "        print('PAGER_RESUMED', flush=True)\n"
        "    signal.signal(signal.SIGCONT, resume)\n"
        "    try:\n"
        "        tty.setcbreak(terminal)\n"
        "        print('PAGER_READY', flush=True)\n"
        "        while os.read(terminal.fileno(), 1) != b'q':\n"
        "            pass\n"
        "    finally:\n"
        "        termios.tcsetattr(terminal, termios.TCSANOW, saved)\n",
        encoding="utf-8",
    )
    application = tmp_path / "application.py"
    application.write_text(
        "from cmd2 import Cmd, ToolbarMode\n"
        "app = Cmd(bottom_toolbar_mode=ToolbarMode.RESERVED)\n"
        "app.prompt = 'TEST> '\n"
        "app.main_session.bottom_toolbar = 'STATUS'\n"
        "app.cmdloop()\n",
        encoding="utf-8",
    )
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    # Establish a controlling terminal in a fresh interpreter, avoiding preexec_fn
    # (unsafe when pytest or its plugins have started threads).
    bootstrap = (
        "import os, fcntl, termios; os.setsid(); "
        "fcntl.ioctl(0, termios.TIOCSCTTY, 0); "
        "os.execv(os.environ['TEST_SHELL'], ['bash', '--noprofile', '--norc', '-i'])"
    )
    env = dict(os.environ, TERM="xterm-256color", PS1="OUTER> ", TEST_SHELL=shell)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    process = subprocess.Popen([sys.executable, "-c", bootstrap], stdin=slave, stdout=slave, stderr=slave, env=env)
    os.close(slave)
    screen = pyte.Screen(80, 24)
    screen.write_process_input = lambda data: os.write(master, data.encode())
    stream = pyte.Stream(screen)
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    transcript = ""

    def send(data):
        os.write(master, data.encode())

    def wait_until(predicate):
        nonlocal transcript
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.05)[0]:
                data = decoder.decode(os.read(master, 65536))
                transcript += data
                stream.feed(data)
            if predicate():
                return
        pytest.fail(f"terminal condition timed out:\n{transcript}")

    job_group = None
    try:
        wait_until(lambda: "OUTER> " in transcript)
        send(f"{shlex.quote(sys.executable)} {shlex.quote(str(application))}\n")
        wait_until(lambda: screen.display[-1].startswith("STATUS"))
        job_group = os.tcgetpgrp(master)
        send(f"help -v | {shlex.quote(sys.executable)} {shlex.quote(str(pager))}\n")
        wait_until(lambda: "PAGER_READY" in transcript)
        for rows in (12, 24):
            send("\x1a")
            wait_until(lambda: os.tcgetpgrp(master) == process.pid)
            start = len(transcript)
            # A child left running can steal these keystrokes from the shell.
            send("printf 'SHELL_%s\\n' OWNS_INPUT\n")
            wait_until(lambda start=start: "SHELL_OWNS_INPUT" in transcript[start:])
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, 80, 0, 0))
            screen.resize(lines=rows, columns=80)
            start = len(transcript)
            send("stty size\n")
            # Bash 5.1+ turns bracketed paste off with "\x1b[?2004l\r" before running the
            # command, so the reply may follow a bare "\r" rather than "\r\n".
            wait_until(lambda start=start, rows=rows: re.search(rf"[\r\n]{rows} 80\r\n", transcript[start:]) is not None)
            start = len(transcript)
            send("fg\n")
            wait_until(lambda start=start: "PAGER_RESUMED" in transcript[start:])
            assert os.tcgetpgrp(master) == job_group
        send(finish)
        wait_until(lambda: screen.display[-1].startswith("STATUS") and "TEST>" in "\n".join(screen.display))
        start = len(transcript)
        send("help quit\n")
        wait_until(lambda: "Exit this application" in transcript[start:])
        send("quit\n")
        wait_until(lambda: os.tcgetpgrp(master) == process.pid)
    finally:
        # Kill only this test's job, including stopped descendants, on assertion failure.
        if pager_pid.exists():
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(pager_pid.read_text()), signal.SIGKILL)
        if job_group is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(job_group, signal.SIGKILL)
        process.kill()
        process.wait(timeout=5)
        os.close(master)
