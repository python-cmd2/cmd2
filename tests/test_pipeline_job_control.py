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


@pytest.mark.parametrize("finish", ["q", "\x03", "process_sigint", "group_sigint", "exit_sigint", "read_input", "shell_input"])
@pytest.mark.parametrize("stop_job", [False, True])
@pytest.mark.parametrize("shell_child", [False, True])
def test_pipeline_stops_with_cmd2_and_returns_terminal(tmp_path, finish, stop_job, shell_child) -> None:
    import fcntl
    import pty
    import struct
    import termios

    shell = shutil.which("bash")
    if shell is None:
        pytest.skip("requires an interactive bash shell")
    pager = tmp_path / "pager.py"
    pager_pid = tmp_path / "pager.pid"
    interrupts = tmp_path / "interrupts"
    pager.write_text(
        "import os, pathlib, signal, sys, termios, tty\n"
        f"pathlib.Path({str(pager_pid)!r}).write_text(str(os.getpid()))\n"
        f"if {finish != 'exit_sigint'!r}: sys.stdin.read()\n"
        # Like less, use an inherited terminal descriptor for keyboard input when
        # stdin is a pipe. This also works in the broken detached-session case.
        "with os.fdopen(os.dup(sys.stderr.fileno()), 'rb', buffering=0) as terminal:\n"
        "    saved = termios.tcgetattr(terminal)\n"
        # os.write rather than print: a signal handler that uses buffered stdout raises
        # "reentrant call inside <_io.BufferedWriter>" when the signal lands mid-write,
        # which happens when the job is stopped while still reporting readiness.
        "    def resume(*args):\n"
        "        tty.setcbreak(terminal)\n"
        "        os.write(1, b'PAGER_RESUMED\\n')\n"
        "    signal.signal(signal.SIGCONT, resume)\n"
        "    def interrupt(*args):\n"
        f"        fd = os.open({str(interrupts)!r}, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)\n"
        "        os.write(fd, b'I')\n"
        "        os.close(fd)\n"
        "        os.write(1, b'PAGER_INTERRUPT\\n')\n"
        f"    signal.signal(signal.SIGINT, {'signal.SIG_DFL' if finish == 'exit_sigint' else 'interrupt'})\n"
        "    try:\n"
        "        tty.setcbreak(terminal)\n"
        "        os.write(1, b'PAGER_READY\\n')\n"
        "        while os.read(terminal.fileno(), 1) != b'q':\n"
        "            pass\n"
        "    finally:\n"
        "        termios.tcsetattr(terminal, termios.TCSANOW, saved)\n",
        encoding="utf-8",
    )
    application = tmp_path / "application.py"
    application.write_text(
        "from cmd2 import Cmd, ToolbarMode\n"
        "import os, time\n"
        "class App(Cmd):\n"
        "    def do_busy(self, statement):\n"
        "        os.write(2, b'BUSY_READY\\n')\n"
        "        time.sleep(30)\n"
        "    def do_ask(self, statement):\n"
        "        self.poutput(self.read_input('INPUT> '))\n"
        "app = App(bottom_toolbar_mode=ToolbarMode.RESERVED)\n"
        "app.prompt = 'TEST> '\n"
        "app.main_session.bottom_toolbar = 'STATUS'\n"
        "app.cmdloop()\n",
        encoding="utf-8",
    )
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    if finish == "exit_sigint":
        settings = termios.tcgetattr(slave)
        settings[3] |= termios.TOSTOP
        termios.tcsetattr(slave, termios.TCSANOW, settings)
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

    def stopped(*pids: int) -> bool:
        """Whether every process is stopped, not merely deprived of the terminal.

        The shell takes the terminal back as soon as its child stops, but a grandchild still
        blocked in a one-byte terminal read is woken by the stop signal and, if a keystroke
        has arrived by then, consumes it before it stops. Typing has to wait for the whole job.
        """
        listing = subprocess.run(
            ["ps", "-o", "stat=", "-p", ",".join(map(str, pids))], capture_output=True, text=True, check=False
        )
        states = listing.stdout.split()
        return len(states) == len(pids) and all(state.startswith("T") for state in states)

    job_group = None
    pipeline_group = None
    try:
        wait_until(lambda: "OUTER> " in transcript)
        send(f"{shlex.quote(sys.executable)} {shlex.quote(str(application))}\n")
        wait_until(lambda: screen.display[-1].startswith("STATUS"))
        job_group = os.tcgetpgrp(master)
        command = "busy" if finish == "exit_sigint" else "help -v"
        if finish == "read_input":
            command = "ask"
        elif finish == "shell_input":
            input_script = tmp_path / "input.py"
            input_script.write_text("import os\nos.write(2, b'INPUT> ')\ninput()\n", encoding="utf-8")
            command = f"shell {shlex.quote(sys.executable)} {shlex.quote(str(input_script))}"
        pipe_command = f"{shlex.quote(sys.executable)} {shlex.quote(str(pager))}"
        if shell_child:
            # Keep a shell between Popen and the terminal reader, rather than allowing
            # the final command to replace it with exec.
            pipe_command = f"{shlex.quote(shell)} -c {shlex.quote(pipe_command + '; :')}"
        send(f"{command} | {pipe_command}\n")
        if finish in ("read_input", "shell_input"):
            wait_until(lambda: any(line.startswith("INPUT>") for line in screen.display))
            send("answer\n")
        # Whole lines only: a traceback naming the marker must not satisfy the wait.
        wait_until(lambda: "PAGER_READY\r\n" in transcript)
        if finish == "exit_sigint":
            wait_until(lambda: "BUSY_READY\r\n" in transcript)
        pager_process = int(pager_pid.read_text())
        pipeline_group = os.tcgetpgrp(master)
        for rows in (12, 24) if stop_job else ():
            send("\x1a")
            wait_until(lambda: os.tcgetpgrp(master) == process.pid)
            wait_until(lambda: stopped(job_group, pager_process))
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
            wait_until(lambda start=start: "PAGER_RESUMED\r\n" in transcript[start:])
            assert os.tcgetpgrp(master) == pipeline_group
        if finish == "exit_sigint":
            send("\x03")
        elif finish in ("\x03", "process_sigint", "group_sigint"):
            for expected_count in (1, 2):
                if finish == "process_sigint":
                    # Signal cmd2 alone, as with `kill -INT <cmd2-pid>`.
                    os.kill(job_group, signal.SIGINT)
                elif finish == "group_sigint":
                    os.killpg(pipeline_group, signal.SIGINT)
                else:
                    send(finish)
                wait_until(lambda count=expected_count: transcript.count("PAGER_INTERRUPT\r\n") >= count)
                # Keep the handler alive long enough to observe a duplicate delivery,
                # then also check that a second real interrupt is not suppressed.
                deadline = time.monotonic() + 0.1
                wait_until(lambda deadline=deadline: time.monotonic() >= deadline)
                assert interrupts.read_text() == "I" * expected_count
        if finish != "exit_sigint":
            send("q")
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
        if pipeline_group is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(pipeline_group, signal.SIGKILL)
        process.kill()
        process.wait(timeout=5)
        os.close(master)
