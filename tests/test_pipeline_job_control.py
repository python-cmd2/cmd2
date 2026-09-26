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


def describe_processes(root: int, master: int) -> str:
    """Report the terminal's foreground group and every descendant of root, for a timeout.

    A silent transcript says only that nothing happened. Process states (T for stopped)
    and wait channels say which process was waiting for whom.
    """
    try:
        foreground: object = os.tcgetpgrp(master)
    except OSError as error:
        foreground = error
    try:
        listing = subprocess.run(
            ["ps", "-e", "-o", "pid,ppid,pgid,stat,wchan,command"], capture_output=True, text=True, check=False
        )
    except OSError as error:
        return f"foreground process group: {foreground}\nno process listing: {error}"
    rows = listing.stdout.splitlines()
    parents = {}
    for row in rows[1:]:
        fields = row.split(maxsplit=2)
        if len(fields) >= 2 and fields[0].isdigit() and fields[1].isdigit():
            parents[int(fields[0])] = int(fields[1])
    family = {root}
    while True:
        grown = family | {pid for pid, parent in parents.items() if parent in family}
        if grown == family:
            break
        family = grown
    described = [row for row in rows[1:] if row.split(maxsplit=1)[0].isdigit() and int(row.split(maxsplit=1)[0]) in family]
    return "\n".join([f"foreground process group: {foreground}", rows[0] if rows else "", *described])


