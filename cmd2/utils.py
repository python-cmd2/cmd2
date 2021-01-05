# coding=utf-8
"""Shared utility functions"""

import collections
import collections.abc as collections_abc
import functools
import glob
import inspect
import itertools
import os
import re
import subprocess
import sys
import threading
import unicodedata
from enum import (
    Enum,
)
from typing import (
    IO,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    TextIO,
    Type,
    Union,
)

from . import (
    constants,
)


def is_quoted(arg: str) -> bool:
    """
    Checks if a string is quoted

    :param arg: the string being checked for quotes
    :return: True if a string is quoted
    """
    return len(arg) > 1 and arg[0] == arg[-1] and arg[0] in constants.QUOTES


def quote_string(arg: str) -> str:
    """Quote a string"""
    if '"' in arg:
        quote = "'"
    else:
        quote = '"'

    return quote + arg + quote


def quote_string_if_needed(arg: str) -> str:
    """Quote a string if it contains spaces and isn't already quoted"""
    if is_quoted(arg) or ' ' not in arg:
        return arg

    return quote_string(arg)


def strip_quotes(arg: str) -> str:
    """Strip outer quotes from a string.

     Applies to both single and double quotes.

    :param arg:  string to strip outer quotes from
    :return: same string with potentially outer quotes stripped
    """
    if is_quoted(arg):
        arg = arg[1:-1]
    return arg


def str_to_bool(val: str) -> bool:
    """Converts a string to a boolean based on its value.

    :param val: string being converted
    :return: boolean value expressed in the string
    :raises: ValueError if the string does not contain a value corresponding to a boolean value
    """
    if isinstance(val, str):
        if val.capitalize() == str(True):
            return True
        elif val.capitalize() == str(False):
            return False
    raise ValueError("must be True or False (case-insensitive)")


class CompletionError(Exception):
    """
    Raised during tab completion operations to report any sort of error you want printed. This can also be used
    just to display a message, even if it's not an error. For instance, ArgparseCompleter raises CompletionErrors
    to display tab completion hints and sets apply_style to False so hints aren't colored like error text.

    Example use cases

    - Reading a database to retrieve a tab completion data set failed
    - A previous command line argument that determines the data set being completed is invalid
    - Tab completion hints
    """
    def __init__(self, *args, apply_style: bool = True, **kwargs):
        """
        Initializer for CompletionError
        :param apply_style: If True, then ansi.style_error will be applied to the message text when printed.
                            Set to False in cases where the message text already has the desired style.
                            Defaults to True.
        """
        self.apply_style = apply_style

        # noinspection PyArgumentList
        super().__init__(*args, **kwargs)


class Settable:
    """Used to configure a cmd2 instance member to be settable via the set command in the CLI"""
    def __init__(self, name: str, val_type: Callable, description: str, *,
                 onchange_cb: Callable[[str, Any, Any], Any] = None,
                 choices: Iterable = None,
                 choices_function: Optional[Callable] = None,
                 choices_method: Optional[Callable] = None,
                 completer_function: Optional[Callable] = None,
                 completer_method: Optional[Callable] = None):
        """
        Settable Initializer

        :param name: name of the instance attribute being made settable
        :param val_type: callable used to cast the string value from the command line into its proper type and
                         even validate its value. Setting this to bool provides tab completion for true/false and
                         validation using str_to_bool(). The val_type function should raise an exception if it fails.
                         This exception will be caught and printed by Cmd.do_set().
        :param description: string describing this setting
        :param onchange_cb: optional function or method to call when the value of this settable is altered
                            by the set command. (e.g. onchange_cb=self.debug_changed)

                            Cmd.do_set() passes the following 3 arguments to onchange_cb:
                                param_name: str - name of the changed parameter
                                old_value: Any - the value before being changed
                                new_value: Any - the value after being changed

        The following optional settings provide tab completion for a parameter's values. They correspond to the
        same settings in argparse-based tab completion. A maximum of one of these should be provided.

        :param choices: iterable of accepted values
        :param choices_function: function that provides choices for this argument
        :param choices_method: cmd2-app method that provides choices for this argument (See note below)
        :param completer_function: tab completion function that provides choices for this argument
        :param completer_method: cmd2-app tab completion method that provides choices
                                 for this argument (See note below)

        Note:
        For choices_method and completer_method, do not set them to a bound method. This is because
        ArgparseCompleter passes the self argument explicitly to these functions.

        Therefore instead of passing something like self.path_complete, pass cmd2.Cmd.path_complete.
        """
        if val_type == bool:
            val_type = str_to_bool
            choices = ['true', 'false']

        self.name = name
        self.val_type = val_type
        self.description = description
        self.onchange_cb = onchange_cb
        self.choices = choices
        self.choices_function = choices_function
        self.choices_method = choices_method
        self.completer_function = completer_function
        self.completer_method = completer_method


