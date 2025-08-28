"""Shared utility functions."""

import argparse
import collections
import contextlib
import functools
import glob
import inspect
import itertools
import os
import re
import subprocess
import sys
import threading
from collections.abc import (
    Callable,
    Iterable,
)
from difflib import SequenceMatcher
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    TextIO,
    TypeVar,
    Union,
    cast,
)

from . import constants
from . import string_utils as su
from .argparse_custom import (
    ChoicesProviderFunc,
    CompleterFunc,
)

if TYPE_CHECKING:  # pragma: no cover
    import cmd2  # noqa: F401

    PopenTextIO = subprocess.Popen[str]
else:
    PopenTextIO = subprocess.Popen

_T = TypeVar('_T')


def to_bool(val: Any) -> bool:
    """Convert anything to a boolean based on its value.

    Strings like "True", "true", "False", and "false" return True, True, False, and False
    respectively. All other values are converted using bool()

    :param val: value being converted
    :return: boolean value expressed in the passed in value
    :raises ValueError: if the string does not contain a value corresponding to a boolean value
    """
    if isinstance(val, str):
        if val.capitalize() == str(True):
            return True
        if val.capitalize() == str(False):
            return False
        raise ValueError("must be True or False (case-insensitive)")
    if isinstance(val, bool):
        return val
    return bool(val)


class Settable:
    """Used to configure an attribute to be settable via the set command in the CLI."""

    def __init__(
        self,
        name: str,
        val_type: type[Any] | Callable[[Any], Any],
        description: str,
        settable_object: object,
        *,
        settable_attrib_name: str | None = None,
        onchange_cb: Callable[[str, _T, _T], Any] | None = None,
        choices: Iterable[Any] | None = None,
        choices_provider: ChoicesProviderFunc | None = None,
        completer: CompleterFunc | None = None,
    ) -> None:
        """Settable Initializer.

        :param name: The user-facing name for this setting in the CLI.
        :param val_type: A callable used to cast the string value from the CLI into its
                         proper type and validate it. This function should raise an
                         exception (like ValueError or TypeError) if the conversion or
                         validation fails, which will be caught and displayed to the user
                         by the set command. For example, setting this to int ensures the
                         input is a valid integer. Specifying bool automatically provides
                         tab completion for 'true' and 'false' and uses a built-in function
                         for conversion and validation.
        :param description: A concise string that describes the purpose of this setting.
        :param settable_object: The object that owns the attribute being made settable (e.g. self).
        :param settable_attrib_name: The name of the attribute on the settable_object that
                                     will be modified. This defaults to the value of the name
                                     parameter if not specified.
        :param onchange_cb: An optional function or method to call when the value of this
                            setting is altered by the set command. The callback is invoked
                            only if the new value is different from the old one.

                            It receives three arguments:
                                param_name: str - name of the parameter
                                old_value: Any - the parameter's old value
                                new_value: Any - the parameter's new value

        The following optional settings provide tab completion for a parameter's values.
        They correspond to the same settings in argparse-based tab completion. A maximum
        of one of these should be provided.

        :param choices: iterable of accepted values
        :param choices_provider: function that provides choices for this argument
        :param completer: tab completion function that provides choices for this argument
        """
        if val_type is bool:

            def get_bool_choices(_: str) -> list[str]:
                """Tab complete lowercase boolean values."""
                return ['true', 'false']

            val_type = to_bool
            choices_provider = cast(ChoicesProviderFunc, get_bool_choices)

        self.name = name
        self.val_type = val_type
        self.description = description
        self.settable_obj = settable_object
        self.settable_attrib_name = settable_attrib_name if settable_attrib_name is not None else name
        self.onchange_cb = onchange_cb
        self.choices = choices
        self.choices_provider = choices_provider
        self.completer = completer

    @property
    def value(self) -> Any:
        """Get the value of the settable attribute."""
        return getattr(self.settable_obj, self.settable_attrib_name)

    @value.setter
    def value(self, value: Any) -> None:
        """Set the settable attribute on the specified destination object.

        :param value: new value to set
        """
        # Run the value through its type function to handle any conversion or validation
        new_value = self.val_type(value)

        # Make sure new_value is a valid choice
        if self.choices is not None and new_value not in self.choices:
            choices_str = ', '.join(map(repr, self.choices))
            raise ValueError(f"invalid choice: {new_value!r} (choose from {choices_str})")

        # Try to update the settable's value
        orig_value = self.value
        setattr(self.settable_obj, self.settable_attrib_name, new_value)

        # Check if we need to call an onchange callback
        if orig_value != new_value and self.onchange_cb:
            self.onchange_cb(self.name, orig_value, new_value)