@pytest.mark.parametrize(
    ("finish", "stop_job", "shell_child", "launcher", "producer", "relay"),
    [
        pytest.param("interrupts", True, False, "direct", "command", "main", id="direct-signals-and-job-control"),
        pytest.param("interrupts", True, True, "sh", "command", "main", id="wrapper-signals-and-job-control"),
        pytest.param("exit_sigint", False, False, "direct", "command", "main", id="interrupt-busy-producer"),
        pytest.param("exit_sigint", True, True, "uv", "command", "worker", id="uv-stop-and-interrupt-busy-producer"),
        pytest.param("exit_sigint", False, False, "direct", "shell", "main", id="interrupt-busy-shell-producer"),
        pytest.param("exit_sigint", True, True, "sh", "shell", "worker", id="wrapper-stop-and-interrupt-busy-shell-producer"),
        pytest.param("read_input", False, False, "direct", "command", "main", id="nested-prompt"),
        pytest.param("shell_input", False, True, "direct", "command", "main", id="shell-input"),
        pytest.param("direct_input", False, False, "sh", "command", "main", id="wrapper-direct-input"),
        pytest.param("direct_input", False, False, "exec", "command", "main", id="direct-input-in-orphaned-session"),
        pytest.param("interrupts", False, False, "exec", "command", "main", id="orphaned-job-control"),
    ],
)
def test_pipeline_stops_with_cmd2_and_returns_terminal(
    tmp_path, finish, stop_job, shell_child, launcher, producer, relay
) -> None:
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
        "import errno, os, pathlib, signal, sys, termios, tty\n"
        f"if {launcher == 'exec'!r}: assert signal.getsignal(signal.SIGTSTP) == signal.SIG_IGN\n"
        # Interactive bash leaves TTIN/TTOU ignored when exec replaces it. Give
        # the simulated pager normal terminal-access stops: EOF can arrive before
        # cmd2 lends it the terminal, and an ignored TTIN makes that read fail with
        # EIO instead of waiting for the handoff. Preserve the inherited TSTP policy.
        "signal.signal(signal.SIGTTIN, signal.SIG_DFL)\n"
        "signal.signal(signal.SIGTTOU, signal.SIG_DFL)\n"
        f"pathlib.Path({str(pager_pid)!r}).write_text(str(os.getpid()))\n"
        f"if {finish != 'exit_sigint'!r}: sys.stdin.read()\n"
        # Like less, use an inherited terminal descriptor for keyboard input when
        # stdin is a pipe. This also works in the broken detached-session case.
        "with os.fdopen(os.dup(sys.stderr.fileno()), 'rb', buffering=0) as terminal:\n"
        "    saved = termios.tcgetattr(terminal)\n"
        "    def setcbreak():\n"
        "        while True:\n"
        "            try:\n"
        "                tty.setcbreak(terminal)\n"
        "                return\n"
        "            except termios.error as error:\n"
        "                if error.args[0] != errno.EINTR: raise\n"
        # os.write rather than print: a signal handler that uses buffered stdout raises
        # "reentrant call inside <_io.BufferedWriter>" when the signal lands mid-write,
        # which happens when the job is stopped while still reporting readiness.
        "    def resume(*args):\n"
        "        setcbreak()\n"
        "        os.write(1, b'PAGER_RESUMED\\n')\n"
        "    signal.signal(signal.SIGCONT, resume)\n"
        "    def interrupt(*args):\n"
        f"        fd = os.open({str(interrupts)!r}, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)\n"
        "        os.write(fd, b'I')\n"
        "        os.close(fd)\n"
        "        os.write(1, b'PAGER_INTERRUPT\\n')\n"
        f"    signal.signal(signal.SIGINT, {'signal.SIG_DFL' if finish == 'exit_sigint' else 'interrupt'})\n"
        "    try:\n"
        "        setcbreak()\n"
        "        os.write(1, b'PAGER_READY\\n')\n"
        "        while True:\n"
        "            key = os.read(terminal.fileno(), 1)\n"
        "            if key == b'q': break\n"
        "            if key == b'p': os.write(1, b'PAGER_ALIVE\\n')\n"
        "    finally:\n"
        "        termios.tcsetattr(terminal, termios.TCSANOW, saved)\n",
        encoding="utf-8",
    )
    application = tmp_path / "application.py"
    application_pid = tmp_path / "application.pid"
    interrupt_request = tmp_path / "interrupt.request"
    last_result = tmp_path / "last_result"
    application.write_text(
        "from cmd2 import Cmd\n"
        "from cmd2.plugin import CommandFinalizationData\n"
        "import getpass, os, pathlib, signal, threading, time\n"
        "signal.signal(signal.SIGTSTP, signal.SIG_DFL)\n"
        f"if {relay == 'worker'!r}:\n"
        # The kernel may hand a signal to a thread other than the one it was aimed at.
        # Deliver the job-control relay to the watcher that sends it, so the main thread,
        # blocked in a pipe write or a wait, only learns of it if it returns on its own.
        "    _pthread_kill = signal.pthread_kill\n"
        "    signal.pthread_kill = lambda thread_id, signum: _pthread_kill(threading.get_ident(), signum)\n"
        f"pathlib.Path({str(application_pid)!r}).write_text(str(os.getpid()))\n"
        "class App(Cmd):\n"
        "    def do_busy(self, statement):\n"
        "        os.write(2, b'BUSY_READY\\n')\n"
        "        self.stdout.write('x' * 262144)\n"
        "        self.stdout.flush()\n"
        "        time.sleep(30)\n"
        "    def do_ask(self, statement):\n"
        "        self.poutput(self.read_input('INPUT> '))\n"
        "    def do_direct(self, statement):\n"
        "        self.stdout.buffer.write(b'x' * 262144)\n"
        "        self.stdout.flush()\n"
        "        assert self.select('first second', 'SELECT> ') == 'first'\n"
        "        assert input('PLAIN> ') == 'answer'\n"
        "        assert getpass.getpass('SECRET> ') == 'secret'\n"
        "        os.write(2, b'RAW> ')\n"
        "        assert os.read(0, 7) == b'direct\\n'\n"
        "        self.poutput('INPUT_COMPLETE')\n"
        "    def record_result(self, data: CommandFinalizationData) -> CommandFinalizationData:\n"
        f"        pathlib.Path({str(last_result)!r}).write_text(repr(self.last_result))\n"
        "        return data\n"
        "app = App()\n"
        "app.register_cmdfinalization_hook(app.record_result)\n"
        "app.prompt = 'TEST> '\n"
        "app.debug = True\n"
        f"if {finish == 'interrupts'!r}:\n"
        "    def interrupt_from_worker():\n"
        f"        request = pathlib.Path({str(interrupt_request)!r})\n"
        "        for _ in range(2):\n"
        "            while not request.exists():\n"
        "                time.sleep(0.01)\n"
        "            request.unlink()\n"
        # A process-directed signal can be delivered to any unblocked thread.
        # Force that case so an indefinite main-thread wait cannot pass by luck.
        "            signal.pthread_kill(threading.get_ident(), signal.SIGINT)\n"
        "    threading.Thread(target=interrupt_from_worker, daemon=True).start()\n"
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
    # Exercise the same pipeline shell on developer machines and in CI. An
    # inherited zsh can exec the pager directly, hiding bash's stop/wait behavior.
    env = dict(os.environ, TERM="xterm-256color", PS1="OUTER> ", TEST_SHELL=shell, SHELL=shell)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    process = subprocess.Popen([sys.executable, "-c", bootstrap], stdin=slave, stdout=slave, stderr=slave, env=env)
    os.close(slave)
    screen = pyte.Screen(80, 24)
    screen.write_process_input = lambda data: os.write(master, data.encode())
    stream = pyte.Stream(screen)
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    transcript = ""
    # Each resize with the size read back straight after it, to tell a resize that never
    # took effect from one undone later.
    resizes: list[str] = []

    def terminal_size() -> tuple[int, int]:
        rows, columns, _, _ = struct.unpack("HHHH", fcntl.ioctl(master, termios.TIOCGWINSZ, b"\0" * 8))
        return rows, columns

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
        pytest.fail(
            f"terminal condition timed out:\n{transcript}\n{describe_processes(process.pid, master)}\n"
            f"resizes: {resizes}\nterminal size at timeout: {terminal_size()}"
        )

    def stopped(*pids: int) -> bool:
        """Whether every process is stopped, not merely deprived of the terminal.

        The shell takes the terminal back as soon as its child stops, but a grandchild still
        blocked in a one-byte terminal read is woken by the stop signal and, if a keystroke
        has arrived by then, consumes it before it stops. Typing has to wait for the whole job.
        """
        pids = tuple(set(pids))
        listing = subprocess.run(
            ["ps", "-o", "stat=", "-p", ",".join(map(str, pids))], capture_output=True, text=True, check=False
        )
        states = listing.stdout.split()
        return len(states) == len(pids) and all(state.startswith("T") for state in states)

    job_group = None
    pipeline_group = None
    try:
        wait_until(lambda: "OUTER> " in transcript)
        launch = f"{shlex.quote(sys.executable)} {shlex.quote(str(application))}"
        if launcher == "sh":
            launch = f"{shlex.quote(shell)} -c {shlex.quote(launch + '; :')}"
        elif launcher == "uv":
            uv = shutil.which("uv")
            if uv is None:
                pytest.skip("requires uv")
            launch = f"{shlex.quote(uv)} run --no-project -- {launch}"
        elif launcher == "exec":
            launch = "exec " + launch
        send(launch + "\n")
        wait_until(lambda: "TEST>" in "\n".join(screen.display))
        # A foreground-group query is an observation, not the child's identity.
        # It can change during startup and handoffs. Never use an unverified
        # foreground query as a kill()/killpg() destination.
        app_pid = int(application_pid.read_text())
        job_group = os.getpgid(app_pid)
        assert job_group > 1
        wait_until(lambda: os.tcgetpgrp(master) == job_group)
        command = "busy" if finish == "exit_sigint" else "help -v"
        if producer == "shell":
            # A shell command writes into the pipe itself rather than through cmd2's
            # stdout, so cmd2 cannot lend the terminal write by write. Like seq or git
            # log, this producer dies from SIGINT rather than handling it.
            busy_script = tmp_path / "busy.py"
            busy_script.write_text(
                "import os, signal, sys, time\n"
                "signal.signal(signal.SIGINT, signal.SIG_DFL)\n"
                "os.write(2, b'BUSY_READY\\n')\n"
                "sys.stdout.write('x' * 262144)\n"
                "sys.stdout.flush()\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            command = f"shell {shlex.quote(sys.executable)} {shlex.quote(str(busy_script))}"
        if finish == "read_input":
            command = "ask"
        elif finish == "direct_input":
            command = "direct"
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
        if finish == "direct_input":
            for prompt, response in (("SELECT>", "\r"), ("PLAIN>", "answer\n"), ("SECRET>", "secret\n"), ("RAW>", "direct\n")):
                wait_until(lambda prompt=prompt: prompt in "\n".join(screen.display))
                assert os.tcgetpgrp(master) == job_group
                send(response)
        if finish in ("read_input", "shell_input"):
            wait_until(lambda: any(line.startswith("INPUT>") for line in screen.display))
            send("answer\n")
        # Whole lines only: a traceback naming the marker must not satisfy the wait.
        wait_until(lambda: "PAGER_READY\r\n" in transcript)
        if finish == "exit_sigint":
            wait_until(lambda: "BUSY_READY\r\n" in transcript)
        pager_process = int(pager_pid.read_text())
        pipeline_group = os.getpgid(pager_process)
        assert pipeline_group > 1
        assert pipeline_group != job_group
        # Readiness output can precede the foreground handoff. Send terminal
        # signals and keystrokes only once the pipeline can receive them.
        wait_until(lambda: os.tcgetpgrp(master) == pipeline_group)
        if launcher == "exec":
            # There is no outer shell to run fg: Ctrl-Z must leave the pager
            # usable. Require a fresh read acknowledgement, not a SIGCONT.
            start = len(transcript)
            send("\x1ap")
            wait_until(lambda: "PAGER_ALIVE\r\n" in transcript[start:])
            assert os.tcgetpgrp(master) == pipeline_group
        for rows in (12, 24) if stop_job else ():
            send("\x1a")
            wait_until(lambda: os.tcgetpgrp(master) == process.pid)
            wait_until(lambda: stopped(job_group, app_pid, pager_process))
            start = len(transcript)
            # A child left running can steal these keystrokes from the shell.
            send("printf 'SHELL_%s\\n' OWNS_INPUT\n")
            wait_until(lambda start=start: "SHELL_OWNS_INPUT" in transcript[start:])
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, 80, 0, 0))
            resizes.append(f"requested {rows}x80, read back {terminal_size()}")
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
        elif finish == "interrupts":
            # Exercise every signal route on this live pipeline, avoiding a fresh
            # interpreter and terminal setup for each overlapping matrix combination.
            sources = ("terminal", "terminal", "process", "process", "thread", "thread", "group", "group")
            for expected_count, source in enumerate(sources, start=1):
                if source == "process":
                    # Signal cmd2 alone, as with `kill -INT <cmd2-pid>`.
                    os.kill(app_pid, signal.SIGINT)
                elif source == "thread":
                    interrupt_request.touch()
                elif source == "group":
                    os.killpg(pipeline_group, signal.SIGINT)
                else:
                    send("\x03")
                wait_until(lambda count=expected_count: transcript.count("PAGER_INTERRUPT\r\n") >= count)
                # Keep the handler alive long enough to observe a duplicate delivery,
                # then also check that a second real interrupt is not suppressed.
                deadline = time.monotonic() + 0.1
                wait_until(lambda deadline=deadline: time.monotonic() >= deadline)
                assert interrupts.read_text() == "I" * expected_count
        if finish != "exit_sigint":
            send("q")
        wait_until(lambda: os.tcgetpgrp(master) == job_group and "TEST>" in "\n".join(screen.display))
        if producer == "shell":
            # Ctrl-C reached the producer directly, as in a shell pipeline. It did not
            # merely die of a broken pipe once the pager was gone.
            wait_until(last_result.exists)
            assert last_result.read_text() == repr(-signal.SIGINT)
        start = len(transcript)
        send("help quit\n")
        wait_until(lambda: "Exit this application" in transcript[start:])
        send("quit\n")
        if launcher != "exec":
            wait_until(lambda: os.tcgetpgrp(master) == process.pid)
    finally:
        # Kill only this test's job, including stopped descendants, on assertion failure.
        if pager_pid.exists():
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(pager_pid.read_text()), signal.SIGKILL)
        if job_group is not None and job_group != process.pid:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(job_group, signal.SIGKILL)
        if pipeline_group is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(pipeline_group, signal.SIGKILL)
        # Release the PTY before reaping its session leader. On macOS, waiting
        # while the master is still open can leave terminal teardown blocked.
        os.close(master)
        process.kill()
        process.wait(timeout=5)


