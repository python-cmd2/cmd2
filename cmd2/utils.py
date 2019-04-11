# coding=utf-8
"""Shared utility functions"""

import collections
import os
import re
import subprocess
import sys
import threading
import unicodedata
from typing import Any, BinaryIO, Iterable, List, Optional, TextIO, Union

from wcwidth import wcswidth

from . import constants


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from a string.

    :param text: string which may contain ANSI escape codes
    :return: the same string with any ANSI escape codes removed
    """
    return constants.ANSI_ESCAPE_RE.sub('', text)


def ansi_safe_wcswidth(text: str) -> int:
    """
    Wraps wcswidth to make it compatible with colored strings

    :param text: the string being measured
    """
    # Strip ANSI escape codes since they cause wcswidth to return -1
    return wcswidth(strip_ansi(text))


def is_quoted(arg: str) -> bool:
    """
    Checks if a string is quoted
    :param arg: the string being checked for quotes
    :return: True if a string is quoted
    """
    return len(arg) > 1 and arg[0] == arg[-1] and arg[0] in constants.QUOTES


def quote_string_if_needed(arg: str) -> str:
    """ Quotes a string if it contains spaces and isn't already quoted """
    if is_quoted(arg) or ' ' not in arg:
        return arg

    if '"' in arg:
        quote = "'"
    else:
        quote = '"'

    return quote + arg + quote


def strip_quotes(arg: str) -> str:
    """ Strip outer quotes from a string.

     Applies to both single and double quotes.

    :param arg:  string to strip outer quotes from
    :return: same string with potentially outer quotes stripped
    """
    if is_quoted(arg):
        arg = arg[1:-1]
    return arg


def namedtuple_with_defaults(typename: str, field_names: Union[str, List[str]],
                             default_values: collections.Iterable = ()):
    """
    Convenience function for defining a namedtuple with default values

    From: https://stackoverflow.com/questions/11351032/namedtuple-and-default-values-for-optional-keyword-arguments

    Examples:
        >>> Node = namedtuple_with_defaults('Node', 'val left right')
        >>> Node()
        Node(val=None, left=None, right=None)
        >>> Node = namedtuple_with_defaults('Node', 'val left right', [1, 2, 3])
        >>> Node()
        Node(val=1, left=2, right=3)
        >>> Node = namedtuple_with_defaults('Node', 'val left right', {'right':7})
        >>> Node()
        Node(val=None, left=None, right=7)
        >>> Node(4)
        Node(val=4, left=None, right=7)
    """
    T = collections.namedtuple(typename, field_names)
    # noinspection PyProtectedMember,PyUnresolvedReferences
    T.__new__.__defaults__ = (None,) * len(T._fields)
    if isinstance(default_values, collections.Mapping):
        prototype = T(**default_values)
    else:
        prototype = T(*default_values)
    T.__new__.__defaults__ = tuple(prototype)
    return T


def cast(current: Any, new: str) -> Any:
    """Tries to force a new value into the same type as the current when trying to set the value for a parameter.

    :param current: current value for the parameter, type varies
    :param new: new value
    :return: new value with same type as current, or the current value if there was an error casting
    """
    typ = type(current)
    orig_new = new

    if typ == bool:
        try:
            return bool(int(new))
        except (ValueError, TypeError):
            pass
        try:
            new = new.lower()
            if (new == 'on') or (new[0] in ('y', 't')):
                return True
            if (new == 'off') or (new[0] in ('n', 'f')):
                return False
        except AttributeError:
            pass
    else:
        try:
            return typ(new)
        except (ValueError, TypeError):
            pass
    print("Problem setting parameter (now {}) to {}; incorrect type?".format(current, orig_new))
    return current


def which(editor: str) -> Optional[str]:
    """Find the full path of a given editor.

    Return the full path of the given editor, or None if the editor can
    not be found.

    :param editor: filename of the editor to check, ie 'notepad.exe' or 'vi'
    :return: a full path or None
    """
    try:
        editor_path = subprocess.check_output(['which', editor], stderr=subprocess.STDOUT).strip()
        editor_path = editor_path.decode()
    except subprocess.CalledProcessError:
        editor_path = None
    return editor_path