def namedtuple_with_defaults(typename: str, field_names: Union[str, List[str]],
                             default_values: collections_abc.Iterable = ()):
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
    if isinstance(default_values, collections_abc.Mapping):
        prototype = T(**default_values)
    else:
        prototype = T(*default_values)
    T.__new__.__defaults__ = tuple(prototype)
    return T


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


def quote_specific_tokens(tokens: List[str], tokens_to_quote: List[str]) -> None:
    """
    Quote specific tokens in a list

    :param tokens: token list being edited
    :param tokens_to_quote: the tokens, which if present in tokens, to quote
    """
    for i, token in enumerate(tokens):
        if token in tokens_to_quote:
            tokens[i] = quote_string(token)


def unquote_specific_tokens(tokens: List[str], tokens_to_unquote: List[str]) -> None:
    """
    Unquote specific tokens in a list

    :param tokens: token list being edited
    :param tokens_to_unquote: the tokens, which if present in tokens, to unquote
    """
    for i, token in enumerate(tokens):
        unquoted_token = strip_quotes(token)
        if unquoted_token in tokens_to_unquote:
            tokens[i] = unquoted_token


def expand_user(token: str) -> str:
    """
    Wrap os.expanduser() to support expanding ~ in quoted strings
    :param token: the string to expand
    """
    if token:
        if is_quoted(token):
            quote_char = token[0]
            token = strip_quotes(token)
        else:
            quote_char = ''

        token = os.path.expanduser(token)

        # Restore the quotes even if not needed to preserve what the user typed
        if quote_char:
            token = quote_char + token + quote_char

    return token


def expand_user_in_tokens(tokens: List[str]) -> None:
    """
    Call expand_user() on all tokens in a list of strings
    :param tokens: tokens to expand
    """
    for index, _ in enumerate(tokens):
        tokens[index] = expand_user(tokens[index])


def find_editor() -> Optional[str]:
    """
    Used to set cmd2.Cmd.DEFAULT_EDITOR. If EDITOR env variable is set, that will be used.
    Otherwise the function will look for a known editor in directories specified by PATH env variable.
    :return: Default editor or None
    """
    editor = os.environ.get('EDITOR')
    if not editor:
        if sys.platform[:3] == 'win':
            editors = ['code.cmd', 'notepad++.exe', 'notepad.exe']
        else:
            editors = ['vim', 'vi', 'emacs', 'nano', 'pico', 'joe', 'code', 'subl', 'atom', 'gedit', 'geany', 'kate']

        paths = [p for p in os.getenv('PATH').split(os.path.pathsep) if not os.path.islink(p)]
        for editor, path in itertools.product(editors, paths):
            editor_path = os.path.join(path, editor)
            if os.path.isfile(editor_path) and os.access(editor_path, os.X_OK):
                if sys.platform[:3] == 'win':
                    # Remove extension from Windows file names
                    editor = os.path.splitext(editor)[0]
                break
        else:
            editor = None

    return editor