def test_pipeline_from_worker_thread_stays_isolated(tmp_path) -> None:
    """A pipe started off the main thread cannot install job-control handlers.

    It must fall back to running the pipeline in its own session, as before, rather
    than failing after Popen and leaving the child unreaped.
    """
    import pty

    shell = shutil.which("bash")
    if shell is None:
        pytest.skip("requires an interactive bash shell")
    application = tmp_path / "application.py"
    application.write_text(
        "from cmd2 import Cmd\n"
        "import os, threading\n"
        "app = Cmd()\n"
        "outcome = []\n"
        "worker = threading.Thread(target=lambda: outcome.append(app.onecmd_plus_hooks('help quit | cat')))\n"
        "worker.start()\n"
        "worker.join()\n"
        "try:\n"
        "    reaped = os.waitpid(-1, os.WNOHANG)\n"
        "except ChildProcessError:\n"
        "    reaped = None\n"
        "os.write(1, f'WORKER_DONE {outcome} {reaped}\\n'.encode())\n",
        encoding="utf-8",
    )
    master, slave = pty.openpty()
    bootstrap = (
        "import os, fcntl, termios; os.setsid(); "
        "fcntl.ioctl(0, termios.TIOCSCTTY, 0); "
        "os.execv(os.environ['TEST_SHELL'], ['bash', '--noprofile', '--norc', '-i'])"
    )
    env = dict(os.environ, TERM="xterm-256color", PS1="OUTER> ", TEST_SHELL=shell, SHELL=shell)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    process = subprocess.Popen([sys.executable, "-c", bootstrap], stdin=slave, stdout=slave, stderr=slave, env=env)
    os.close(slave)
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    transcript = ""

    def wait_until(predicate):
        nonlocal transcript
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.05)[0]:
                transcript += decoder.decode(os.read(master, 65536))
            if predicate():
                return
        pytest.fail(f"terminal condition timed out:\n{transcript}\n{describe_processes(process.pid, master)}")

    try:
        wait_until(lambda: "OUTER> " in transcript)
        os.write(master, f"{shlex.quote(sys.executable)} {shlex.quote(str(application))}\n".encode())
        # The whole line: a partial read must not satisfy the wait before the reap result arrives.
        wait_until(lambda: re.search(r"WORKER_DONE .*\r\n", transcript) is not None)
        assert "Exit this application" in transcript
        assert "WORKER_DONE [False] None" in transcript
    finally:
        os.close(master)
        process.kill()
        process.wait(timeout=5)