def is_text_file(file_path: str) -> bool:
    """Returns if a file contains only ASCII or UTF-8 encoded text.

    :param file_path: path to the file being checked
    :return: True if the file is a text file, False if it is binary.
    """
    import codecs

    expanded_path = os.path.abspath(os.path.expanduser(file_path.strip()))
    valid_text_file = False

    # Check if the file is ASCII
    try:
        with codecs.open(expanded_path, encoding='ascii', errors='strict') as f:
            # Make sure the file has at least one line of text
            # noinspection PyUnusedLocal
            if sum(1 for line in f) > 0:
                valid_text_file = True
    except OSError:  # pragma: no cover
        pass
    except UnicodeDecodeError:
        # The file is not ASCII. Check if it is UTF-8.
        try:
            with codecs.open(expanded_path, encoding='utf-8', errors='strict') as f:
                # Make sure the file has at least one line of text
                # noinspection PyUnusedLocal
                if sum(1 for line in f) > 0:
                    valid_text_file = True
        except OSError:  # pragma: no cover
            pass
        except UnicodeDecodeError:
            # Not UTF-8
            pass

    return valid_text_file


def remove_duplicates(list_to_prune: List) -> List:
    """Removes duplicates from a list while preserving order of the items.

    :param list_to_prune: the list being pruned of duplicates
    :return: The pruned list
    """
    temp_dict = collections.OrderedDict()
    for item in list_to_prune:
        temp_dict[item] = None

    return list(temp_dict.keys())


def norm_fold(astr: str) -> str:
    """Normalize and casefold Unicode strings for saner comparisons.

    :param astr: input unicode string
    :return: a normalized and case-folded version of the input string
    """
    return unicodedata.normalize('NFC', astr).casefold()


def alphabetical_sort(list_to_sort: Iterable[str]) -> List[str]:
    """Sorts a list of strings alphabetically.

    For example: ['a1', 'A11', 'A2', 'a22', 'a3']

    To sort a list in place, don't call this method, which makes a copy. Instead, do this:

    my_list.sort(key=norm_fold)

    :param list_to_sort: the list being sorted
    :return: the sorted list
    """
    return sorted(list_to_sort, key=norm_fold)


def try_int_or_force_to_lower_case(input_str: str) -> Union[int, str]:
    """
    Tries to convert the passed-in string to an integer. If that fails, it converts it to lower case using norm_fold.
    :param input_str: string to convert
    :return: the string as an integer or a lower case version of the string
    """
    try:
        return int(input_str)
    except ValueError:
        return norm_fold(input_str)


def natural_keys(input_str: str) -> List[Union[int, str]]:
    """
    Converts a string into a list of integers and strings to support natural sorting (see natural_sort).

    For example: natural_keys('abc123def') -> ['abc', '123', 'def']
    :param input_str: string to convert
    :return: list of strings and integers
    """
    return [try_int_or_force_to_lower_case(substr) for substr in re.split(r'(\d+)', input_str)]


def natural_sort(list_to_sort: Iterable[str]) -> List[str]:
    """
    Sorts a list of strings case insensitively as well as numerically.

    For example: ['a1', 'A2', 'a3', 'A11', 'a22']

    To sort a list in place, don't call this method, which makes a copy. Instead, do this:

    my_list.sort(key=natural_keys)

    :param list_to_sort: the list being sorted
    :return: the list sorted naturally
    """
    return sorted(list_to_sort, key=natural_keys)


def unquote_redirection_tokens(args: List[str]) -> None:
    """
    Unquote redirection tokens in a list of command-line arguments
    This is used when redirection tokens have to be passed to another command
    :param args: the command line args
    """
    for i, arg in enumerate(args):
        unquoted_arg = strip_quotes(arg)
        if unquoted_arg in constants.REDIRECTION_TOKENS:
            args[i] = unquoted_arg