def files_from_glob_pattern(pattern: str, access=os.F_OK) -> List[str]:
    """Return a list of file paths based on a glob pattern.

    Only files are returned, not directories, and optionally only files for which the user has a specified access to.

    :param pattern: file name or glob pattern
    :param access: file access type to verify (os.* where * is F_OK, R_OK, W_OK, or X_OK)
    :return: list of files matching the name or glob pattern
    """
    return [f for f in glob.glob(pattern) if os.path.isfile(f) and os.access(f, access)]


def files_from_glob_patterns(patterns: List[str], access=os.F_OK) -> List[str]:
    """Return a list of file paths based on a list of glob patterns.

    Only files are returned, not directories, and optionally only files for which the user has a specified access to.

    :param patterns: list of file names and/or glob patterns
    :param access: file access type to verify (os.* where * is F_OK, R_OK, W_OK, or X_OK)
    :return: list of files matching the names and/or glob patterns
    """
    files = []
    for pattern in patterns:
        matches = files_from_glob_pattern(pattern, access=access)
        files.extend(matches)
    return files


def get_exes_in_path(starts_with: str) -> List[str]:
    """Returns names of executables in a user's path

    :param starts_with: what the exes should start with. leave blank for all exes in path.
    :return: a list of matching exe names
    """
    # Purposely don't match any executable containing wildcards
    wildcards = ['*', '?']
    for wildcard in wildcards:
        if wildcard in starts_with:
            return []

    # Get a list of every directory in the PATH environment variable and ignore symbolic links
    paths = [p for p in os.getenv('PATH').split(os.path.pathsep) if not os.path.islink(p)]

    # Use a set to store exe names since there can be duplicates
    exes_set = set()

    # Find every executable file in the user's path that matches the pattern
    for path in paths:
        full_path = os.path.join(path, starts_with)
        matches = files_from_glob_pattern(full_path + '*', access=os.X_OK)

        for match in matches:
            exes_set.add(os.path.basename(match))

    return list(exes_set)