def test_pipeline_pager_can_set_terminal_modes_at_startup(tmp_path) -> None:
    """A pager such as less puts the terminal in raw mode as it starts, before reading its pipe.

    It has to own the terminal by then. A background tcsetattr() stops it with SIGTTOU, and
    on macOS the call then fails with EINTR once it is continued rather than being restarted.
    less ignores that failure, leaving a cooked terminal: q needs Enter and keys are echoed.
    """
    import pty
    import termios

    shell = shutil.which("bash")
    if shell is None:
        pytest.skip("requires an interactive bash shell")
    pager = tmp_path / "pager.py"
    outcome = tmp_path / "outcome"
    pager.write_text(
        "import os, pathlib, sys, termios, tty\n"
        "with os.fdopen(os.dup(sys.stderr.fileno()), 'rb', buffering=0) as terminal:\n"
        "    saved = termios.tcgetattr(terminal)\n"
        "    try:\n"
        # Whether cmd2 had lent the terminal yet, should the attempt fail.
        "        foreground = os.tcgetpgrp(terminal.fileno()) == os.getpgrp()\n"
        # Like less, make a single attempt and carry on whatever comes of it.
        "        try:\n"
        "            tty.setcbreak(terminal)\n"
        "            result = 'ok'\n"
        "        except termios.error as error:\n"
        "            result = f'{error!r}, foreground before the attempt: {foreground}'\n"
        f"        pathlib.Path({str(outcome)!r}).write_text(result)\n"
        "        while os.read(terminal.fileno(), 1) != b'q': pass\n"
        "    finally:\n"
        "        termios.tcsetattr(terminal, termios.TCSANOW, saved)\n",
        encoding="utf-8",
    )
    application = tmp_path / "application.py"
    application.write_text(
        "import pathlib, time\n"
        "from cmd2 import Cmd, utils\n"
        # The pipeline's first wait is cmd2's 0.2s startup check. Hold it open until the pager
        # has reported, so the test does not race that timer on a busy CI runner: what it checks
        # is that the pager owns the terminal throughout the check, however slowly it starts.
        "startup_wait = utils.ProcReader.wait_for_exit\n"
        "def held_startup_wait(reader, timeout=None):\n"
        "    utils.ProcReader.wait_for_exit = startup_wait\n"
        f"    outcome = pathlib.Path({str(outcome)!r})\n"
        "    deadline = time.monotonic() + 5\n"
        "    while time.monotonic() < deadline and not (outcome.exists() and outcome.read_text()):\n"
        "        time.sleep(0.01)\n"
        "    return startup_wait(reader, timeout)\n"
        "utils.ProcReader.wait_for_exit = held_startup_wait\n"
        "app = Cmd()\n"
        "app.prompt = 'TEST> '\n"
        "app.cmdloop()\n",
        encoding="utf-8",
    )
    master, slave = pty.openpty()
    bootstrap = (
        "import os, fcntl, termios; os.setsid(); "
        "fcntl.ioctl(0, termios.TIOCSCTTY, 0); "
        "os.execv(os.environ['TEST_SHELL'], ['bash', '--noprofile', '--norc', '-i'])"
    )
    env = dict(os.environ, TERM="xterm-256color", PS1="OUTER> ", TEST_SHELL=shell, SHELL=shell)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    process = subprocess.Popen([sys.executable, "-c", bootstrap], stdin=slave, stdout=slave, stderr=slave, env=env)
    os.close(slave)
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    transcript = ""

    def wait_until(predicate):
        nonlocal transcript
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.05)[0]:
                data = decoder.decode(os.read(master, 65536))
                transcript += data
                if "\x1b[6n" in data:
                    # Answer prompt-toolkit's cursor-position request as a terminal would.
                    os.write(master, b"\x1b[1;1R")
            if predicate():
                return
        pytest.fail(f"terminal condition timed out:\n{transcript}\n{describe_processes(process.pid, master)}")

    try:
        wait_until(lambda: "OUTER> " in transcript)
        os.write(master, f"{shlex.quote(sys.executable)} {shlex.quote(str(application))}\n".encode())
        wait_until(lambda: "TEST>" in transcript)
        os.write(master, f"help -v | {shlex.quote(sys.executable)} {shlex.quote(str(pager))}\n".encode())
        wait_until(outcome.exists)
        wait_until(lambda: outcome.read_text() != "")
        assert outcome.read_text() == "ok"
        assert not termios.tcgetattr(master)[3] & termios.ICANON
        # A cooked terminal would hold the key back until Enter.
        start = len(transcript)
        os.write(master, b"q")
        wait_until(lambda: "TEST>" in transcript[start:])
        os.write(master, b"quit\n")
        wait_until(lambda: os.tcgetpgrp(master) == process.pid)
    finally:
        os.close(master)
        process.kill()
        process.wait(timeout=5)