def is_text_file(file_path: str) -> bool:
    """Return if a file contains only ASCII or UTF-8 encoded text and isn't empty.

    :param file_path: path to the file being checked
    :return: True if the file is a non-empty text file, otherwise False
    :raises OSError: if file can't be read
    """
    expanded_path = os.path.abspath(os.path.expanduser(file_path.strip()))
    valid_text_file = False

    # Only need to check for utf-8 compliance since that covers ASCII, too
    try:
        with open(expanded_path, encoding='utf-8', errors='strict') as f:
            # Make sure the file has only utf-8 text and is not empty
            if sum(1 for _ in f) > 0:
                valid_text_file = True
    except OSError:
        raise
    except UnicodeDecodeError:
        # Not UTF-8
        pass

    return valid_text_file


def remove_duplicates(list_to_prune: list[_T]) -> list[_T]:
    """Remove duplicates from a list while preserving order of the items.

    :param list_to_prune: the list being pruned of duplicates
    :return: The pruned list
    """
    temp_dict: collections.OrderedDict[_T, Any] = collections.OrderedDict()
    for item in list_to_prune:
        temp_dict[item] = None

    return list(temp_dict.keys())


def alphabetical_sort(list_to_sort: Iterable[str]) -> list[str]:
    """Sorts a list of strings alphabetically.

    For example: ['a1', 'A11', 'A2', 'a22', 'a3']

    To sort a list in place, don't call this method, which makes a copy. Instead, do this:

    my_list.sort(key=norm_fold)

    :param list_to_sort: the list being sorted
    :return: the sorted list
    """
    return sorted(list_to_sort, key=su.norm_fold)


def try_int_or_force_to_lower_case(input_str: str) -> int | str:
    """Try to convert the passed-in string to an integer. If that fails, it converts it to lower case using norm_fold.

    :param input_str: string to convert
    :return: the string as an integer or a lower case version of the string.
    """
    try:
        return int(input_str)
    except ValueError:
        return su.norm_fold(input_str)


def natural_keys(input_str: str) -> list[int | str]:
    """Convert a string into a list of integers and strings to support natural sorting (see natural_sort).

    For example: natural_keys('abc123def') -> ['abc', '123', 'def']
    :param input_str: string to convert
    :return: list of strings and integers
    """
    return [try_int_or_force_to_lower_case(substr) for substr in re.split(r'(\d+)', input_str)]


def natural_sort(list_to_sort: Iterable[str]) -> list[str]:
    """Sorts a list of strings case insensitively as well as numerically.

    For example: ['a1', 'A2', 'a3', 'A11', 'a22']

    To sort a list in place, don't call this method, which makes a copy. Instead, do this:

    my_list.sort(key=natural_keys)

    :param list_to_sort: the list being sorted
    :return: the list sorted naturally
    """
    return sorted(list_to_sort, key=natural_keys)


def quote_specific_tokens(tokens: list[str], tokens_to_quote: list[str]) -> None:
    """Quote specific tokens in a list.

    :param tokens: token list being edited
    :param tokens_to_quote: the tokens, which if present in tokens, to quote
    """
    for i, token in enumerate(tokens):
        if token in tokens_to_quote:
            tokens[i] = su.quote(token)


def unquote_specific_tokens(tokens: list[str], tokens_to_unquote: list[str]) -> None:
    """Unquote specific tokens in a list.

    :param tokens: token list being edited
    :param tokens_to_unquote: the tokens, which if present in tokens, to unquote
    """
    for i, token in enumerate(tokens):
        unquoted_token = su.strip_quotes(token)
        if unquoted_token in tokens_to_unquote:
            tokens[i] = unquoted_token


def expand_user(token: str) -> str:
    """Wrap os.expanduser() to support expanding ~ in quoted strings.

    :param token: the string to expand
    """
    if token:
        if su.is_quoted(token):
            quote_char = token[0]
            token = su.strip_quotes(token)
        else:
            quote_char = ''

        token = os.path.expanduser(token)

        # Restore the quotes even if not needed to preserve what the user typed
        if quote_char:
            token = quote_char + token + quote_char

    return token