def find_editor() -> str:
    """Find a reasonable editor to use by default for the system that the cmd2 application is running on."""
    editor = os.environ.get('EDITOR')
    if not editor:
        if sys.platform[:3] == 'win':
            editor = 'notepad'
        else:
            # Favor command-line editors first so we don't leave the terminal to edit
            for editor in ['vim', 'vi', 'emacs', 'nano', 'pico', 'gedit', 'kate', 'subl', 'geany', 'atom']:
                if which(editor):
                    break
    return editor


class StdSim(object):
    """
    Class to simulate behavior of sys.stdout or sys.stderr.
    Stores contents in internal buffer and optionally echos to the inner stream it is simulating.
    """
    def __init__(self, inner_stream, echo: bool = False,
                 encoding: str = 'utf-8', errors: str = 'replace') -> None:
        """
        Initializer
        :param inner_stream: the emulated stream
        :param echo: if True, then all input will be echoed to inner_stream
        :param encoding: codec for encoding/decoding strings (defaults to utf-8)
        :param errors: how to handle encoding/decoding errors (defaults to replace)
        """
        self.inner_stream = inner_stream
        self.echo = echo
        self.encoding = encoding
        self.errors = errors
        self.pause_storage = False
        self.buffer = ByteBuf(self)

    def write(self, s: str) -> None:
        """Add str to internal bytes buffer and if echo is True, echo contents to inner stream"""
        if not isinstance(s, str):
            raise TypeError('write() argument must be str, not {}'.format(type(s)))

        if not self.pause_storage:
            self.buffer.byte_buf += s.encode(encoding=self.encoding, errors=self.errors)
        if self.echo:
            self.inner_stream.write(s)

    def getvalue(self) -> str:
        """Get the internal contents as a str"""
        return self.buffer.byte_buf.decode(encoding=self.encoding, errors=self.errors)

    def getbytes(self) -> bytes:
        """Get the internal contents as bytes"""
        return bytes(self.buffer.byte_buf)

    def read(self) -> str:
        """Read from the internal contents as a str and then clear them out"""
        result = self.getvalue()
        self.clear()
        return result

    def readbytes(self) -> bytes:
        """Read from the internal contents as bytes and then clear them out"""
        result = self.getbytes()
        self.clear()
        return result

    def clear(self) -> None:
        """Clear the internal contents"""
        self.buffer.byte_buf.clear()

    def isatty(self) -> bool:
        """StdSim only considered an interactive stream if `echo` is True and `inner_stream` is a tty."""
        if self.echo:
            return self.inner_stream.isatty()
        else:
            return False

    def __getattr__(self, item: str):
        if item in self.__dict__:
            return self.__dict__[item]
        else:
            return getattr(self.inner_stream, item)


class ByteBuf(object):
    """
    Used by StdSim to write binary data and stores the actual bytes written
    """
    def __init__(self, std_sim_instance: StdSim) -> None:
        self.byte_buf = bytearray()
        self.std_sim_instance = std_sim_instance

    def write(self, b: bytes) -> None:
        """Add bytes to internal bytes buffer and if echo is True, echo contents to inner stream."""
        if not isinstance(b, bytes):
            raise TypeError('a bytes-like object is required, not {}'.format(type(b)))
        if not self.std_sim_instance.pause_storage:
            self.byte_buf += b
        if self.std_sim_instance.echo:
            self.std_sim_instance.inner_stream.buffer.write(b)