@pytest.mark.parametrize("producer", ["command", "shell"])
def test_pipeline_children_inherit_an_ordinary_signal_mask(tmp_path, producer) -> None:
    """Processes started during a terminal pipeline must not inherit a blocked SIGTTOU.

    cmd2 blocks SIGTTOU for itself while it lends the terminal. A signal mask survives fork
    and exec, so a child spawned with it blocked -- a shell producer, or a subprocess run by
    command code -- would keep it for life, and change terminal modes from the background
    where it should be stopped.
    """
    import pty

    shell = shutil.which("bash")
    if shell is None:
        pytest.skip("requires an interactive bash shell")
    probe = tmp_path / "probe.py"
    outcome = tmp_path / "outcome"
    probe.write_text(
        "import pathlib, signal\n"
        "blocked = signal.SIGTTOU in signal.pthread_sigmask(signal.SIG_BLOCK, [])\n"
        f"pathlib.Path({str(outcome)!r}).write_text(repr(blocked))\n",
        encoding="utf-8",
    )
    application = tmp_path / "application.py"
    application.write_text(
        "import subprocess, sys\n"
        "from cmd2 import Cmd\n"
        "class App(Cmd):\n"
        "    def do_probe(self, _):\n"
        "        self.poutput('probing')\n"
        f"        subprocess.run([sys.executable, {str(probe)!r}], check=True)\n"
        "app = App()\n"
        "app.prompt = 'TEST> '\n"
        "app.cmdloop()\n",
        encoding="utf-8",
    )
    master, slave = pty.openpty()
    bootstrap = (
        "import os, fcntl, termios; os.setsid(); "
        "fcntl.ioctl(0, termios.TIOCSCTTY, 0); "
        "os.execv(os.environ['TEST_SHELL'], ['bash', '--noprofile', '--norc', '-i'])"
    )
    env = dict(os.environ, TERM="xterm-256color", PS1="OUTER> ", TEST_SHELL=shell, SHELL=shell)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    process = subprocess.Popen([sys.executable, "-c", bootstrap], stdin=slave, stdout=slave, stderr=slave, env=env)
    os.close(slave)
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    transcript = ""

    def wait_until(predicate):
        nonlocal transcript
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.05)[0]:
                data = decoder.decode(os.read(master, 65536))
                transcript += data
                if "\x1b[6n" in data:
                    # Answer prompt-toolkit's cursor-position request as a terminal would.
                    os.write(master, b"\x1b[1;1R")
            if predicate():
                return
        pytest.fail(f"terminal condition timed out:\n{transcript}\n{describe_processes(process.pid, master)}")

    command = "probe" if producer == "command" else f"shell {shlex.quote(sys.executable)} {shlex.quote(str(probe))}"
    try:
        wait_until(lambda: "OUTER> " in transcript)
        os.write(master, f"{shlex.quote(sys.executable)} {shlex.quote(str(application))}\n".encode())
        wait_until(lambda: "TEST>" in transcript)
        start = len(transcript)
        os.write(master, f"{command} | cat\n".encode())
        wait_until(lambda: outcome.exists() and outcome.read_text() != "" and "TEST>" in transcript[start:])
        assert outcome.read_text() == "False"
        os.write(master, b"quit\n")
        wait_until(lambda: os.tcgetpgrp(master) == process.pid)
    finally:
        os.close(master)
        process.kill()
        process.wait(timeout=5)