def expand_user_in_tokens(tokens: list[str]) -> None:
    """Call expand_user() on all tokens in a list of strings.

    :param tokens: tokens to expand.
    """
    for index, _ in enumerate(tokens):
        tokens[index] = expand_user(tokens[index])


def find_editor() -> str | None:
    """Set cmd2.Cmd.DEFAULT_EDITOR. If EDITOR env variable is set, that will be used.

    Otherwise the function will look for a known editor in directories specified by PATH env variable.
    :return: Default editor or None.
    """
    editor = os.environ.get('EDITOR')
    if not editor:
        if sys.platform[:3] == 'win':
            editors = ['edit', 'code.cmd', 'notepad++.exe', 'notepad.exe']
        else:
            editors = ['vim', 'vi', 'emacs', 'nano', 'pico', 'joe', 'code', 'subl', 'gedit', 'kate']

        # Get a list of every directory in the PATH environment variable and ignore symbolic links
        env_path = os.getenv('PATH')
        paths = [] if env_path is None else [p for p in env_path.split(os.path.pathsep) if not os.path.islink(p)]

        for possible_editor, path in itertools.product(editors, paths):
            editor_path = os.path.join(path, possible_editor)
            if os.path.isfile(editor_path) and os.access(editor_path, os.X_OK):
                if sys.platform[:3] == 'win':
                    # Remove extension from Windows file names
                    editor = os.path.splitext(possible_editor)[0]
                else:
                    editor = possible_editor
                break
        else:
            editor = None

    return editor


def files_from_glob_pattern(pattern: str, access: int = os.F_OK) -> list[str]:
    """Return a list of file paths based on a glob pattern.

    Only files are returned, not directories, and optionally only files for which the user has a specified access to.

    :param pattern: file name or glob pattern
    :param access: file access type to verify (os.* where * is F_OK, R_OK, W_OK, or X_OK)
    :return: list of files matching the name or glob pattern
    """
    return [f for f in glob.glob(pattern) if os.path.isfile(f) and os.access(f, access)]


def files_from_glob_patterns(patterns: list[str], access: int = os.F_OK) -> list[str]:
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