class ProcReader(object):
    """
    Used to captured stdout and stderr from a Popen process if any of those were set to subprocess.PIPE.
    If neither are pipes, then the process will run normally and no output will be captured.
    """
    def __init__(self, proc: subprocess.Popen, stdout: Union[StdSim, BinaryIO, TextIO],
                 stderr: Union[StdSim, BinaryIO, TextIO]) -> None:
        """
        ProcReader initializer
        :param proc: the Popen process being read from
        :param stdout: the stream to write captured stdout
        :param stderr: the stream to write captured stderr
        """
        self._proc = proc
        self._stdout = stdout
        self._stderr = stderr

        self._out_thread = threading.Thread(name='out_thread', target=self._reader_thread_func,
                                            kwargs={'read_stdout': True})

        self._err_thread = threading.Thread(name='out_thread', target=self._reader_thread_func,
                                            kwargs={'read_stdout': False})

        # Start the reader threads for pipes only
        if self._proc.stdout is not None:
            self._out_thread.start()
        if self._proc.stderr is not None:
            self._err_thread.start()

    def send_sigint(self) -> None:
        """Send a SIGINT to the process similar to if <Ctrl>+C were pressed."""
        import signal
        if sys.platform.startswith('win'):
            signal_to_send = signal.CTRL_C_EVENT
        else:
            signal_to_send = signal.SIGINT
        self._proc.send_signal(signal_to_send)

    def terminate(self) -> None:
        """Terminate the process"""
        self._proc.terminate()

    def wait(self) -> None:
        """Wait for the process to finish"""
        if self._out_thread.is_alive():
            self._out_thread.join()
        if self._err_thread.is_alive():
            self._err_thread.join()

        # Handle case where the process ended before the last read could be done.
        # This will return None for the streams that weren't pipes.
        out, err = self._proc.communicate()

        if out:
            self._write_bytes(self._stdout, out)
        if err:
            self._write_bytes(self._stderr, err)

    def _reader_thread_func(self, read_stdout: bool) -> None:
        """
        Thread function that reads a stream from the process
        :param read_stdout: if True, then this thread deals with stdout. Otherwise it deals with stderr.
        """
        if read_stdout:
            read_stream = self._proc.stdout
            write_stream = self._stdout
        else:
            read_stream = self._proc.stderr
            write_stream = self._stderr

        # The thread should have been started only if this stream was a pipe
        assert read_stream is not None

        # Run until process completes
        while self._proc.poll() is None:
            # noinspection PyUnresolvedReferences
            available = read_stream.peek()
            if available:
                read_stream.read(len(available))
                self._write_bytes(write_stream, available)

    @staticmethod
    def _write_bytes(stream: Union[StdSim, BinaryIO, TextIO], to_write: bytes) -> None:
        """
        Write bytes to a stream
        :param stream: the stream being written to
        :param to_write: the bytes being written
        """
        try:
            if hasattr(stream, 'buffer'):
                stream.buffer.write(to_write)
            else:
                stream.write(to_write)
        except BrokenPipeError:
            # This occurs if output is being piped to a process that closed
            pass


class ContextFlag(object):
    """A context manager which is also used as a boolean flag value within the default sigint handler.

    Its main use is as a flag to prevent the SIGINT handler in cmd2 from raising a KeyboardInterrupt
    while a critical code section has set the flag to True. Because signal handling is always done on the
    main thread, this class is not thread-safe since there is no need.
    """
    def __init__(self) -> None:
        # When this flag has a positive value, it is considered set.
        # When it is 0, it is not set. It should never go below 0.
        self.__count = 0

    def __bool__(self) -> bool:
        return self.__count > 0

    def __enter__(self) -> None:
        self.__count += 1

    def __exit__(self, *args) -> None:
        self.__count -= 1
        if self.__count < 0:
            raise ValueError("count has gone below 0")


class RedirectionSavedState(object):
    """Created by each command to store information about their redirection."""

    def __init__(self, self_stdout: Union[StdSim, BinaryIO, TextIO], sys_stdout: Union[StdSim, BinaryIO, TextIO],
                 pipe_proc_reader: Optional[ProcReader]) -> None:
        # Used to restore values after the command ends
        self.saved_self_stdout = self_stdout
        self.saved_sys_stdout = sys_stdout
        self.saved_pipe_proc_reader = pipe_proc_reader

        # Tells if the command is redirecting
        self.redirecting = False

        # If the command created a process to pipe to, then then is its reader
        self.pipe_proc_reader = None