@pytest.mark.parametrize("suspend", [False, True])
def test_shell_producer_keeps_the_terminal_after_its_consumer_exits(tmp_path, suspend) -> None:
    """A shell producer that outlives its consumer still reads the terminal.

    do_shell() lends the terminal to the pipeline's group for as long as the producer runs.
    The consumer's exit must not take it back early: the producer would stop with SIGTTIN on
    its next terminal read, and nothing watches an ordinary shell command for stops.

    Ctrl-Z then reaches the producer alone, since it is all that is left of the foreground
    group. With the consumer's watcher gone, do_shell() has to relay that stop to the
    whole job itself, or it waits forever on a stopped child.
    """
    import pty

    shell = shutil.which("bash")
    if shell is None:
        pytest.skip("requires an interactive bash shell")
    consumer = tmp_path / "consumer.py"
    consumer.write_text("import os, time\ntime.sleep(0.5)\nos.write(2, b'CONSUMER_DONE\\n')\n", encoding="utf-8")
    producer = tmp_path / "producer.py"
    producer.write_text(
        "import os, signal, time\n"
        # Interactive bash leaves TTIN ignored in what it execs, which turns a background read into EIO.
        "signal.signal(signal.SIGTTIN, signal.SIG_DFL)\n"
        "time.sleep(1.5)\n"
        "os.write(2, b'PRODUCER> ')\n"
        "os.write(2, b'GOT ' + os.read(0, 7))\n",
        encoding="utf-8",
    )
    application = tmp_path / "application.py"
    application.write_text(
        "from cmd2 import Cmd\napp = Cmd()\napp.prompt = 'TEST> '\napp.cmdloop()\n",
        encoding="utf-8",
    )
    master, slave = pty.openpty()
    bootstrap = (
        "import os, fcntl, termios; os.setsid(); "
        "fcntl.ioctl(0, termios.TIOCSCTTY, 0); "
        "os.execv(os.environ['TEST_SHELL'], ['bash', '--noprofile', '--norc', '-i'])"
    )
    env = dict(os.environ, TERM="xterm-256color", PS1="OUTER> ", TEST_SHELL=shell, SHELL=shell)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    process = subprocess.Popen([sys.executable, "-c", bootstrap], stdin=slave, stdout=slave, stderr=slave, env=env)
    os.close(slave)
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    transcript = ""

    def wait_until(predicate):
        nonlocal transcript
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.05)[0]:
                data = decoder.decode(os.read(master, 65536))
                transcript += data
                if "\x1b[6n" in data:
                    # Answer prompt-toolkit's cursor-position request as a terminal would.
                    os.write(master, b"\x1b[1;1R")
            if predicate():
                return
        pytest.fail(f"terminal condition timed out:\n{transcript}\n{describe_processes(process.pid, master)}")

    python = shlex.quote(sys.executable)
    try:
        wait_until(lambda: "OUTER> " in transcript)
        os.write(master, f"{python} {shlex.quote(str(application))}\n".encode())
        wait_until(lambda: "TEST>" in transcript)
        os.write(master, f"shell {python} {shlex.quote(str(producer))} | {python} {shlex.quote(str(consumer))}\n".encode())
        wait_until(lambda: "CONSUMER_DONE\r\n" in transcript)
        wait_until(lambda: "PRODUCER> " in transcript)
        if suspend:
            start = len(transcript)
            os.write(master, b"\x1a")
            wait_until(lambda: os.tcgetpgrp(master) == process.pid and "OUTER> " in transcript[start:])
            os.write(master, b"fg\n")
            wait_until(lambda: os.tcgetpgrp(master) not in (process.pid, os.getpgid(process.pid)))
        os.write(master, b"answer\n")
        wait_until(lambda: "GOT answer" in transcript)
        # cmd2 owns the terminal again once the producer is done.
        start = len(transcript)
        wait_until(lambda: "TEST>" in transcript[start:])
        os.write(master, b"help quit\n")
        wait_until(lambda: "Exit this application" in transcript[start:])
        os.write(master, b"quit\n")
        wait_until(lambda: os.tcgetpgrp(master) == process.pid)
    finally:
        os.close(master)
        process.kill()
        process.wait(timeout=5)