def get_exes_in_path(starts_with: str) -> list[str]:
    """Return names of executables in a user's path.

    :param starts_with: what the exes should start with. leave blank for all exes in path.
    :return: a list of matching exe names
    """
    # Purposely don't match any executable containing wildcards
    wildcards = ['*', '?']
    for wildcard in wildcards:
        if wildcard in starts_with:
            return []

    # Get a list of every directory in the PATH environment variable and ignore symbolic links
    env_path = os.getenv('PATH')
    paths = [] if env_path is None else [p for p in env_path.split(os.path.pathsep) if not os.path.islink(p)]

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
    """Class to simulate behavior of sys.stdout or sys.stderr.

    Stores contents in internal buffer and optionally echos to the inner stream it is simulating.
    """

    def __init__(
        self,
        inner_stream: Union[TextIO, 'StdSim'],
        *,
        echo: bool = False,
        encoding: str = 'utf-8',
        errors: str = 'replace',
    ) -> None:
        """StdSim Initializer.

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
        """Add str to internal bytes buffer and if echo is True, echo contents to inner stream.

        :param s: String to write to the stream
        """
        if not isinstance(s, str):
            raise TypeError(f'write() argument must be str, not {type(s)}')

        if not self.pause_storage:
            self.buffer.byte_buf += s.encode(encoding=self.encoding, errors=self.errors)
        if self.echo:
            self.inner_stream.write(s)

    def getvalue(self) -> str:
        """Get the internal contents as a str."""
        return self.buffer.byte_buf.decode(encoding=self.encoding, errors=self.errors)

    def getbytes(self) -> bytes:
        """Get the internal contents as bytes."""
        return bytes(self.buffer.byte_buf)

    def read(self, size: int | None = -1) -> str:
        """Read from the internal contents as a str and then clear them out.

        :param size: Number of bytes to read from the stream
        """
        if size is None or size == -1:
            result = self.getvalue()
            self.clear()
        else:
            result = self.buffer.byte_buf[:size].decode(encoding=self.encoding, errors=self.errors)
            self.buffer.byte_buf = self.buffer.byte_buf[size:]

        return result

    def readbytes(self) -> bytes:
        """Read from the internal contents as bytes and then clear them out."""
        result = self.getbytes()
        self.clear()
        return result

    def clear(self) -> None:
        """Clear the internal contents."""
        self.buffer.byte_buf.clear()

    def isatty(self) -> bool:
        """StdSim only considered an interactive stream if `echo` is True and `inner_stream` is a tty."""
        if self.echo:
            return self.inner_stream.isatty()
        return False

    @property
    def line_buffering(self) -> bool:
        """Handle when the inner stream doesn't have a line_buffering attribute.

        Which is the case when running unit tests because pytest sets stdout to a pytest EncodedFile object.
        """
        try:
            return bool(self.inner_stream.line_buffering)
        except AttributeError:
            return False

    def __getattr__(self, item: str) -> Any:
        """When an attribute lookup fails to find the attribute in the usual places, this special method is called."""
        if item in self.__dict__:
            return self.__dict__[item]
        return getattr(self.inner_stream, item)


class ByteBuf:
    """Used by StdSim to write binary data and stores the actual bytes written."""

    # Used to know when to flush the StdSim
    NEWLINES = (b'\n', b'\r')

    def __init__(self, std_sim_instance: StdSim) -> None:
        """Initialize the ByteBuf instance."""
        self.byte_buf = bytearray()
        self.std_sim_instance = std_sim_instance

    def write(self, b: bytes) -> None:
        """Add bytes to internal bytes buffer and if echo is True, echo contents to inner stream."""
        if not isinstance(b, bytes):
            raise TypeError(f'a bytes-like object is required, not {type(b)}')
        if not self.std_sim_instance.pause_storage:
            self.byte_buf += b
        if self.std_sim_instance.echo:
            self.std_sim_instance.inner_stream.buffer.write(b)

            # Since StdSim wraps TextIO streams, we will flush the stream if line buffering is on
            # and the bytes being written contain a new line character. This is helpful when StdSim
            # is being used to capture output of a shell command because it causes the output to print
            # to the screen more often than if we waited for the stream to flush its buffer.
            if self.std_sim_instance.line_buffering and any(newline in b for newline in ByteBuf.NEWLINES):
                self.std_sim_instance.flush()


class ProcReader:
    """Used to capture stdout and stderr from a Popen process if any of those were set to subprocess.PIPE.

    If neither are pipes, then the process will run normally and no output will be captured.
    """

    def __init__(self, proc: PopenTextIO, stdout: StdSim | TextIO, stderr: StdSim | TextIO) -> None:
        """ProcReader initializer.

        :param proc: the Popen process being read from
        :param stdout: the stream to write captured stdout
        :param stderr: the stream to write captured stderr.
        """
        self._proc = proc
        self._stdout = stdout
        self._stderr = stderr

        self._out_thread = threading.Thread(name='out_thread', target=self._reader_thread_func, kwargs={'read_stdout': True})

        self._err_thread = threading.Thread(name='err_thread', target=self._reader_thread_func, kwargs={'read_stdout': False})

        # Start the reader threads for pipes only
        if self._proc.stdout is not None:
            self._out_thread.start()
        if self._proc.stderr is not None:
            self._err_thread.start()

    def send_sigint(self) -> None:
        """Send a SIGINT to the process similar to if <Ctrl>+C were pressed."""
        import signal

        if sys.platform.startswith('win'):
            # cmd2 started the Windows process in a new process group. Therefore we must send
            # a CTRL_BREAK_EVENT since CTRL_C_EVENT signals cannot be generated for process groups.
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
        """Terminate the process."""
        self._proc.terminate()

    def wait(self) -> None:
        """Wait for the process to finish."""
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
        """Thread function that reads a stream from the process.

        :param read_stdout: if True, then this thread deals with stdout. Otherwise it deals with stderr.
        """
        if read_stdout:
            read_stream = self._proc.stdout
            write_stream = self._stdout
        else:
            read_stream = self._proc.stderr
            write_stream = self._stderr

        # The thread should have been started only if this stream was a pipe
        if read_stream is None:
            raise ValueError("read_stream is None")

        # Run until process completes
        while self._proc.poll() is None:
            available = read_stream.peek()  # type: ignore[attr-defined]
            if available:
                read_stream.read(len(available))
                self._write_bytes(write_stream, available)

    @staticmethod
    def _write_bytes(stream: StdSim | TextIO, to_write: bytes | str) -> None:
        """Write bytes to a stream.

        :param stream: the stream being written to
        :param to_write: the bytes being written.
        """
        if isinstance(to_write, str):
            to_write = to_write.encode()

        # BrokenPipeError can occur if output is being piped to a process that closed
        with contextlib.suppress(BrokenPipeError):
            stream.buffer.write(to_write)


class ContextFlag:
    """A context manager which is also used as a boolean flag value within the default sigint handler.

    Its main use is as a flag to prevent the SIGINT handler in cmd2 from raising a KeyboardInterrupt
    while a critical code section has set the flag to True. Because signal handling is always done on the
    main thread, this class is not thread-safe since there is no need.
    """

    def __init__(self) -> None:
        """When this flag has a positive value, it is considered set. When it is 0, it is not set.

        It should never go below 0.
        """
        self.__count = 0

    def __bool__(self) -> bool:
        """Define the truth value of an object when it is used in a boolean context."""
        return self.__count > 0

    def __enter__(self) -> None:
        """When a with block is entered, the __enter__ method of the context manager is called."""
        self.__count += 1

    def __exit__(self, *args: object) -> None:
        """When the execution flow exits a with statement block this is called, regardless of whether an exception occurred."""
        self.__count -= 1
        if self.__count < 0:
            raise ValueError("count has gone below 0")


class RedirectionSavedState:
    """Created by each command to store information required to restore state after redirection."""

    def __init__(
        self,
        self_stdout: StdSim | TextIO,
        stdouts_match: bool,
        pipe_proc_reader: ProcReader | None,
        saved_redirecting: bool,
    ) -> None:
        """RedirectionSavedState initializer.

        :param self_stdout: saved value of Cmd.stdout
        :param stdouts_match: True if Cmd.stdout is equal to sys.stdout
        :param pipe_proc_reader: saved value of Cmd._cur_pipe_proc_reader
        :param saved_redirecting: saved value of Cmd._redirecting.
        """
        # Tells if command is redirecting
        self.redirecting = False

        # Used to restore stdout values after redirection ends
        self.saved_self_stdout = self_stdout
        self.stdouts_match = stdouts_match

        # Used to restore values after command ends regardless of whether the command redirected
        self.saved_pipe_proc_reader = pipe_proc_reader
        self.saved_redirecting = saved_redirecting


def categorize(func: Callable[..., Any] | Iterable[Callable[..., Any]], category: str) -> None:
    """Categorize a function.

    The help command output will group the passed function under the
    specified category heading

    :param func: function or list of functions to categorize
    :param category: category to put it in

    Example:
    ```py
    import cmd2
    class MyApp(cmd2.Cmd):
      def do_echo(self, arglist):
        self.poutput(' '.join(arglist)

      cmd2.utils.categorize(do_echo, "Text Processing")
    ```

    For an alternative approach to categorizing commands using a decorator, see [cmd2.decorators.with_category][]

    """
    if isinstance(func, Iterable):
        for item in func:
            setattr(item, constants.CMD_ATTR_HELP_CATEGORY, category)
    elif inspect.ismethod(func):
        setattr(func.__func__, constants.CMD_ATTR_HELP_CATEGORY, category)
    else:
        setattr(func, constants.CMD_ATTR_HELP_CATEGORY, category)


def get_defining_class(meth: Callable[..., Any]) -> type[Any] | None:
    """Attempt to resolve the class that defined a method.

    Inspired by implementation published here:
        https://stackoverflow.com/a/25959545/1956611

    :param meth: method to inspect
    :return: class type in which the supplied method was defined. None if it couldn't be resolved.
    """
    if isinstance(meth, functools.partial):
        return get_defining_class(meth.func)
    if inspect.ismethod(meth) or (
        inspect.isbuiltin(meth) and hasattr(meth, '__self__') and hasattr(meth.__self__, '__class__')
    ):
        for cls in inspect.getmro(meth.__self__.__class__):
            if meth.__name__ in cls.__dict__:
                return cls
        meth = getattr(meth, '__func__', meth)  # fallback to __qualname__ parsing
    if inspect.isfunction(meth):
        cls = getattr(inspect.getmodule(meth), meth.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0])
        if isinstance(cls, type):
            return cls
    return cast(type, getattr(meth, '__objclass__', None))  # handle special descriptor objects


class CompletionMode(Enum):
    """Enum for what type of tab completion to perform in cmd2.Cmd.read_input()."""

    # Tab completion will be disabled during read_input() call
    # Use of custom up-arrow history supported
    NONE = 1

    # read_input() will tab complete cmd2 commands and their arguments
    # cmd2's command line history will be used for up arrow if history is not provided.
    # Otherwise use of custom up-arrow history supported.
    COMMANDS = 2

    # read_input() will tab complete based on one of its following parameters:
    #     choices, choices_provider, completer, parser
    # Use of custom up-arrow history supported
    CUSTOM = 3


class CustomCompletionSettings:
    """Used by cmd2.Cmd.complete() to tab complete strings other than command arguments."""

    def __init__(self, parser: argparse.ArgumentParser, *, preserve_quotes: bool = False) -> None:
        """CustomCompletionSettings initializer.

        :param parser: arg parser defining format of string being tab completed
        :param preserve_quotes: if True, then quoted tokens will keep their quotes when processed by
                                ArgparseCompleter. This is helpful in cases when you're tab completing
                                flag-like tokens (e.g. -o, --option) and you don't want them to be
                                treated as argparse flags when quoted. Set this to True if you plan
                                on passing the string to argparse with the tokens still quoted.
        """
        self.parser = parser
        self.preserve_quotes = preserve_quotes


def strip_doc_annotations(doc: str) -> str:
    """Strip annotations from a docstring leaving only the text description.

    :param doc: documentation string
    """
    # Attempt to locate the first documentation block
    cmd_desc = ''
    found_first = False
    for doc_line in doc.splitlines():
        stripped_line = doc_line.strip()

        # Don't include :param type lines
        if stripped_line.startswith(':'):
            if found_first:
                break
        elif stripped_line:
            if found_first:
                cmd_desc += "\n"
            cmd_desc += stripped_line
            found_first = True
        elif found_first:
            break
    return cmd_desc


def similarity_function(s1: str, s2: str) -> float:
    """Ratio from s1,s2 may be different to s2,s1. We keep the max.

    See https://docs.python.org/3/library/difflib.html#difflib.SequenceMatcher.ratio
    """
    return max(SequenceMatcher(None, s1, s2).ratio(), SequenceMatcher(None, s2, s1).ratio())


MIN_SIMIL_TO_CONSIDER = 0.7


def suggest_similar(
    requested_command: str, options: Iterable[str], similarity_function_to_use: Callable[[str, str], float] | None = None
) -> str | None:
    """Given a requested command and an iterable of possible options returns the most similar (if any is similar).

    :param requested_command: The command entered by the user
    :param options: The list of available commands to search for the most similar
    :param similarity_function_to_use: An optional callable to use to compare commands
    :return: The most similar command or None if no one is similar
    """
    proposed_command = None
    best_simil = MIN_SIMIL_TO_CONSIDER
    requested_command_to_compare = requested_command.lower()
    similarity_function_to_use = similarity_function_to_use or similarity_function
    for each in options:
        simil = similarity_function_to_use(each.lower(), requested_command_to_compare)
        if best_simil < simil:
            best_simil = simil
            proposed_command = each
    return proposed_command


def get_types(func_or_method: Callable[..., Any]) -> tuple[dict[str, Any], Any]:
    """Use inspect.get_annotations() to extract type hints for parameters and return value.

    This is a thin convenience wrapper around inspect.get_annotations() that treats the return value
    annotation separately.

    :param func_or_method: Function or method to return the type hints for
    :return: tuple with first element being dictionary mapping param names to type hints
            and second element being the return type hint or None if there is no return value type hint
    :raises ValueError: if the `func_or_method` argument is not a valid object to pass to `inspect.get_annotations`
    """
    try:
        type_hints = inspect.get_annotations(func_or_method, eval_str=True)  # Get dictionary of type hints
    except TypeError as exc:
        raise ValueError("Argument passed to get_types should be a function or method") from exc
    ret_ann = type_hints.pop('return', None)  # Pop off the return annotation if it exists
    if inspect.ismethod(func_or_method):
        type_hints.pop('self', None)  # Pop off `self` hint for methods
    return type_hints, ret_ann