class StdSim:
    """
    Class to simulate behavior of sys.stdout or sys.stderr.
    Stores contents in internal buffer and optionally echos to the inner stream it is simulating.
    """
    def __init__(self, inner_stream, *, echo: bool = False,
                 encoding: str = 'utf-8', errors: str = 'replace') -> None:
        """
        StdSim Initializer
        :param inner_stream: the wrapped stream. Should be a TextIO or StdSim instance.
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

    def read(self, size: Optional[int] = -1) -> str:
        """Read from the internal contents as a str and then clear them out"""
        if size is None or size == -1:
            result = self.getvalue()
            self.clear()
        else:
            result = self.buffer.byte_buf[:size].decode(encoding=self.encoding, errors=self.errors)
            self.buffer.byte_buf = self.buffer.byte_buf[size:]

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

    @property
    def line_buffering(self) -> bool:
        """
        Handle when the inner stream doesn't have a line_buffering attribute which is the case
        when running unit tests because pytest sets stdout to a pytest EncodedFile object.
        """
        try:
            return self.inner_stream.line_buffering
        except AttributeError:
            return False

    def __getattr__(self, item: str):
        if item in self.__dict__:
            return self.__dict__[item]
        else:
            return getattr(self.inner_stream, item)


class ByteBuf:
    """
    Used by StdSim to write binary data and stores the actual bytes written
    """
    # Used to know when to flush the StdSim
    NEWLINES = [b'\n', b'\r']

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

            # Since StdSim wraps TextIO streams, we will flush the stream if line buffering is on
            # and the bytes being written contain a new line character. This is helpful when StdSim
            # is being used to capture output of a shell command because it causes the output to print
            # to the screen more often than if we waited for the stream to flush its buffer.
            if self.std_sim_instance.line_buffering:
                if any(newline in b for newline in ByteBuf.NEWLINES):
                    self.std_sim_instance.flush()


class ProcReader:
    """
    Used to capture stdout and stderr from a Popen process if any of those were set to subprocess.PIPE.
    If neither are pipes, then the process will run normally and no output will be captured.
    """
    def __init__(self, proc: subprocess.Popen, stdout: Union[StdSim, TextIO],
                 stderr: Union[StdSim, TextIO]) -> None:
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
        """Send a SIGINT to the process similar to if <Ctrl>+C were pressed"""
        import signal
        if sys.platform.startswith('win'):
            # cmd2 started the Windows process in a new process group. Therefore
            # a CTRL_C_EVENT can't be sent to it. Send a CTRL_BREAK_EVENT instead.
            self._proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            # Since cmd2 uses shell=True in its Popen calls, we need to send the SIGINT to
            # the whole process group to make sure it propagates further than the shell
            try:
                group_id = os.getpgid(self._proc.pid)
                os.killpg(group_id, signal.SIGINT)
            except ProcessLookupError:
                return

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
    def _write_bytes(stream: Union[StdSim, TextIO], to_write: bytes) -> None:
        """
        Write bytes to a stream
        :param stream: the stream being written to
        :param to_write: the bytes being written
        """
        try:
            stream.buffer.write(to_write)
        except BrokenPipeError:
            # This occurs if output is being piped to a process that closed
            pass


class ContextFlag:
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


class RedirectionSavedState:
    """Created by each command to store information required to restore state after redirection"""
    def __init__(self, self_stdout: Union[StdSim, IO[str]], sys_stdout: Union[StdSim, IO[str]],
                 pipe_proc_reader: Optional[ProcReader], saved_redirecting: bool) -> None:
        """
        RedirectionSavedState initializer
        :param self_stdout: saved value of Cmd.stdout
        :param sys_stdout: saved value of sys.stdout
        :param pipe_proc_reader: saved value of Cmd._cur_pipe_proc_reader
        :param saved_redirecting: saved value of Cmd._redirecting
        """
        # Tells if command is redirecting
        self.redirecting = False

        # Used to restore values after redirection ends
        self.saved_self_stdout = self_stdout
        self.saved_sys_stdout = sys_stdout

        # Used to restore values after command ends regardless of whether the command redirected
        self.saved_pipe_proc_reader = pipe_proc_reader
        self.saved_redirecting = saved_redirecting


# noinspection PyUnusedLocal
def basic_complete(text: str, line: str, begidx: int, endidx: int, match_against: Iterable) -> List[str]:
    """
    Basic tab completion function that matches against a list of strings without considering line contents
    or cursor position. The args required by this function are defined in the header of Python's cmd.py.

    :param text: the string prefix we are attempting to match (all matches must begin with it)
    :param line: the current input line with leading whitespace removed
    :param begidx: the beginning index of the prefix text
    :param endidx: the ending index of the prefix text
    :param match_against: the strings being matched against
    :return: a list of possible tab completions
    """
    return [cur_match for cur_match in match_against if cur_match.startswith(text)]


class TextAlignment(Enum):
    """Horizontal text alignment"""
    LEFT = 1
    CENTER = 2
    RIGHT = 3


def align_text(text: str, alignment: TextAlignment, *, fill_char: str = ' ',
               width: Optional[int] = None, tab_width: int = 4, truncate: bool = False) -> str:
    """
    Align text for display within a given width. Supports characters with display widths greater than 1.
    ANSI style sequences do not count toward the display width. If text has line breaks, then each line is aligned
    independently.

    There are convenience wrappers around this function: align_left(), align_center(), and align_right()

    :param text: text to align (can contain multiple lines)
    :param alignment: how to align the text
    :param fill_char: character that fills the alignment gap. Defaults to space. (Cannot be a line breaking character)
    :param width: display width of the aligned text. Defaults to width of the terminal.
    :param tab_width: any tabs in the text will be replaced with this many spaces. if fill_char is a tab, then it will
                      be converted to one space.
    :param truncate: if True, then each line will be shortened to fit within the display width. The truncated
                     portions are replaced by a '…' character. Defaults to False.
    :return: aligned text
    :raises: TypeError if fill_char is more than one character (not including ANSI style sequences)
    :raises: ValueError if text or fill_char contains an unprintable character
    :raises: ValueError if width is less than 1
    """
    import io
    import shutil

    from . import ansi

    if width is None:
        width = shutil.get_terminal_size().columns

    if width < 1:
        raise ValueError("width must be at least 1")

    # Handle tabs
    text = text.replace('\t', ' ' * tab_width)
    fill_char = fill_char.replace('\t', ' ')

    if len(ansi.strip_style(fill_char)) != 1:
        raise TypeError("Fill character must be exactly one character long")

    fill_char_width = ansi.style_aware_wcswidth(fill_char)
    if fill_char_width == -1:
        raise (ValueError("Fill character is an unprintable character"))

    if text:
        lines = text.splitlines()
    else:
        lines = ['']

    text_buf = io.StringIO()

    # ANSI style sequences that may affect future lines will be cancelled by the fill_char's style.
    # To avoid this, we save the state of a line's style so we can restore it when beginning the next line.
    # This also allows the lines to be used independently and still have their style. TableCreator does this.
    aggregate_styles = ''

    # Save the ANSI style sequences in fill_char
    fill_char_styles = get_styles_in_text(fill_char)

    # Create a space with the same style as fill_char for cases in which
    # fill_char does not divide evenly into the gap.
    styled_space = ''
    char_index = 0
    while char_index < len(fill_char):
        if char_index in fill_char_styles:
            # Preserve this style in styled_space
            styled_space += fill_char_styles[char_index]
            char_index += len(fill_char_styles[char_index])
        else:
            # We've reached the visible fill_char. Replace it with a space.
            styled_space += ' '
            char_index += 1

    for index, line in enumerate(lines):
        if index > 0:
            text_buf.write('\n')

        if truncate:
            line = truncate_line(line, width)

        line_width = ansi.style_aware_wcswidth(line)
        if line_width == -1:
            raise(ValueError("Text to align contains an unprintable character"))

        # Get the styles in this line
        line_styles = get_styles_in_text(line)

        # Calculate how wide each side of filling needs to be
        if line_width >= width:
            # Don't return here even though the line needs no fill chars.
            # There may be styles sequences to restore.
            total_fill_width = 0
        else:
            total_fill_width = width - line_width

        if alignment == TextAlignment.LEFT:
            left_fill_width = 0
            right_fill_width = total_fill_width
        elif alignment == TextAlignment.CENTER:
            left_fill_width = total_fill_width // 2
            right_fill_width = total_fill_width - left_fill_width
        else:
            left_fill_width = total_fill_width
            right_fill_width = 0

        # Determine how many fill characters are needed to cover the width
        left_fill = (left_fill_width // fill_char_width) * fill_char
        right_fill = (right_fill_width // fill_char_width) * fill_char

        # In cases where the fill character display width didn't divide evenly into
        # the gap being filled, pad the remainder with styled_space.
        left_fill += styled_space * (left_fill_width - ansi.style_aware_wcswidth(left_fill))
        right_fill += styled_space * (right_fill_width - ansi.style_aware_wcswidth(right_fill))

        # Don't allow styles in fill_char and text to affect one another
        if fill_char_styles or aggregate_styles or line_styles:
            if left_fill:
                left_fill = ansi.RESET_ALL + left_fill
            left_fill += ansi.RESET_ALL

            if right_fill:
                right_fill = ansi.RESET_ALL + right_fill
            right_fill += ansi.RESET_ALL

        # Write the line and restore any styles from previous lines
        text_buf.write(left_fill + aggregate_styles + line + right_fill)

        # Update the aggregate with styles in this line
        aggregate_styles += ''.join(line_styles.values())

    return text_buf.getvalue()


def align_left(text: str, *, fill_char: str = ' ', width: Optional[int] = None,
               tab_width: int = 4, truncate: bool = False) -> str:
    """
    Left align text for display within a given width. Supports characters with display widths greater than 1.
    ANSI style sequences do not count toward the display width. If text has line breaks, then each line is aligned
    independently.

    :param text: text to left align (can contain multiple lines)
    :param fill_char: character that fills the alignment gap. Defaults to space. (Cannot be a line breaking character)
    :param width: display width of the aligned text. Defaults to width of the terminal.
    :param tab_width: any tabs in the text will be replaced with this many spaces. if fill_char is a tab, then it will
                      be converted to one space.
    :param truncate: if True, then text will be shortened to fit within the display width. The truncated portion is
                     replaced by a '…' character. Defaults to False.
    :return: left-aligned text
    :raises: TypeError if fill_char is more than one character (not including ANSI style sequences)
    :raises: ValueError if text or fill_char contains an unprintable character
    :raises: ValueError if width is less than 1
    """
    return align_text(text, TextAlignment.LEFT, fill_char=fill_char, width=width,
                      tab_width=tab_width, truncate=truncate)


def align_center(text: str, *, fill_char: str = ' ', width: Optional[int] = None,
                 tab_width: int = 4, truncate: bool = False) -> str:
    """
    Center text for display within a given width. Supports characters with display widths greater than 1.
    ANSI style sequences do not count toward the display width. If text has line breaks, then each line is aligned
    independently.

    :param text: text to center (can contain multiple lines)
    :param fill_char: character that fills the alignment gap. Defaults to space. (Cannot be a line breaking character)
    :param width: display width of the aligned text. Defaults to width of the terminal.
    :param tab_width: any tabs in the text will be replaced with this many spaces. if fill_char is a tab, then it will
                      be converted to one space.
    :param truncate: if True, then text will be shortened to fit within the display width. The truncated portion is
                     replaced by a '…' character. Defaults to False.
    :return: centered text
    :raises: TypeError if fill_char is more than one character (not including ANSI style sequences)
    :raises: ValueError if text or fill_char contains an unprintable character
    :raises: ValueError if width is less than 1
    """
    return align_text(text, TextAlignment.CENTER, fill_char=fill_char, width=width,
                      tab_width=tab_width, truncate=truncate)


def align_right(text: str, *, fill_char: str = ' ', width: Optional[int] = None,
                tab_width: int = 4, truncate: bool = False) -> str:
    """
    Right align text for display within a given width. Supports characters with display widths greater than 1.
    ANSI style sequences do not count toward the display width. If text has line breaks, then each line is aligned
    independently.

    :param text: text to right align (can contain multiple lines)
    :param fill_char: character that fills the alignment gap. Defaults to space. (Cannot be a line breaking character)
    :param width: display width of the aligned text. Defaults to width of the terminal.
    :param tab_width: any tabs in the text will be replaced with this many spaces. if fill_char is a tab, then it will
                      be converted to one space.
    :param truncate: if True, then text will be shortened to fit within the display width. The truncated portion is
                     replaced by a '…' character. Defaults to False.
    :return: right-aligned text
    :raises: TypeError if fill_char is more than one character (not including ANSI style sequences)
    :raises: ValueError if text or fill_char contains an unprintable character
    :raises: ValueError if width is less than 1
    """
    return align_text(text, TextAlignment.RIGHT, fill_char=fill_char, width=width,
                      tab_width=tab_width, truncate=truncate)


def truncate_line(line: str, max_width: int, *, tab_width: int = 4) -> str:
    """
    Truncate a single line to fit within a given display width. Any portion of the string that is truncated
    is replaced by a '…' character. Supports characters with display widths greater than 1. ANSI style sequences
    do not count toward the display width.

    If there are ANSI style sequences in the string after where truncation occurs, this function will append them
    to the returned string.

    This is done to prevent issues caused in cases like: truncate_string(fg.blue + hello + fg.reset, 3)
    In this case, "hello" would be truncated before fg.reset resets the color from blue. Appending the remaining style
    sequences makes sure the style is in the same state had the entire string been printed. align_text() relies on this
    behavior when preserving style over multiple lines.

    :param line: text to truncate
    :param max_width: the maximum display width the resulting string is allowed to have
    :param tab_width: any tabs in the text will be replaced with this many spaces
    :return: line that has a display width less than or equal to width
    :raises: ValueError if text contains an unprintable character like a newline
    :raises: ValueError if max_width is less than 1
    """
    import io
    from . import ansi

    # Handle tabs
    line = line.replace('\t', ' ' * tab_width)

    if ansi.style_aware_wcswidth(line) == -1:
        raise (ValueError("text contains an unprintable character"))

    if max_width < 1:
        raise ValueError("max_width must be at least 1")

    if ansi.style_aware_wcswidth(line) <= max_width:
        return line

    # Find all style sequences in the line
    styles = get_styles_in_text(line)

    # Add characters one by one and preserve all style sequences
    done = False
    index = 0
    total_width = 0
    truncated_buf = io.StringIO()

    while not done:
        # Check if a style sequence is at this index. These don't count toward display width.
        if index in styles:
            truncated_buf.write(styles[index])
            style_len = len(styles[index])
            styles.pop(index)
            index += style_len
            continue

        char = line[index]
        char_width = ansi.style_aware_wcswidth(char)

        # This char will make the text too wide, add the ellipsis instead
        if char_width + total_width >= max_width:
            char = constants.HORIZONTAL_ELLIPSIS
            char_width = ansi.style_aware_wcswidth(char)
            done = True

        total_width += char_width
        truncated_buf.write(char)
        index += 1

    # Append remaining style sequences from original string
    truncated_buf.write(''.join(styles.values()))

    return truncated_buf.getvalue()


def get_styles_in_text(text: str) -> Dict[int, str]:
    """
    Return an OrderedDict containing all ANSI style sequences found in a string

    The structure of the dictionary is:
        key: index where sequences begins
        value: ANSI style sequence found at index in text

    Keys are in ascending order

    :param text: text to search for style sequences
    """
    from . import ansi

    start = 0
    styles = collections.OrderedDict()

    while True:
        match = ansi.ANSI_STYLE_RE.search(text, start)
        if match is None:
            break
        styles[match.start()] = match.group()
        start += len(match.group())

    return styles


def categorize(func: Union[Callable, Iterable[Callable]], category: str) -> None:
    """Categorize a function.

    The help command output will group the passed function under the
    specified category heading

    :param func: function or list of functions to categorize
    :param category: category to put it in

    :Example:

    >>> import cmd2
    >>> class MyApp(cmd2.Cmd):
    >>>   def do_echo(self, arglist):
    >>>     self.poutput(' '.join(arglist)
    >>>
    >>>   cmd2.utils.categorize(do_echo, "Text Processing")

    For an alternative approach to categorizing commands using a decorator, see
    :func:`~cmd2.decorators.with_category`
    """
    if isinstance(func, Iterable):
        for item in func:
            setattr(item, constants.CMD_ATTR_HELP_CATEGORY, category)
    else:
        if inspect.ismethod(func):
            setattr(func.__func__, constants.CMD_ATTR_HELP_CATEGORY, category)
        else:
            setattr(func, constants.CMD_ATTR_HELP_CATEGORY, category)


def get_defining_class(meth) -> Type:
    """
    Attempts to resolve the class that defined a method.

    Inspired by implementation published here:
        https://stackoverflow.com/a/25959545/1956611

    TODO: Python 3.5.2 is unable to handle the type hints Callable and Optional[Type].
          Restore proper type hints after we drop 3.5.2 support

    :param meth: method to inspect
    :type meth: Callable
    :return: class type in which the supplied method was defined. None if it couldn't be resolved.
    :rtype: Optional[Type]
    """
    if isinstance(meth, functools.partial):
        return get_defining_class(meth.func)
    if inspect.ismethod(meth) or (inspect.isbuiltin(meth)
                                  and getattr(meth, '__self__') is not None
                                  and getattr(meth.__self__, '__class__')):
        for cls in inspect.getmro(meth.__self__.__class__):
            if meth.__name__ in cls.__dict__:
                return cls
        meth = getattr(meth, '__func__', meth)  # fallback to __qualname__ parsing
    if inspect.isfunction(meth):
        cls = getattr(inspect.getmodule(meth),
                      meth.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0])
        if isinstance(cls, type):
            return cls
    return getattr(meth, '__objclass__', None)  # handle special descriptor objects
