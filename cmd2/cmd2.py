#!/usr/bin/env python
# coding=utf-8
"""Variant on standard library's cmd with extra features.

To use, simply import cmd2.Cmd instead of cmd.Cmd; use precisely as though you
were using the standard library's cmd, while enjoying the extra features.

Searchable command history (commands: "history")
Load commands from file, save to file, edit commands in file
Multi-line commands
Special-character shortcut commands (beyond cmd's "@" and "!")
Settable environment parameters
Parsing commands with `argparse` argument parsers (flags)
Redirection to file with >, >>; input from file with <
Easy transcript-based testing of applications (see examples/example.py)
Bash-style ``select`` available

Note that redirection with > and | will only work if `self.poutput()`
is used in place of `print`.

- Catherine Devlin, Jan 03 2008 - catherinedevlin.blogspot.com

Git repository on GitHub at https://github.com/python-cmd2/cmd2
"""
# This module has many imports, quite a few of which are only
# infrequently utilized. To reduce the initial overhead of
# import this module, many of these imports are lazy-loaded
# i.e. we only import the module when we use it
# For example, we don't import the 'traceback' module
# until the perror() function is called and the debug
# setting is True
import argparse
import cmd
import collections
import colorama
from colorama import Fore
import glob
import inspect
import os
import re
import shlex
import sys
import threading
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Type, Union, IO

from . import constants
from . import utils
from . import plugin
from .argparse_completer import AutoCompleter, ACArgumentParser, ACTION_ARG_CHOICES
from .clipboard import can_clip, get_paste_buffer, write_to_paste_buffer
from .parsing import StatementParser, Statement, Macro, MacroArg

# Set up readline
from .rl_utils import rl_type, RlType, rl_get_point, rl_set_prompt, vt100_support, rl_make_safe_prompt
if rl_type == RlType.NONE:  # pragma: no cover
    rl_warning = "Readline features including tab completion have been disabled since no \n" \
                 "supported version of readline was found. To resolve this, install \n" \
                 "pyreadline on Windows or gnureadline on Mac.\n\n"
    sys.stderr.write(Fore.LIGHTYELLOW_EX + rl_warning + Fore.RESET)
else:
    from .rl_utils import rl_force_redisplay, readline

    # Used by rlcompleter in Python console loaded by py command
    orig_rl_delims = readline.get_completer_delims()

    if rl_type == RlType.PYREADLINE:

        # Save the original pyreadline display completion function since we need to override it and restore it
        # noinspection PyProtectedMember
        orig_pyreadline_display = readline.rl.mode._display_completions

    elif rl_type == RlType.GNU:

        # We need wcswidth to calculate display width of tab completions
        from wcwidth import wcswidth

        # Get the readline lib so we can make changes to it
        import ctypes
        from .rl_utils import readline_lib

        rl_basic_quote_characters = ctypes.c_char_p.in_dll(readline_lib, "rl_basic_quote_characters")
        orig_rl_basic_quotes = ctypes.cast(rl_basic_quote_characters, ctypes.c_void_p).value

# Collection is a container that is sizable and iterable
# It was introduced in Python 3.6. We will try to import it, otherwise use our implementation
try:
    from collections.abc import Collection, Iterable
except ImportError:
    from collections.abc import Sized, Iterable, Container

    # noinspection PyAbstractClass
    class Collection(Sized, Iterable, Container):

        __slots__ = ()

        # noinspection PyPep8Naming
        @classmethod
        def __subclasshook__(cls, C):
            if cls is Collection:
                if any("__len__" in B.__dict__ for B in C.__mro__) and \
                        any("__iter__" in B.__dict__ for B in C.__mro__) and \
                        any("__contains__" in B.__dict__ for B in C.__mro__):
                    return True
            return NotImplemented

# Python 3.4 require contextlib2 for temporarily redirecting stderr and stdout
if sys.version_info < (3, 5):
    from contextlib2 import redirect_stdout
else:
    from contextlib import redirect_stdout

# Detect whether IPython is installed to determine if the built-in "ipy" command should be included
ipython_available = True
try:
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    from IPython import embed
except ImportError:  # pragma: no cover
    ipython_available = False


# optional attribute, when tagged on a function, allows cmd2 to categorize commands
HELP_CATEGORY = 'help_category'

INTERNAL_COMMAND_EPILOG = ("Notes:\n"
                           "  This command is for internal use and is not intended to be called from the\n"
                           "  command line.")

# All command functions start with this
COMMAND_FUNC_PREFIX = 'do_'

# All help functions start with this
HELP_FUNC_PREFIX = 'help_'


def categorize(func: Union[Callable, Iterable], category: str) -> None:
    """Categorize a function.

    The help command output will group this function under the specified category heading

    :param func: function to categorize
    :param category: category to put it in
    """
    if isinstance(func, Iterable):
        for item in func:
            setattr(item, HELP_CATEGORY, category)
    else:
        setattr(func, HELP_CATEGORY, category)


def parse_quoted_string(string: str, preserve_quotes: bool) -> List[str]:
    """
    Parse a quoted string into a list of arguments
    :param string: the string being parsed
    :param preserve_quotes: if True, then quotes will not be stripped
    """
    if isinstance(string, list):
        # arguments are already a list, return the list we were passed
        lexed_arglist = string
    else:
        # Use shlex to split the command line into a list of arguments based on shell rules
        lexed_arglist = shlex.split(string, posix=False)

        if not preserve_quotes:
            lexed_arglist = [utils.strip_quotes(arg) for arg in lexed_arglist]
    return lexed_arglist


def with_category(category: str) -> Callable:
    """A decorator to apply a category to a command function."""
    def cat_decorator(func):
        categorize(func, category)
        return func
    return cat_decorator


def with_argument_list(func: Callable, preserve_quotes: bool=False) -> Callable:
    """A decorator to alter the arguments passed to a do_* cmd2
    method. Default passes a string of whatever the user typed.
    With this decorator, the decorated method will receive a list
    of arguments parsed from user input using shlex.split()."""
    import functools

    @functools.wraps(func)
    def cmd_wrapper(self, cmdline):
        lexed_arglist = parse_quoted_string(cmdline, preserve_quotes)
        return func(self, lexed_arglist)

    cmd_wrapper.__doc__ = func.__doc__
    return cmd_wrapper


def with_argparser_and_unknown_args(argparser: argparse.ArgumentParser, preserve_quotes: bool=False) -> Callable:
    """A decorator to alter a cmd2 method to populate its ``args`` argument by parsing arguments with the given
    instance of argparse.ArgumentParser, but also returning unknown args as a list.

    :param argparser: given instance of ArgumentParser
    :param preserve_quotes: if True, then the arguments passed to arparse be maintain their quotes
    :return: function that gets passed parsed args and a list of unknown args
    """
    import functools

    # noinspection PyProtectedMember
    def arg_decorator(func: Callable):
        @functools.wraps(func)
        def cmd_wrapper(instance, cmdline):
            lexed_arglist = parse_quoted_string(cmdline, preserve_quotes)
            try:
                args, unknown = argparser.parse_known_args(lexed_arglist)
            except SystemExit:
                return
            else:
                return func(instance, args, unknown)

        # argparser defaults the program name to sys.argv[0]
        # we want it to be the name of our command
        argparser.prog = func.__name__[len(COMMAND_FUNC_PREFIX):]

        # If the description has not been set, then use the method docstring if one exists
        if argparser.description is None and func.__doc__:
            argparser.description = func.__doc__

        # If argparser.description is None, this will show under 'Undocumented commands'
        cmd_wrapper.__doc__ = argparser.description

        # Mark this function as having an argparse ArgumentParser
        setattr(cmd_wrapper, 'argparser', argparser)

        return cmd_wrapper

    return arg_decorator


def with_argparser(argparser: argparse.ArgumentParser, preserve_quotes: bool=False) -> Callable:
    """A decorator to alter a cmd2 method to populate its ``args`` argument by parsing arguments
    with the given instance of argparse.ArgumentParser.

    :param argparser: given instance of ArgumentParser
    :param preserve_quotes: if True, then the arguments passed to arparse be maintain their quotes
    :return: function that gets passed parsed args
    """
    import functools

    # noinspection PyProtectedMember
    def arg_decorator(func: Callable):
        @functools.wraps(func)
        def cmd_wrapper(instance, cmdline):
            lexed_arglist = parse_quoted_string(cmdline, preserve_quotes)
            try:
                args = argparser.parse_args(lexed_arglist)
            except SystemExit:
                return
            else:
                return func(instance, args)

        # argparser defaults the program name to sys.argv[0]
        # we want it to be the name of our command
        argparser.prog = func.__name__[len(COMMAND_FUNC_PREFIX):]

        # If the description has not been set, then use the method docstring if one exists
        if argparser.description is None and func.__doc__:
            argparser.description = func.__doc__

        # If argparser.description is None, this will show under 'Undocumented commands'
        cmd_wrapper.__doc__ = argparser.description

        # Mark this function as having an argparse ArgumentParser
        setattr(cmd_wrapper, 'argparser', argparser)

        return cmd_wrapper

    return arg_decorator


class EmbeddedConsoleExit(SystemExit):
    """Custom exception class for use with the py command."""
    pass


class EmptyStatement(Exception):
    """Custom exception class for handling behavior when the user just presses <Enter>."""
    pass


class HistoryItem(str):
    """Class used to represent an item in the History list.

    Thin wrapper around str class which adds a custom format for printing. It
    also keeps track of its index in the list as well as a lowercase
    representation of itself for convenience/efficiency.

    """
    listformat = '-------------------------[{}]\n{}\n'

    # noinspection PyUnusedLocal
    def __init__(self, instr: str) -> None:
        str.__init__(self)
        self.lowercase = self.lower()
        self.idx = None

    def pr(self) -> str:
        """Represent a HistoryItem in a pretty fashion suitable for printing.

        :return: pretty print string version of a HistoryItem
        """
        return self.listformat.format(self.idx, str(self).rstrip())


class Cmd(cmd.Cmd):
    """An easy but powerful framework for writing line-oriented command interpreters.

    Extends the Python Standard Library’s cmd package by adding a lot of useful features
    to the out of the box configuration.

    Line-oriented command interpreters are often useful for test harnesses, internal tools, and rapid prototypes.
    """
    # Attributes used to configure the StatementParser, best not to change these at runtime
    multiline_commands = []
    shortcuts = {'?': 'help', '!': 'shell', '@': 'load', '@@': '_relative_load'}
    terminators = [';']

    # Attributes which are NOT dynamically settable at runtime
    allow_cli_args = True       # Should arguments passed on the command-line be processed as commands?
    allow_redirection = True    # Should output redirection and pipes be allowed
    default_to_shell = False    # Attempt to run unrecognized commands as shell commands
    quit_on_sigint = False      # Quit the loop on interrupt instead of just resetting prompt
    reserved_words = []

    # Attributes which ARE dynamically settable at runtime
    colors = constants.COLORS_TERMINAL
    continuation_prompt = '> '
    debug = False
    echo = False
    editor = os.environ.get('EDITOR')
    if not editor:
        if sys.platform[:3] == 'win':
            editor = 'notepad'
        else:
            # Favor command-line editors first so we don't leave the terminal to edit
            for editor in ['vim', 'vi', 'emacs', 'nano', 'pico', 'gedit', 'kate', 'subl', 'geany', 'atom']:
                if utils.which(editor):
                    break
    feedback_to_output = False  # Do not include nonessentials in >, | output by default (things like timing)
    locals_in_py = False
    quiet = False  # Do not suppress nonessential output
    timing = False  # Prints elapsed time for each command

    # To make an attribute settable with the "do_set" command, add it to this ...
    # This starts out as a dictionary but gets converted to an OrderedDict sorted alphabetically by key
    settable = {'colors': 'Allow colorized output (valid values: Terminal, Always, Never)',
                'continuation_prompt': 'On 2nd+ line of input',
                'debug': 'Show full error stack on error',
                'echo': 'Echo command issued into output',
                'editor': 'Program used by ``edit``',
                'feedback_to_output': 'Include nonessentials in `|`, `>` results',
                'locals_in_py': 'Allow access to your application in py via self',
                'prompt': 'The prompt issued to solicit input',
                'quiet': "Don't print nonessential feedback",
                'timing': 'Report execution times'}

    def __init__(self, completekey: str='tab', stdin=None, stdout=None, persistent_history_file: str='',
                 persistent_history_length: int=1000, startup_script: Optional[str]=None, use_ipython: bool=False,
                 transcript_files: Optional[List[str]]=None) -> None:
        """An easy but powerful framework for writing line-oriented command interpreters, extends Python's cmd package.

        :param completekey: (optional) readline name of a completion key, default to Tab
        :param stdin: (optional) alternate input file object, if not specified, sys.stdin is used
        :param stdout: (optional) alternate output file object, if not specified, sys.stdout is used
        :param persistent_history_file: (optional) file path to load a persistent readline history from
        :param persistent_history_length: (optional) max number of lines which will be written to the history file
        :param startup_script: (optional) file path to a a script to load and execute at startup
        :param use_ipython: (optional) should the "ipy" command be included for an embedded IPython shell
        :param transcript_files: (optional) allows running transcript tests when allow_cli_args is False
        """
        # If use_ipython is False, make sure the do_ipy() method doesn't exit
        if not use_ipython:
            try:
                del Cmd.do_ipy
            except AttributeError:
                pass

        # Override whether ansi codes should be stripped from the output since cmd2 has its own logic for doing this
        colorama.init(strip=False)

        # initialize plugin system
        # needs to be done before we call __init__(0)
        self._initialize_plugin_system()

        # Call super class constructor
        super().__init__(completekey=completekey, stdin=stdin, stdout=stdout)

        # Get rid of cmd's complete_help() functions so AutoCompleter will complete our help command
        if getattr(cmd.Cmd, 'complete_help', None) is not None:
            delattr(cmd.Cmd, 'complete_help')

        # Commands to exclude from the help menu and tab completion
        self.hidden_commands = ['eof', 'eos', '_relative_load']

        # Commands to exclude from the history command
        self.exclude_from_history = '''history edit eof eos'''.split()

        # Command aliases and macros
        self.aliases = dict()
        self.macros = dict()

        self._finalize_app_parameters()

        self.initial_stdout = sys.stdout
        self.history = History()
        self.pystate = {}
        self.py_history = []
        self.pyscript_name = 'app'
        self.keywords = self.reserved_words + self.get_all_commands()
        self.statement_parser = StatementParser(
            allow_redirection=self.allow_redirection,
            terminators=self.terminators,
            multiline_commands=self.multiline_commands,
            aliases=self.aliases,
            shortcuts=self.shortcuts,
        )
        self._transcript_files = transcript_files

        # Used to enable the ability for a Python script to quit the application
        self._should_quit = False

        # True if running inside a Python script or interactive console, False otherwise
        self._in_py = False

        # Stores results from the last command run to enable usage of results in a Python script or interactive console
        # Built-in commands don't make use of this.  It is purely there for user-defined commands and convenience.
        self._last_result = None

        # Used to save state during a redirection
        self.kept_state = None
        self.kept_sys = None

        # Codes used for exit conditions
        self._STOP_AND_EXIT = True  # cmd convention

        self._colorcodes = {'bold': {True: '\x1b[1m', False: '\x1b[22m'},
                            'cyan': {True: Fore.CYAN, False: Fore.RESET},
                            'blue': {True: Fore.BLUE, False: Fore.RESET},
                            'red': {True: Fore.RED, False: Fore.RESET},
                            'magenta': {True: Fore.MAGENTA, False: Fore.RESET},
                            'green': {True: Fore.GREEN, False: Fore.RESET},
                            'underline': {True: '\x1b[4m', False: Fore.RESET},
                            'yellow': {True: Fore.YELLOW, False: Fore.RESET}}

        # Used load command to store the current script dir as a LIFO queue to support _relative_load command
        self._script_dir = []

        # Used when piping command output to a shell command
        self.pipe_proc = None

        # Used by complete() for readline tab completion
        self.completion_matches = []

        # Used to keep track of whether we are redirecting or piping output
        self.redirecting = False

        # If this string is non-empty, then this warning message will print if a broken pipe error occurs while printing
        self.broken_pipe_warning = ''

        # Check if history should persist
        self.persistent_history_file = ''
        if persistent_history_file and rl_type != RlType.NONE:
            persistent_history_file = os.path.expanduser(persistent_history_file)
            read_err = False

            try:
                # First try to read any existing history file
                readline.read_history_file(persistent_history_file)
            except FileNotFoundError:
                pass
            except OSError as ex:
                self.perror("readline cannot read persistent history file '{}': {}".format(persistent_history_file, ex),
                            traceback_war=False)
                read_err = True

            if not read_err:
                try:
                    # Make sure readline is able to write the history file. Doing it this way is a more thorough check
                    # than trying to open the file with write access since readline's underlying function needs to
                    # create a temporary file in the same directory and may not have permission.
                    readline.set_history_length(persistent_history_length)
                    readline.write_history_file(persistent_history_file)
                except OSError as ex:
                    self.perror("readline cannot write persistent history file '{}': {}".
                                format(persistent_history_file, ex), traceback_war=False)
                else:
                    # Set history file and register to save our history at exit
                    import atexit
                    self.persistent_history_file = persistent_history_file
                    atexit.register(readline.write_history_file, self.persistent_history_file)

        # If a startup script is provided, then add it in the queue to load
        if startup_script is not None:
            startup_script = os.path.expanduser(startup_script)
            if os.path.exists(startup_script) and os.path.getsize(startup_script) > 0:
                self.cmdqueue.append("load '{}'".format(startup_script))

        ############################################################################################################
        # The following variables are used by tab-completion functions. They are reset each time complete() is run
        # in reset_completion_defaults() and it is up to completer functions to set them before returning results.
        ############################################################################################################

        # If True and a single match is returned to complete(), then a space will be appended
        # if the match appears at the end of the line
        self.allow_appended_space = True

        # If True and a single match is returned to complete(), then a closing quote
        # will be added if there is an unmatched opening quote
        self.allow_closing_quote = True

        # An optional header that prints above the tab-completion suggestions
        self.completion_header = ''

        # Use this list if you are completing strings that contain a common delimiter and you only want to
        # display the final portion of the matches as the tab-completion suggestions. The full matches
        # still must be returned from your completer function. For an example, look at path_complete()
        # which uses this to show only the basename of paths as the suggestions. delimiter_complete() also
        # populates this list.
        self.display_matches = []

        # Used by functions like path_complete() and delimiter_complete() to properly
        # quote matches that are completed in a delimited fashion
        self.matches_delimited = False

        # Set to True before returning matches to complete() in cases where matches are sorted with custom ordering.
        # If False, then complete() will sort the matches alphabetically before they are displayed.
        self.matches_sorted = False

        # Set the pager(s) for use with the ppaged() method for displaying output using a pager
        if sys.platform.startswith('win'):
            self.pager = self.pager_chop = 'more'
        else:
            # Here is the meaning of the various flags we are using with the less command:
            # -S causes lines longer than the screen width to be chopped (truncated) rather than wrapped
            # -R causes ANSI "color" escape sequences to be output in raw form (i.e. colors are displayed)
            # -X disables sending the termcap initialization and deinitialization strings to the terminal
            # -F causes less to automatically exit if the entire file can be displayed on the first screen
            self.pager = 'less -RXF'
            self.pager_chop = 'less -SRXF'

        # This boolean flag determines whether or not the cmd2 application can interact with the clipboard
        self.can_clip = can_clip

        # This determines if a non-zero exit code should be used when exiting the application
        self.exit_code = None

        # This lock should be acquired before doing any asynchronous changes to the terminal to
        # ensure the updates to the terminal don't interfere with the input being typed. It can be
        # acquired any time there is a readline prompt on screen.
        self.terminal_lock = threading.RLock()

    # -----  Methods related to presenting output to the user -----

    @property
    def visible_prompt(self) -> str:
        """Read-only property to get the visible prompt with any ANSI escape codes stripped.

        Used by transcript testing to make it easier and more reliable when users are doing things like coloring the
        prompt using ANSI color codes.

        :return: prompt stripped of any ANSI escape codes
        """
        return utils.strip_ansi(self.prompt)

    def _finalize_app_parameters(self) -> None:
        """Finalize the shortcuts and settable parameters."""
        # noinspection PyUnresolvedReferences
        self.shortcuts = sorted(self.shortcuts.items(), reverse=True)

        # Make sure settable parameters are sorted alphabetically by key
        self.settable = collections.OrderedDict(sorted(self.settable.items(), key=lambda t: t[0]))

    def decolorized_write(self, fileobj: IO, msg: str) -> None:
        """Write a string to a fileobject, stripping ANSI escape sequences if necessary

        Honor the current colors setting, which requires us to check whether the
        fileobject is a tty.
        """
        if self.colors.lower() == constants.COLORS_NEVER.lower() or \
                (self.colors.lower() == constants.COLORS_TERMINAL.lower() and not fileobj.isatty()):
            msg = utils.strip_ansi(msg)
        fileobj.write(msg)

    def poutput(self, msg: Any, end: str='\n', color: str='') -> None:
        """Smarter self.stdout.write(); color aware and adds newline of not present.

        Also handles BrokenPipeError exceptions for when a commands's output has
        been piped to another process and that process terminates before the
        cmd2 command is finished executing.

        :param msg: message to print to current stdout (anything convertible to a str with '{}'.format() is OK)
        :param end: (optional) string appended after the end of the message if not already present, default a newline
        :param color: (optional) color escape to output this message with
        """
        if msg is not None and msg != '':
            try:
                msg_str = '{}'.format(msg)
                if not msg_str.endswith(end):
                    msg_str += end
                if color:
                    msg_str = color + msg_str + Fore.RESET
                self.decolorized_write(self.stdout, msg_str)
            except BrokenPipeError:
                # This occurs if a command's output is being piped to another
                # process and that process closes before the command is
                # finished. If you would like your application to print a
                # warning message, then set the broken_pipe_warning attribute
                # to the message you want printed.
                if self.broken_pipe_warning:
                    sys.stderr.write(self.broken_pipe_warning)

    def perror(self, err: Union[str, Exception], traceback_war: bool=True, err_color: str=Fore.LIGHTRED_EX,
               war_color: str=Fore.LIGHTYELLOW_EX) -> None:
        """ Print error message to sys.stderr and if debug is true, print an exception Traceback if one exists.

        :param err: an Exception or error message to print out
        :param traceback_war: (optional) if True, print a message to let user know they can enable debug
        :param err_color: (optional) color escape to output error with
        :param war_color: (optional) color escape to output warning with
        """
        if self.debug:
            import traceback
            traceback.print_exc()

        if isinstance(err, Exception):
            err_msg = "EXCEPTION of type '{}' occurred with message: '{}'\n".format(type(err).__name__, err)
        else:
            err_msg = "ERROR: {}\n".format(err)
        err_msg = err_color + err_msg + Fore.RESET
        self.decolorized_write(sys.stderr, err_msg)

        if traceback_war:
            war = "To enable full traceback, run the following command:  'set debug true'\n"
            war = war_color + war + Fore.RESET
            self.decolorized_write(sys.stderr, war)

    def pfeedback(self, msg: str) -> None:
        """For printing nonessential feedback.  Can be silenced with `quiet`.
           Inclusion in redirected output is controlled by `feedback_to_output`."""
        if not self.quiet:
            if self.feedback_to_output:
                self.poutput(msg)
            else:
                self.decolorized_write(sys.stderr, "{}\n".format(msg))

    def ppaged(self, msg: str, end: str='\n', chop: bool=False) -> None:
        """Print output using a pager if it would go off screen and stdout isn't currently being redirected.

        Never uses a pager inside of a script (Python or text) or when output is being redirected or piped or when
        stdout or stdin are not a fully functional terminal.

        :param msg: message to print to current stdout (anything convertible to a str with '{}'.format() is OK)
        :param end: string appended after the end of the message if not already present, default a newline
        :param chop: True -> causes lines longer than the screen width to be chopped (truncated) rather than wrapped
                              - truncated text is still accessible by scrolling with the right & left arrow keys
                              - chopping is ideal for displaying wide tabular data as is done in utilities like pgcli
                     False -> causes lines longer than the screen width to wrap to the next line
                              - wrapping is ideal when you want to keep users from having to use horizontal scrolling

        WARNING: On Windows, the text always wraps regardless of what the chop argument is set to
        """
        import subprocess
        if msg is not None and msg != '':
            try:
                msg_str = '{}'.format(msg)
                if not msg_str.endswith(end):
                    msg_str += end

                # Attempt to detect if we are not running within a fully functional terminal.
                # Don't try to use the pager when being run by a continuous integration system like Jenkins + pexpect.
                functional_terminal = False

                if self.stdin.isatty() and self.stdout.isatty():
                    if sys.platform.startswith('win') or os.environ.get('TERM') is not None:
                        functional_terminal = True

                # Don't attempt to use a pager that can block if redirecting or running a script (either text or Python)
                # Also only attempt to use a pager if actually running in a real fully functional terminal
                if functional_terminal and not self.redirecting and not self._in_py and not self._script_dir:
                    if self.colors.lower() == constants.COLORS_NEVER.lower():
                        msg_str = utils.strip_ansi(msg_str)

                    pager = self.pager
                    if chop:
                        pager = self.pager_chop
                    self.pipe_proc = subprocess.Popen(pager, shell=True, stdin=subprocess.PIPE)
                    try:
                        self.pipe_proc.stdin.write(msg_str.encode('utf-8', 'replace'))
                        self.pipe_proc.stdin.close()
                    except (OSError, KeyboardInterrupt):
                        pass

                    # Less doesn't respect ^C, but catches it for its own UI purposes (aborting search etc. inside less)
                    while True:
                        try:
                            self.pipe_proc.wait()
                        except KeyboardInterrupt:
                            pass
                        else:
                            break
                    self.pipe_proc = None
                else:
                    self.stdout.write(msg_str)
            except BrokenPipeError:
                # This occurs if a command's output is being piped to another process and that process closes before the
                # command is finished. If you would like your application to print a warning message, then set the
                # broken_pipe_warning attribute to the message you want printed.`
                if self.broken_pipe_warning:
                    sys.stderr.write(self.broken_pipe_warning)

    def colorize(self, val: str, color: str) -> str:
        """Given a string (``val``), returns that string wrapped in UNIX-style
           special characters that turn on (and then off) text color and style.
           If the ``colors`` environment parameter is ``False``, or the application
           is running on Windows, will return ``val`` unchanged.
           ``color`` should be one of the supported strings (or styles):
           red/blue/green/cyan/magenta, bold, underline"""
        if self.colors.lower() != constants.COLORS_NEVER.lower() and (self.stdout == self.initial_stdout):
            return self._colorcodes[color][True] + val + self._colorcodes[color][False]
        return val

    # -----  Methods related to tab completion -----

    def reset_completion_defaults(self) -> None:
        """
        Resets tab completion settings
        Needs to be called each time readline runs tab completion
        """
        self.allow_appended_space = True
        self.allow_closing_quote = True
        self.completion_header = ''
        self.display_matches = []
        self.matches_delimited = False
        self.matches_sorted = False

        if rl_type == RlType.GNU:
            readline.set_completion_display_matches_hook(self._display_matches_gnu_readline)
        elif rl_type == RlType.PYREADLINE:
            readline.rl.mode._display_completions = self._display_matches_pyreadline

    def tokens_for_completion(self, line: str, begidx: int, endidx: int) -> Tuple[List[str], List[str]]:
        """
        Used by tab completion functions to get all tokens through the one being completed
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :return: A 2 item tuple where the items are
                 On Success
                     tokens: list of unquoted tokens
                             this is generally the list needed for tab completion functions
                     raw_tokens: list of tokens with any quotes preserved
                                 this can be used to know if a token was quoted or is missing a closing quote

                     Both lists are guaranteed to have at least 1 item
                     The last item in both lists is the token being tab completed

                 On Failure
                    Two empty lists
        """
        import copy
        unclosed_quote = ''
        quotes_to_try = copy.copy(constants.QUOTES)

        tmp_line = line[:endidx]
        tmp_endidx = endidx

        # Parse the line into tokens
        while True:
            try:
                # Use non-POSIX parsing to keep the quotes around the tokens
                initial_tokens = shlex.split(tmp_line[:tmp_endidx], posix=False)

                # If the cursor is at an empty token outside of a quoted string,
                # then that is the token being completed. Add it to the list.
                if not unclosed_quote and begidx == tmp_endidx:
                    initial_tokens.append('')
                break
            except ValueError as ex:
                # Make sure the exception was due to an unclosed quote and
                # we haven't exhausted the closing quotes to try
                if str(ex) == "No closing quotation" and quotes_to_try:
                    # Add a closing quote and try to parse again
                    unclosed_quote = quotes_to_try[0]
                    quotes_to_try = quotes_to_try[1:]

                    tmp_line = line[:endidx]
                    tmp_line += unclosed_quote
                    tmp_endidx = endidx + 1
                else:
                    # The parsing error is not caused by unclosed quotes.
                    # Return empty lists since this means the line is malformed.
                    return [], []

        if self.allow_redirection:

            # Since redirection is enabled, we need to treat redirection characters (|, <, >)
            # as word breaks when they are in unquoted strings. Go through each token
            # and further split them on these characters. Each run of redirect characters
            # is treated as a single token.
            raw_tokens = []

            for cur_initial_token in initial_tokens:

                # Save tokens up to 1 character in length or quoted tokens. No need to parse these.
                if len(cur_initial_token) <= 1 or cur_initial_token[0] in constants.QUOTES:
                    raw_tokens.append(cur_initial_token)
                    continue

                # Iterate over each character in this token
                cur_index = 0
                cur_char = cur_initial_token[cur_index]

                # Keep track of the token we are building
                cur_raw_token = ''

                while True:
                    if cur_char not in constants.REDIRECTION_CHARS:

                        # Keep appending to cur_raw_token until we hit a redirect char
                        while cur_char not in constants.REDIRECTION_CHARS:
                            cur_raw_token += cur_char
                            cur_index += 1
                            if cur_index < len(cur_initial_token):
                                cur_char = cur_initial_token[cur_index]
                            else:
                                break

                    else:
                        redirect_char = cur_char

                        # Keep appending to cur_raw_token until we hit something other than redirect_char
                        while cur_char == redirect_char:
                            cur_raw_token += cur_char
                            cur_index += 1
                            if cur_index < len(cur_initial_token):
                                cur_char = cur_initial_token[cur_index]
                            else:
                                break

                    # Save the current token
                    raw_tokens.append(cur_raw_token)
                    cur_raw_token = ''

                    # Check if we've viewed all characters
                    if cur_index >= len(cur_initial_token):
                        break
        else:
            raw_tokens = initial_tokens

        # Save the unquoted tokens
        tokens = [utils.strip_quotes(cur_token) for cur_token in raw_tokens]

        # If the token being completed had an unclosed quote, we need
        # to remove the closing quote that was added in order for it
        # to match what was on the command line.
        if unclosed_quote:
            raw_tokens[-1] = raw_tokens[-1][:-1]

        return tokens, raw_tokens

    # noinspection PyUnusedLocal
    @staticmethod
    def basic_complete(text: str, line: str, begidx: int, endidx: int, match_against: Iterable) -> List[str]:
        """
        Performs tab completion against a list

        :param text: the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param match_against: the list being matched against
        :return: a list of possible tab completions
        """
        return [cur_match for cur_match in match_against if cur_match.startswith(text)]

    def delimiter_complete(self, text: str, line: str, begidx: int, endidx: int, match_against: Iterable,
                           delimiter: str) -> List[str]:
        """
        Performs tab completion against a list but each match is split on a delimiter and only
        the portion of the match being tab completed is shown as the completion suggestions.
        This is useful if you match against strings that are hierarchical in nature and have a
        common delimiter.

        An easy way to illustrate this concept is path completion since paths are just directories/files
        delimited by a slash. If you are tab completing items in /home/user you don't get the following
        as suggestions:

        /home/user/file.txt     /home/user/program.c
        /home/user/maps/        /home/user/cmd2.py

        Instead you are shown:

        file.txt                program.c
        maps/                   cmd2.py

        For a large set of data, this can be visually more pleasing and easier to search.

        Another example would be strings formatted with the following syntax: company::department::name
        In this case the delimiter would be :: and the user could easily narrow down what they are looking
        for if they were only shown suggestions in the category they are at in the string.

        :param text: the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param match_against: the list being matched against
        :param delimiter: what delimits each portion of the matches (ex: paths are delimited by a slash)
        :return: a list of possible tab completions
        """
        matches = self.basic_complete(text, line, begidx, endidx, match_against)

        # Display only the portion of the match that's being completed based on delimiter
        if matches:
            # Set this to True for proper quoting of matches with spaces
            self.matches_delimited = True

            # Get the common beginning for the matches
            common_prefix = os.path.commonprefix(matches)
            prefix_tokens = common_prefix.split(delimiter)

            # Calculate what portion of the match we are completing
            display_token_index = 0
            if prefix_tokens:
                display_token_index = len(prefix_tokens) - 1

            # Get this portion for each match and store them in self.display_matches
            for cur_match in matches:
                match_tokens = cur_match.split(delimiter)
                display_token = match_tokens[display_token_index]

                if not display_token:
                    display_token = delimiter
                self.display_matches.append(display_token)

        return matches

    def flag_based_complete(self, text: str, line: str, begidx: int, endidx: int,
                            flag_dict: Dict[str, Union[Iterable, Callable]],
                            all_else: Union[None, Iterable, Callable]=None) -> List[str]:
        """
        Tab completes based on a particular flag preceding the token being completed
        :param text: the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param flag_dict: dictionary whose structure is the following:
                          keys - flags (ex: -c, --create) that result in tab completion for the next
                                 argument in the command line
                          values - there are two types of values
                             1. iterable list of strings to match against (dictionaries, lists, etc.)
                             2. function that performs tab completion (ex: path_complete)
        :param all_else: an optional parameter for tab completing any token that isn't preceded by a flag in flag_dict
        :return: a list of possible tab completions
        """
        # Get all tokens through the one being completed
        tokens, _ = self.tokens_for_completion(line, begidx, endidx)
        if not tokens:
            return []

        completions_matches = []
        match_against = all_else

        # Must have at least 2 args for a flag to precede the token being completed
        if len(tokens) > 1:
            flag = tokens[-2]
            if flag in flag_dict:
                match_against = flag_dict[flag]

        # Perform tab completion using a Collection
        if isinstance(match_against, Collection):
            completions_matches = self.basic_complete(text, line, begidx, endidx, match_against)

        # Perform tab completion using a function
        elif callable(match_against):
            completions_matches = match_against(text, line, begidx, endidx)

        return completions_matches

    def index_based_complete(self, text: str, line: str, begidx: int, endidx: int,
                             index_dict: Mapping[int, Union[Iterable, Callable]],
                             all_else: Union[None, Iterable, Callable] = None) -> List[str]:
        """
        Tab completes based on a fixed position in the input string
        :param text: the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param index_dict: dictionary whose structure is the following:
                           keys - 0-based token indexes into command line that determine which tokens
                                  perform tab completion
                           values - there are two types of values
                              1. iterable list of strings to match against (dictionaries, lists, etc.)
                              2. function that performs tab completion (ex: path_complete)
        :param all_else: an optional parameter for tab completing any token that isn't at an index in index_dict
        :return: a list of possible tab completions
        """
        # Get all tokens through the one being completed
        tokens, _ = self.tokens_for_completion(line, begidx, endidx)
        if not tokens:
            return []

        matches = []

        # Get the index of the token being completed
        index = len(tokens) - 1

        # Check if token is at an index in the dictionary
        if index in index_dict:
            match_against = index_dict[index]
        else:
            match_against = all_else

        # Perform tab completion using a Collection
        if isinstance(match_against, Collection):
            matches = self.basic_complete(text, line, begidx, endidx, match_against)

        # Perform tab completion using a function
        elif callable(match_against):
            matches = match_against(text, line, begidx, endidx)

        return matches

    # noinspection PyUnusedLocal
    def path_complete(self, text: str, line: str, begidx: int, endidx: int, dir_exe_only: bool=False,
                      dir_only: bool=False) -> List[str]:
        """Performs completion of local file system paths

        :param text: the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param dir_exe_only: only return directories and executables, not non-executable files
        :param dir_only: only return directories
        :return: a list of possible tab completions
        """

        # Used to complete ~ and ~user strings
        def complete_users():

            # We are returning ~user strings that resolve to directories,
            # so don't append a space or quote in the case of a single result.
            self.allow_appended_space = False
            self.allow_closing_quote = False

            users = []

            # Windows lacks the pwd module so we can't get a list of users.
            # Instead we will return a result once the user enters text that
            # resolves to an existing home directory.
            if sys.platform.startswith('win'):
                expanded_path = os.path.expanduser(text)
                if os.path.isdir(expanded_path):
                    user = text
                    if add_trailing_sep_if_dir:
                        user += os.path.sep
                    users.append(user)
            else:
                import pwd

                # Iterate through a list of users from the password database
                for cur_pw in pwd.getpwall():

                    # Check if the user has an existing home dir
                    if os.path.isdir(cur_pw.pw_dir):

                        # Add a ~ to the user to match against text
                        cur_user = '~' + cur_pw.pw_name
                        if cur_user.startswith(text):
                            if add_trailing_sep_if_dir:
                                cur_user += os.path.sep
                            users.append(cur_user)

            return users

        # Determine if a trailing separator should be appended to directory completions
        add_trailing_sep_if_dir = False
        if endidx == len(line) or (endidx < len(line) and line[endidx] != os.path.sep):
            add_trailing_sep_if_dir = True

        # Used to replace cwd in the final results
        cwd = os.getcwd()
        cwd_added = False

        # Used to replace expanded user path in final result
        orig_tilde_path = ''
        expanded_tilde_path = ''

        # If the search text is blank, then search in the CWD for *
        if not text:
            search_str = os.path.join(os.getcwd(), '*')
            cwd_added = True
        else:
            # Purposely don't match any path containing wildcards - what we are doing is complicated enough!
            wildcards = ['*', '?']
            for wildcard in wildcards:
                if wildcard in text:
                    return []

            # Start the search string
            search_str = text + '*'

            # Handle tilde expansion and completion
            if text.startswith('~'):
                sep_index = text.find(os.path.sep, 1)

                # If there is no slash, then the user is still completing the user after the tilde
                if sep_index == -1:
                    return complete_users()

                # Otherwise expand the user dir
                else:
                    search_str = os.path.expanduser(search_str)

                    # Get what we need to restore the original tilde path later
                    orig_tilde_path = text[:sep_index]
                    expanded_tilde_path = os.path.expanduser(orig_tilde_path)

            # If the search text does not have a directory, then use the cwd
            elif not os.path.dirname(text):
                search_str = os.path.join(os.getcwd(), search_str)
                cwd_added = True

        # Set this to True for proper quoting of paths with spaces
        self.matches_delimited = True

        # Find all matching path completions
        matches = glob.glob(search_str)

        # Filter based on type
        if dir_exe_only:
            matches = [c for c in matches if os.path.isdir(c) or os.access(c, os.X_OK)]
        elif dir_only:
            matches = [c for c in matches if os.path.isdir(c)]

        # Don't append a space or closing quote to directory
        if len(matches) == 1 and os.path.isdir(matches[0]):
            self.allow_appended_space = False
            self.allow_closing_quote = False

        # Sort the matches alphabetically before any trailing slashes are added
        matches.sort(key=utils.norm_fold)
        self.matches_sorted = True

        # Build display_matches and add a slash to directories
        for index, cur_match in enumerate(matches):

            # Display only the basename of this path in the tab-completion suggestions
            self.display_matches.append(os.path.basename(cur_match))

            # Add a separator after directories if the next character isn't already a separator
            if os.path.isdir(cur_match) and add_trailing_sep_if_dir:
                matches[index] += os.path.sep
                self.display_matches[index] += os.path.sep

        # Remove cwd if it was added to match the text readline expects
        if cwd_added:
            matches = [cur_path.replace(cwd + os.path.sep, '', 1) for cur_path in matches]

        # Restore the tilde string if we expanded one to match the text readline expects
        if expanded_tilde_path:
            matches = [cur_path.replace(expanded_tilde_path, orig_tilde_path, 1) for cur_path in matches]

        return matches

    @staticmethod
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
            matches = [f for f in glob.glob(full_path + '*') if os.path.isfile(f) and os.access(f, os.X_OK)]

            for match in matches:
                exes_set.add(os.path.basename(match))

        return list(exes_set)

    def shell_cmd_complete(self, text: str, line: str, begidx: int, endidx: int,
                           complete_blank: bool=False) -> List[str]:
        """Performs completion of executables either in a user's path or a given path
        :param text: the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param complete_blank: If True, then a blank will complete all shell commands in a user's path
                               If False, then no completion is performed
                               Defaults to False to match Bash shell behavior
        :return: a list of possible tab completions
        """
        # Don't tab complete anything if no shell command has been started
        if not complete_blank and not text:
            return []

        # If there are no path characters in the search text, then do shell command completion in the user's path
        if not text.startswith('~') and os.path.sep not in text:
            return self.get_exes_in_path(text)

        # Otherwise look for executables in the given path
        else:
            return self.path_complete(text, line, begidx, endidx, dir_exe_only=True)

    def _redirect_complete(self, text: str, line: str, begidx: int, endidx: int, compfunc: Callable) -> List[str]:
        """Called by complete() as the first tab completion function for all commands
        It determines if it should tab complete for redirection (|, <, >, >>) or use the
        completer function for the current command

        :param text: the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param compfunc: the completer function for the current command
                         this will be called if we aren't completing for redirection
        :return: a list of possible tab completions
        """
        if self.allow_redirection:

            # Get all tokens through the one being completed. We want the raw tokens
            # so we can tell if redirection strings are quoted and ignore them.
            _, raw_tokens = self.tokens_for_completion(line, begidx, endidx)
            if not raw_tokens:
                return []

            if len(raw_tokens) > 1:

                # Check if there are redirection strings prior to the token being completed
                seen_pipe = False
                has_redirection = False

                for cur_token in raw_tokens[:-1]:
                    if cur_token in constants.REDIRECTION_TOKENS:
                        has_redirection = True

                        if cur_token == constants.REDIRECTION_PIPE:
                            seen_pipe = True

                # Get token prior to the one being completed
                prior_token = raw_tokens[-2]

                # If a pipe is right before the token being completed, complete a shell command as the piped process
                if prior_token == constants.REDIRECTION_PIPE:
                    return self.shell_cmd_complete(text, line, begidx, endidx)

                # Otherwise do path completion either as files to redirectors or arguments to the piped process
                elif prior_token in constants.REDIRECTION_TOKENS or seen_pipe:
                    return self.path_complete(text, line, begidx, endidx)

                # If there were redirection strings anywhere on the command line, then we
                # are no longer tab completing for the current command
                elif has_redirection:
                    return []

        # Call the command's completer function
        return compfunc(text, line, begidx, endidx)

    @staticmethod
    def _pad_matches_to_display(matches_to_display: List[str]) -> Tuple[List[str], int]:  # pragma: no cover
        """Adds padding to the matches being displayed as tab completion suggestions.
        The default padding of readline/pyreadine is small and not visually appealing
        especially if matches have spaces. It appears very squished together.

        :param matches_to_display: the matches being padded
        :return: the padded matches and length of padding that was added
        """
        if rl_type == RlType.GNU:
            # Add 2 to the padding of 2 that readline uses for a total of 4.
            padding = 2 * ' '

        elif rl_type == RlType.PYREADLINE:
            # Add 3 to the padding of 1 that pyreadline uses for a total of 4.
            padding = 3 * ' '

        else:
            return matches_to_display, 0

        return [cur_match + padding for cur_match in matches_to_display], len(padding)

    def _display_matches_gnu_readline(self, substitution: str, matches: List[str],
                                      longest_match_length: int) -> None:  # pragma: no cover
        """Prints a match list using GNU readline's rl_display_match_list()
        This exists to print self.display_matches if it has data. Otherwise matches prints.

        :param substitution: the substitution written to the command line
        :param matches: the tab completion matches to display
        :param longest_match_length: longest printed length of the matches
        """
        if rl_type == RlType.GNU:

            # Check if we should show display_matches
            if self.display_matches:
                matches_to_display = self.display_matches

                # Recalculate longest_match_length for display_matches
                longest_match_length = 0

                for cur_match in matches_to_display:
                    cur_length = wcswidth(cur_match)
                    if cur_length > longest_match_length:
                        longest_match_length = cur_length
            else:
                matches_to_display = matches

            # Add padding for visual appeal
            matches_to_display, padding_length = self._pad_matches_to_display(matches_to_display)
            longest_match_length += padding_length

            # We will use readline's display function (rl_display_match_list()), so we
            # need to encode our string as bytes to place in a C array.
            encoded_substitution = bytes(substitution, encoding='utf-8')
            encoded_matches = [bytes(cur_match, encoding='utf-8') for cur_match in matches_to_display]

            # rl_display_match_list() expects matches to be in argv format where
            # substitution is the first element, followed by the matches, and then a NULL.
            # noinspection PyCallingNonCallable,PyTypeChecker
            strings_array = (ctypes.c_char_p * (1 + len(encoded_matches) + 1))()

            # Copy in the encoded strings and add a NULL to the end
            strings_array[0] = encoded_substitution
            strings_array[1:-1] = encoded_matches
            strings_array[-1] = None

            # Print the header if one exists
            if self.completion_header:
                sys.stdout.write('\n' + self.completion_header)

            # Call readline's display function
            # rl_display_match_list(strings_array, number of completion matches, longest match length)
            readline_lib.rl_display_match_list(strings_array, len(encoded_matches), longest_match_length)

            # Redraw prompt and input line
            rl_force_redisplay()

    def _display_matches_pyreadline(self, matches: List[str]) -> None:  # pragma: no cover
        """Prints a match list using pyreadline's _display_completions()
        This exists to print self.display_matches if it has data. Otherwise matches prints.

        :param matches: the tab completion matches to display
        """
        if rl_type == RlType.PYREADLINE:

            # Check if we should show display_matches
            if self.display_matches:
                matches_to_display = self.display_matches
            else:
                matches_to_display = matches

            # Add padding for visual appeal
            matches_to_display, _ = self._pad_matches_to_display(matches_to_display)

            # Print the header if one exists
            if self.completion_header:
                readline.rl.mode.console.write('\n' + self.completion_header)

            # Display matches using actual display function. This also redraws the prompt and line.
            orig_pyreadline_display(matches_to_display)

    # -----  Methods which override stuff in cmd -----

    def complete(self, text: str, state: int) -> Optional[str]:
        """Override of command method which returns the next possible completion for 'text'.

        If a command has not been entered, then complete against command list.
        Otherwise try to call complete_<command> to get list of completions.

        This method gets called directly by readline because it is set as the tab-completion function.

        This completer function is called as complete(text, state), for state in 0, 1, 2, …, until it returns a
        non-string value. It should return the next possible completion starting with text.

        :param text: the current word that user is typing
        :param state: non-negative integer
        """
        import functools
        if state == 0 and rl_type != RlType.NONE:
            unclosed_quote = ''
            self.reset_completion_defaults()

            # lstrip the original line
            orig_line = readline.get_line_buffer()
            line = orig_line.lstrip()
            stripped = len(orig_line) - len(line)

            # Calculate new indexes for the stripped line. If the cursor is at a position before the end of a
            # line of spaces, then the following math could result in negative indexes. Enforce a max of 0.
            begidx = max(readline.get_begidx() - stripped, 0)
            endidx = max(readline.get_endidx() - stripped, 0)

            # Shortcuts are not word break characters when tab completing. Therefore shortcuts become part
            # of the text variable if there isn't a word break, like a space, after it. We need to remove it
            # from text and update the indexes. This only applies if we are at the the beginning of the line.
            shortcut_to_restore = ''
            if begidx == 0:
                for (shortcut, _) in self.shortcuts:
                    if text.startswith(shortcut):
                        # Save the shortcut to restore later
                        shortcut_to_restore = shortcut

                        # Adjust text and where it begins
                        text = text[len(shortcut_to_restore):]
                        begidx += len(shortcut_to_restore)
                        break

            # If begidx is greater than 0, then we are no longer completing the command
            if begidx > 0:

                # Parse the command line
                statement = self.statement_parser.parse_command_only(line)
                command = statement.command
                expanded_line = statement.command_and_args

                # We overwrote line with a properly formatted but fully stripped version
                # Restore the end spaces since line is only supposed to be lstripped when
                # passed to completer functions according to Python docs
                rstripped_len = len(line) - len(line.rstrip())
                expanded_line += ' ' * rstripped_len

                # Fix the index values if expanded_line has a different size than line
                if len(expanded_line) != len(line):
                    diff = len(expanded_line) - len(line)
                    begidx += diff
                    endidx += diff

                # Overwrite line to pass into completers
                line = expanded_line

                # Get all tokens through the one being completed
                tokens, raw_tokens = self.tokens_for_completion(line, begidx, endidx)

                # Check if we either had a parsing error or are trying to complete the command token
                # The latter can happen if " or ' was entered as the command
                if len(tokens) <= 1:
                    self.completion_matches = []
                    return None

                # Text we need to remove from completions later
                text_to_remove = ''

                # Get the token being completed with any opening quote preserved
                raw_completion_token = raw_tokens[-1]

                # Check if the token being completed has an opening quote
                if raw_completion_token and raw_completion_token[0] in constants.QUOTES:

                    # Since the token is still being completed, we know the opening quote is unclosed
                    unclosed_quote = raw_completion_token[0]

                    # readline still performs word breaks after a quote. Therefore something like quoted search
                    # text with a space would have resulted in begidx pointing to the middle of the token we
                    # we want to complete. Figure out where that token actually begins and save the beginning
                    # portion of it that was not part of the text readline gave us. We will remove it from the
                    # completions later since readline expects them to start with the original text.
                    actual_begidx = line[:endidx].rfind(tokens[-1])

                    if actual_begidx != begidx:
                        text_to_remove = line[actual_begidx:begidx]

                        # Adjust text and where it begins so the completer routines
                        # get unbroken search text to complete on.
                        text = text_to_remove + text
                        begidx = actual_begidx

                # Check if a valid command was entered
                if command in self.get_all_commands():
                    # Get the completer function for this command
                    compfunc = getattr(self, 'complete_' + command, None)

                    if compfunc is None:
                        # There's no completer function, next see if the command uses argparser
                        func = self.cmd_func(command)
                        if func and hasattr(func, 'argparser'):
                            compfunc = functools.partial(self._autocomplete_default,
                                                         argparser=getattr(func, 'argparser'))
                        else:
                            compfunc = self.completedefault

                # Check if a macro was entered
                elif command in self.macros:
                    compfunc = self.path_complete

                # A valid command was not entered
                else:
                    # Check if this command should be run as a shell command
                    if self.default_to_shell and command in self.get_exes_in_path(command):
                        compfunc = self.path_complete
                    else:
                        compfunc = self.completedefault

                # Attempt tab completion for redirection first, and if that isn't occurring,
                # call the completer function for the current command
                self.completion_matches = self._redirect_complete(text, line, begidx, endidx, compfunc)

                if self.completion_matches:

                    # Eliminate duplicates
                    self.completion_matches = utils.remove_duplicates(self.completion_matches)
                    self.display_matches = utils.remove_duplicates(self.display_matches)

                    if not self.display_matches:
                        # Since self.display_matches is empty, set it to self.completion_matches
                        # before we alter them. That way the suggestions will reflect how we parsed
                        # the token being completed and not how readline did.
                        import copy
                        self.display_matches = copy.copy(self.completion_matches)

                    # Check if we need to add an opening quote
                    if not unclosed_quote:

                        add_quote = False

                        # This is the tab completion text that will appear on the command line.
                        common_prefix = os.path.commonprefix(self.completion_matches)

                        if self.matches_delimited:
                            # Check if any portion of the display matches appears in the tab completion
                            display_prefix = os.path.commonprefix(self.display_matches)

                            # For delimited matches, we check what appears before the display
                            # matches (common_prefix) as well as the display matches themselves.
                            if (' ' in common_prefix) or (display_prefix and ' ' in ''.join(self.display_matches)):
                                add_quote = True

                        # If there is a tab completion and any match has a space, then add an opening quote
                        elif common_prefix and ' ' in ''.join(self.completion_matches):
                            add_quote = True

                        if add_quote:
                            # Figure out what kind of quote to add and save it as the unclosed_quote
                            if '"' in ''.join(self.completion_matches):
                                unclosed_quote = "'"
                            else:
                                unclosed_quote = '"'

                            self.completion_matches = [unclosed_quote + match for match in self.completion_matches]

                    # Check if we need to remove text from the beginning of tab completions
                    elif text_to_remove:
                        self.completion_matches = \
                            [m.replace(text_to_remove, '', 1) for m in self.completion_matches]

                    # Check if we need to restore a shortcut in the tab completions
                    # so it doesn't get erased from the command line
                    if shortcut_to_restore:
                        self.completion_matches = \
                            [shortcut_to_restore + match for match in self.completion_matches]

            else:
                # Complete token against anything a user can run
                self.completion_matches = self.basic_complete(text, line, begidx, endidx,
                                                              self.get_commands_aliases_and_macros_for_completion())

            # Handle single result
            if len(self.completion_matches) == 1:
                str_to_append = ''

                # Add a closing quote if needed and allowed
                if self.allow_closing_quote and unclosed_quote:
                    str_to_append += unclosed_quote

                # If we are at the end of the line, then add a space if allowed
                if self.allow_appended_space and endidx == len(line):
                    str_to_append += ' '

                self.completion_matches[0] += str_to_append

            # Sort matches alphabetically if they haven't already been sorted
            if not self.matches_sorted:
                self.completion_matches.sort(key=utils.norm_fold)
                self.display_matches.sort(key=utils.norm_fold)
                self.matches_sorted = True

        try:
            return self.completion_matches[state]
        except IndexError:
            return None

    def _autocomplete_default(self, text: str, line: str, begidx: int, endidx: int,
                              argparser: argparse.ArgumentParser) -> List[str]:
        """Default completion function for argparse commands."""
        completer = AutoCompleter(argparser, cmd2_app=self)

        tokens, _ = self.tokens_for_completion(line, begidx, endidx)
        if not tokens:
            return []

        return completer.complete_command(tokens, text, line, begidx, endidx)

    def get_all_commands(self) -> List[str]:
        """Returns a list of all commands."""
        return [name[len(COMMAND_FUNC_PREFIX):] for name in self.get_names()
                if name.startswith(COMMAND_FUNC_PREFIX) and callable(getattr(self, name))]

    def get_visible_commands(self) -> List[str]:
        """Returns a list of commands that have not been hidden."""
        commands = self.get_all_commands()

        # Remove the hidden commands
        for name in self.hidden_commands:
            if name in commands:
                commands.remove(name)

        return commands

    def get_alias_names(self) -> List[str]:
        """Return a list of alias names."""
        return list(self.aliases)

    def get_macro_names(self) -> List[str]:
        """Return a list of macro names."""
        return list(self.macros)

    def get_commands_aliases_and_macros_for_completion(self) -> List[str]:
        """Return a list of visible commands, aliases, and macros for tab completion"""
        visible_commands = set(self.get_visible_commands())
        alias_names = set(self.get_alias_names())
        macro_names = set(self.get_macro_names())
        return list(visible_commands | alias_names | macro_names)

    def get_help_topics(self) -> List[str]:
        """ Returns a list of help topics """
        return [name[len(HELP_FUNC_PREFIX):] for name in self.get_names()
                if name.startswith(HELP_FUNC_PREFIX) and callable(getattr(self, name))]

    # noinspection PyUnusedLocal
    def sigint_handler(self, signum: int, frame) -> None:
        """Signal handler for SIGINTs which typically come from Ctrl-C events.

        If you need custom SIGINT behavior, then override this function.

        :param signum: signal number
        :param frame
        """

        # Save copy of pipe_proc since it could theoretically change while this is running
        pipe_proc = self.pipe_proc

        if pipe_proc is not None:
            pipe_proc.terminate()

        # Re-raise a KeyboardInterrupt so other parts of the code can catch it
        raise KeyboardInterrupt("Got a keyboard interrupt")

    def precmd(self, statement: Statement) -> Statement:
        """Hook method executed just before the command is processed by ``onecmd()`` and after adding it to the history.

        :param statement: subclass of str which also contains the parsed input
        :return: a potentially modified version of the input Statement object
        """
        return statement

    def parseline(self, line: str) -> Tuple[str, str, str]:
        """Parse the line into a command name and a string containing the arguments.

        NOTE: This is an override of a parent class method.  It is only used by other parent class methods.

        Different from the parent class method, this ignores self.identchars.

        :param line: line read by readline
        :return: tuple containing (command, args, line)
        """
        statement = self.statement_parser.parse_command_only(line)
        return statement.command, statement.args, statement.command_and_args

    def onecmd_plus_hooks(self, line: str) -> bool:
        """Top-level function called by cmdloop() to handle parsing a line and running the command and all of its hooks.

        :param line: line of text read from input
        :return: True if cmdloop() should exit, False otherwise
        """
        import datetime

        stop = False
        try:
            statement = self._complete_statement(line)
        except EmptyStatement:
            return self._run_cmdfinalization_hooks(stop, None)
        except ValueError as ex:
            # If shlex.split failed on syntax, let user know whats going on
            self.perror("Invalid syntax: {}".format(ex), traceback_war=False)
            return stop

        # now that we have a statement, run it with all the hooks
        try:
            # call the postparsing hooks
            data = plugin.PostparsingData(False, statement)
            for func in self._postparsing_hooks:
                data = func(data)
                if data.stop:
                    break
            # unpack the data object
            statement = data.statement
            stop = data.stop
            if stop:
                # we should not run the command, but
                # we need to run the finalization hooks
                raise EmptyStatement

            try:
                if self.allow_redirection:
                    self._redirect_output(statement)
                timestart = datetime.datetime.now()
                if self._in_py:
                    self._last_result = None

                # precommand hooks
                data = plugin.PrecommandData(statement)
                for func in self._precmd_hooks:
                    data = func(data)
                statement = data.statement
                # call precmd() for compatibility with cmd.Cmd
                statement = self.precmd(statement)

                # go run the command function
                stop = self.onecmd(statement)

                # postcommand hooks
                data = plugin.PostcommandData(stop, statement)
                for func in self._postcmd_hooks:
                    data = func(data)
                # retrieve the final value of stop, ignoring any statement modification from the hooks
                stop = data.stop
                # call postcmd() for compatibility with cmd.Cmd
                stop = self.postcmd(stop, statement)

                if self.timing:
                    self.pfeedback('Elapsed: %s' % str(datetime.datetime.now() - timestart))
            finally:
                if self.allow_redirection and self.redirecting:
                    self._restore_output(statement)
        except EmptyStatement:
            # don't do anything, but do allow command finalization hooks to run
            pass
        except Exception as ex:
            self.perror(ex)
        finally:
            return self._run_cmdfinalization_hooks(stop, statement)

    def _run_cmdfinalization_hooks(self, stop: bool, statement: Optional[Statement]) -> bool:
        """Run the command finalization hooks"""

        if not sys.platform.startswith('win'):
            # Fix those annoying problems that occur with terminal programs like "less" when you pipe to them
            if self.stdin.isatty():
                import subprocess
                proc = subprocess.Popen(shlex.split('stty sane'))
                proc.communicate()

        try:
            data = plugin.CommandFinalizationData(stop, statement)
            for func in self._cmdfinalization_hooks:
                data = func(data)
            # retrieve the final value of stop, ignoring any
            # modifications to the statement
            return data.stop
        except Exception as ex:
            self.perror(ex)

    def runcmds_plus_hooks(self, cmds: List[str]) -> bool:
        """Convenience method to run multiple commands by onecmd_plus_hooks.

        This method adds the given cmds to the command queue and processes the
        queue until completion or an error causes it to abort. Scripts that are
        loaded will have their commands added to the queue. Scripts may even
        load other scripts recursively. This means, however, that you should not
        use this method if there is a running cmdloop or some other event-loop.
        This method is only intended to be used in "one-off" scenarios.

        NOTE: You may need this method even if you only have one command. If
        that command is a load, then you will need this command to fully process
        all the subsequent commands that are loaded from the script file. This
        is an improvement over onecmd_plus_hooks, which expects to be used
        inside of a command loop which does the processing of loaded commands.

        Example: cmd_obj.runcmds_plus_hooks(['load myscript.txt'])

        :param cmds: command strings suitable for onecmd_plus_hooks.
        :return: True implies the entire application should exit.

        """
        stop = False
        self.cmdqueue = list(cmds) + self.cmdqueue
        try:
            while self.cmdqueue and not stop:
                line = self.cmdqueue.pop(0)
                if self.echo and line != 'eos':
                    self.poutput('{}{}'.format(self.prompt, line))

                stop = self.onecmd_plus_hooks(line)
        finally:
            # Clear out the command queue and script directory stack, just in
            # case we hit an error and they were not completed.
            self.cmdqueue = []
            self._script_dir = []
            # NOTE: placing this return here inside the finally block will
            # swallow exceptions. This is consistent with what is done in
            # onecmd_plus_hooks and _cmdloop, although it may not be
            # necessary/desired here.
            return stop

    def _complete_statement(self, line: str) -> Statement:
        """Keep accepting lines of input until the command is complete.

        There is some pretty hacky code here to handle some quirks of
        self.pseudo_raw_input(). It returns a literal 'eof' if the input
        pipe runs out. We can't refactor it because we need to retain
        backwards compatibility with the standard library version of cmd.
        """
        while True:
            try:
                statement = self.statement_parser.parse(line)
                if statement.multiline_command and statement.terminator:
                    # we have a completed multiline command, we are done
                    break
                if not statement.multiline_command:
                    # it's not a multiline command, but we parsed it ok
                    # so we are done
                    break
            except ValueError:
                # we have unclosed quotation marks, lets parse only the command
                # and see if it's a multiline
                statement = self.statement_parser.parse_command_only(line)
                if not statement.multiline_command:
                    # not a multiline command, so raise the exception
                    raise

            # if we get here we must have:
            #   - a multiline command with no terminator
            #   - a multiline command with unclosed quotation marks
            if not self.quit_on_sigint:
                try:
                    newline = self.pseudo_raw_input(self.continuation_prompt)
                    if newline == 'eof':
                        # they entered either a blank line, or we hit an EOF
                        # for some other reason. Turn the literal 'eof'
                        # into a blank line, which serves as a command
                        # terminator
                        newline = '\n'
                        self.poutput(newline)
                    line = '{}\n{}'.format(statement.raw, newline)
                except KeyboardInterrupt:
                    self.poutput('^C')
                    statement = self.statement_parser.parse('')
                    break
            else:
                newline = self.pseudo_raw_input(self.continuation_prompt)
                if newline == 'eof':
                    # they entered either a blank line, or we hit an EOF
                    # for some other reason. Turn the literal 'eof'
                    # into a blank line, which serves as a command
                    # terminator
                    newline = '\n'
                    self.poutput(newline)
                line = '{}\n{}'.format(statement.raw, newline)

        if not statement.command:
            raise EmptyStatement()
        return statement

    def _redirect_output(self, statement: Statement) -> None:
        """Handles output redirection for >, >>, and |.

        :param statement: a parsed statement from the user
        """
        import io
        import subprocess

        if statement.pipe_to:
            self.kept_state = Statekeeper(self, ('stdout',))

            # Create a pipe with read and write sides
            read_fd, write_fd = os.pipe()

            # Open each side of the pipe and set stdout accordingly
            # noinspection PyTypeChecker
            self.stdout = io.open(write_fd, 'w')
            self.redirecting = True
            # noinspection PyTypeChecker
            subproc_stdin = io.open(read_fd, 'r')

            # We want Popen to raise an exception if it fails to open the process.  Thus we don't set shell to True.
            try:
                self.pipe_proc = subprocess.Popen(statement.pipe_to, stdin=subproc_stdin)
            except Exception as ex:
                # Restore stdout to what it was and close the pipe
                self.stdout.close()
                subproc_stdin.close()
                self.pipe_proc = None
                self.kept_state.restore()
                self.kept_state = None
                self.redirecting = False

                # Re-raise the exception
                raise ex
        elif statement.output:
            import tempfile
            if (not statement.output_to) and (not self.can_clip):
                raise EnvironmentError("Cannot redirect to paste buffer; install 'pyperclip' and re-run to enable")
            self.kept_state = Statekeeper(self, ('stdout',))
            self.kept_sys = Statekeeper(sys, ('stdout',))
            self.redirecting = True
            if statement.output_to:
                # going to a file
                mode = 'w'
                # statement.output can only contain
                # REDIRECTION_APPEND or REDIRECTION_OUTPUT
                if statement.output == constants.REDIRECTION_APPEND:
                    mode = 'a'
                try:
                    sys.stdout = self.stdout = open(statement.output_to, mode)
                except OSError as ex:
                    self.perror('Not Redirecting because - {}'.format(ex), traceback_war=False)
                    self.redirecting = False
            else:
                # going to a paste buffer
                sys.stdout = self.stdout = tempfile.TemporaryFile(mode="w+")
                if statement.output == constants.REDIRECTION_APPEND:
                    self.poutput(get_paste_buffer())

    def _restore_output(self, statement: Statement) -> None:
        """Handles restoring state after output redirection as well as
        the actual pipe operation if present.

        :param statement: Statement object which contains the parsed input from the user
        """
        # If we have redirected output to a file or the clipboard or piped it to a shell command, then restore state
        if self.kept_state is not None:
            # If we redirected output to the clipboard
            if statement.output and not statement.output_to:
                self.stdout.seek(0)
                write_to_paste_buffer(self.stdout.read())

            try:
                # Close the file or pipe that stdout was redirected to
                self.stdout.close()
            except BrokenPipeError:
                pass
            finally:
                # Restore self.stdout
                self.kept_state.restore()
                self.kept_state = None

            # If we were piping output to a shell command, then close the subprocess the shell command was running in
            if self.pipe_proc is not None:
                self.pipe_proc.communicate()
                self.pipe_proc = None

        # Restore sys.stdout if need be
        if self.kept_sys is not None:
            self.kept_sys.restore()
            self.kept_sys = None

        self.redirecting = False

    def cmd_func(self, command: str) -> Optional[Callable]:
        """
        Get the function for a command
        :param command: the name of the command
        """
        func_name = self.cmd_func_name(command)
        if func_name:
            return getattr(self, func_name)

    def cmd_func_name(self, command: str) -> str:
        """Get the method name associated with a given command.

        :param command: command to look up method name which implements it
        :return: method name which implements the given command
        """
        target = COMMAND_FUNC_PREFIX + command
        return target if callable(getattr(self, target, None)) else ''

    def onecmd(self, statement: Union[Statement, str]) -> bool:
        """ This executes the actual do_* method for a command.

        If the command provided doesn't exist, then it executes _default() instead.

        :param statement: intended to be a Statement instance parsed command from the input stream, alternative
                          acceptance of a str is present only for backward compatibility with cmd
        :return: a flag indicating whether the interpretation of commands should stop
        """
        # For backwards compatibility with cmd, allow a str to be passed in
        if not isinstance(statement, Statement):
            statement = self._complete_statement(statement)

        # Check if this is a macro
        if statement.command in self.macros:
            stop = self._run_macro(statement)
        else:
            func = self.cmd_func(statement.command)
            if func:
                stop = func(statement)

                # Since we have a valid command store it in the history
                if statement.command not in self.exclude_from_history:
                    self.history.append(statement.raw)

            else:
                self.default(statement)
                stop = False

        return stop

    def _run_macro(self, statement: Statement) -> bool:
        """
        Resolve a macro and run the resulting string

        :param statement: the parsed statement from the command line
        :return: a flag indicating whether the interpretation of commands should stop
        """
        if statement.command not in self.macros.keys():
            raise KeyError('{} is not a macro'.format(statement.command))

        macro = self.macros[statement.command]

        # For macros, every argument must be provided and there can be no extra arguments.
        if len(statement.arg_list) != macro.required_arg_count:
            self.perror("The macro '{}' expects {} argument(s)".format(statement.command, macro.required_arg_count),
                        traceback_war=False)
            return False

        # Resolve the arguments in reverse
        resolved = macro.value
        reverse_arg_list = sorted(macro.arg_list, key=lambda ma: ma.start_index, reverse=True)

        for arg in reverse_arg_list:
            if arg.is_escaped:
                to_replace = '{{' + arg.number_str + '}}'
                replacement = '{' + arg.number_str + '}'
            else:
                to_replace = '{' + arg.number_str + '}'
                replacement = statement.argv[int(arg.number_str)]

            parts = resolved.rsplit(to_replace, maxsplit=1)
            resolved = parts[0] + replacement + parts[1]

        # Run the resolved command
        return self.onecmd_plus_hooks(resolved)

    def default(self, statement: Statement) -> None:
        """Executed when the command given isn't a recognized command implemented by a do_* method.

        :param statement: Statement object with parsed input
        """
        arg = statement.raw
        if self.default_to_shell:
            result = os.system(arg)
            # If os.system() succeeded, then don't print warning about unknown command
            if not result:
                return

        # Print out a message stating this is an unknown command
        self.poutput('*** Unknown syntax: {}\n'.format(arg))

    def pseudo_raw_input(self, prompt: str) -> str:
        """Began life as a copy of cmd's cmdloop; like raw_input but

        - accounts for changed stdin, stdout
        - if input is a pipe (instead of a tty), look at self.echo
          to decide whether to print the prompt and the input
        """

        # Temporarily save over self.prompt to reflect what will be on screen
        orig_prompt = self.prompt
        self.prompt = prompt

        if self.use_rawinput:
            try:
                if sys.stdin.isatty():
                    # Wrap in try since terminal_lock may not be locked when this function is called from unit tests
                    try:
                        # A prompt is about to be drawn. Allow asynchronous changes to the terminal.
                        self.terminal_lock.release()
                    except RuntimeError:
                        pass

                    # Deal with the vagaries of readline and ANSI escape codes
                    safe_prompt = rl_make_safe_prompt(prompt)
                    line = input(safe_prompt)
                else:
                    line = input()
                    if self.echo:
                        sys.stdout.write('{}{}\n'.format(self.prompt, line))
            except EOFError:
                line = 'eof'
            finally:
                if sys.stdin.isatty():
                    # The prompt is gone. Do not allow asynchronous changes to the terminal.
                    self.terminal_lock.acquire()
        else:
            if self.stdin.isatty():
                # on a tty, print the prompt first, then read the line
                self.poutput(self.prompt, end='')
                self.stdout.flush()
                line = self.stdin.readline()
                if len(line) == 0:
                    line = 'eof'
            else:
                # we are reading from a pipe, read the line to see if there is
                # anything there, if so, then decide whether to print the
                # prompt or not
                line = self.stdin.readline()
                if len(line):
                    # we read something, output the prompt and the something
                    if self.echo:
                        self.poutput('{}{}'.format(self.prompt, line))
                else:
                    line = 'eof'

        # Restore prompt
        self.prompt = orig_prompt

        return line.strip()

    def _cmdloop(self) -> bool:
        """Repeatedly issue a prompt, accept input, parse an initial prefix
        off the received input, and dispatch to action methods, passing them
        the remainder of the line as argument.

        This serves the same role as cmd.cmdloop().

        :return: True implies the entire application should exit.
        """
        # An almost perfect copy from Cmd; however, the pseudo_raw_input portion
        # has been split out so that it can be called separately
        if self.use_rawinput and self.completekey and rl_type != RlType.NONE:

            # Set up readline for our tab completion needs
            if rl_type == RlType.GNU:
                # Set GNU readline's rl_basic_quote_characters to NULL so it won't automatically add a closing quote
                # We don't need to worry about setting rl_completion_suppress_quote since we never declared
                # rl_completer_quote_characters.
                old_basic_quotes = ctypes.cast(rl_basic_quote_characters, ctypes.c_void_p).value
                rl_basic_quote_characters.value = None

            old_completer = readline.get_completer()
            readline.set_completer(self.complete)

            # Break words on whitespace and quotes when tab completing
            completer_delims = " \t\n" + ''.join(constants.QUOTES)

            if self.allow_redirection:
                # If redirection is allowed, then break words on those characters too
                completer_delims += ''.join(constants.REDIRECTION_CHARS)

            old_delims = readline.get_completer_delims()
            readline.set_completer_delims(completer_delims)

            # Enable tab completion
            readline.parse_and_bind(self.completekey + ": complete")

        stop = False
        try:
            while not stop:
                if self.cmdqueue:
                    # Run command out of cmdqueue if nonempty (populated by load command or commands at invocation)
                    line = self.cmdqueue.pop(0)

                    if self.echo and line != 'eos':
                        self.poutput('{}{}'.format(self.prompt, line))
                else:
                    # Otherwise, read a command from stdin
                    if not self.quit_on_sigint:
                        try:
                            line = self.pseudo_raw_input(self.prompt)
                        except KeyboardInterrupt:
                            self.poutput('^C')
                            line = ''
                    else:
                        line = self.pseudo_raw_input(self.prompt)

                # Run the command along with all associated pre and post hooks
                stop = self.onecmd_plus_hooks(line)
        finally:
            if self.use_rawinput and self.completekey and rl_type != RlType.NONE:

                # Restore what we changed in readline
                readline.set_completer(old_completer)
                readline.set_completer_delims(old_delims)

                if rl_type == RlType.GNU:
                    readline.set_completion_display_matches_hook(None)
                    rl_basic_quote_characters.value = old_basic_quotes
                elif rl_type == RlType.PYREADLINE:
                    readline.rl.mode._display_completions = orig_pyreadline_display

            self.cmdqueue.clear()
            self._script_dir.clear()

            return stop

    # -----  Alias subcommand functions -----

    def alias_create(self, args: argparse.Namespace):
        """ Creates or overwrites an alias """

        # Validate the alias name
        args.name = utils.strip_quotes(args.name)
        valid, errmsg = self.statement_parser.is_valid_command(args.name)
        if not valid:
            self.perror("Invalid alias name: {}".format(errmsg), traceback_war=False)
            return

        if args.name in self.macros:
            self.perror("Alias cannot have the same name as a macro", traceback_war=False)
            return

        utils.unquote_redirection_tokens(args.command_args)

        # Build the alias value string
        value = args.command
        if args.command_args:
            value += ' ' + ' '.join(args.command_args)

        # Set the alias
        result = "overwritten" if args.name in self.aliases else "created"
        self.aliases[args.name] = value
        self.poutput("Alias '{}' {}".format(args.name, result))

    def alias_delete(self, args: argparse.Namespace):
        """ Deletes aliases """
        if args.all:
            self.aliases.clear()
            self.poutput("All aliases deleted")
        elif not args.name:
            self.do_help('alias delete')
        else:
            # Get rid of duplicates and strip quotes since the argparse decorator for do_alias() preserves them
            aliases_to_delete = [utils.strip_quotes(cur_name) for cur_name in utils.remove_duplicates(args.name)]

            for cur_name in aliases_to_delete:
                if cur_name in self.aliases:
                    del self.aliases[cur_name]
                    self.poutput("Alias '{}' deleted".format(cur_name))
                else:
                    self.perror("Alias '{}' does not exist".format(cur_name), traceback_war=False)

    def alias_list(self, args: argparse.Namespace):
        """ Lists some or all aliases """
        if args.name:
            # Get rid of duplicates and strip quotes since the argparse decorator for do_alias() preserves them
            names_to_view = [utils.strip_quotes(cur_name) for cur_name in utils.remove_duplicates(args.name)]

            for cur_name in names_to_view:
                if cur_name in self.aliases:
                    self.poutput("alias create {} {}".format(cur_name, self.aliases[cur_name]))
                else:
                    self.perror("Alias '{}' not found".format(cur_name), traceback_war=False)
        else:
            sorted_aliases = utils.alphabetical_sort(self.aliases)
            for cur_alias in sorted_aliases:
                self.poutput("alias create {} {}".format(cur_alias, self.aliases[cur_alias]))

    # Top-level parser for alias
    alias_description = ("Manage aliases\n"
                         "\n"
                         "An alias is a command that enables replacement of a word by another string.")
    alias_epilog = ("See also:\n"
                    "  macro")
    alias_parser = ACArgumentParser(description=alias_description, epilog=alias_epilog, prog='alias')

    # Add subcommands to alias
    alias_subparsers = alias_parser.add_subparsers()

    # alias -> create
    alias_create_help = "create or overwrite an alias"
    alias_create_description = "Create or overwrite an alias"

    alias_create_epilog = ("Notes:\n"
                           "  If you want to use redirection or pipes in the alias, then quote them to\n"
                           "  prevent the 'alias create' command from being redirected.\n"
                           "\n"
                           "  Since aliases are resolved during parsing, tab completion will function as it\n"
                           "  would for the actual command the alias resolves to.\n"
                           "\n"
                           "Examples:\n"
                           "  alias ls !ls -lF\n"
                           "  alias create show_log !cat \"log file.txt\"\n"
                           "  alias create save_results print_results \">\" out.txt\n")

    alias_create_parser = alias_subparsers.add_parser('create', help=alias_create_help,
                                                      description=alias_create_description,
                                                      epilog=alias_create_epilog)
    alias_create_parser.add_argument('name', help='name of this alias')
    setattr(alias_create_parser.add_argument('command', help='what the alias resolves to'),
            ACTION_ARG_CHOICES, get_commands_aliases_and_macros_for_completion)
    setattr(alias_create_parser.add_argument('command_args', nargs=argparse.REMAINDER,
                                             help='arguments to pass to command'),
            ACTION_ARG_CHOICES, ('path_complete',))
    alias_create_parser.set_defaults(func=alias_create)

    # alias -> delete
    alias_delete_help = "delete aliases"
    alias_delete_description = "Delete specified aliases or all aliases if --all is used"
    alias_delete_parser = alias_subparsers.add_parser('delete', help=alias_delete_help,
                                                      description=alias_delete_description)
    setattr(alias_delete_parser.add_argument('name', nargs='*', help='alias to delete'),
            ACTION_ARG_CHOICES, get_alias_names)
    alias_delete_parser.add_argument('-a', '--all', action='store_true', help="delete all aliases")
    alias_delete_parser.set_defaults(func=alias_delete)

    # alias -> list
    alias_list_help = "list aliases"
    alias_list_description = ("List specified aliases in a reusable form that can be saved to a startup script\n"
                              "to preserve aliases across sessions\n"
                              "\n"
                              "Without arguments, all aliases will be listed.")

    alias_list_parser = alias_subparsers.add_parser('list', help=alias_list_help,
                                                    description=alias_list_description)
    setattr(alias_list_parser.add_argument('name', nargs="*", help='alias to list'),
            ACTION_ARG_CHOICES, get_alias_names)
    alias_list_parser.set_defaults(func=alias_list)

    # Preserve quotes since we are passing strings to other commands
    @with_argparser(alias_parser, preserve_quotes=True)
    def do_alias(self, args: argparse.Namespace):
        """Manage aliases"""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever subcommand function was selected
            func(self, args)
        else:
            # No subcommand was provided, so call help
            self.do_help('alias')

    # -----  Macro subcommand functions -----

    def macro_create(self, args: argparse.Namespace):
        """ Creates or overwrites a macro """

        # Validate the macro name
        args.name = utils.strip_quotes(args.name)
        valid, errmsg = self.statement_parser.is_valid_command(args.name)
        if not valid:
            self.perror("Invalid macro name: {}".format(errmsg), traceback_war=False)
            return

        if args.name in self.get_all_commands():
            self.perror("Macro cannot have the same name as a command", traceback_war=False)
            return

        if args.name in self.aliases:
            self.perror("Macro cannot have the same name as an alias", traceback_war=False)
            return

        utils.unquote_redirection_tokens(args.command_args)

        # Build the macro value string
        value = args.command
        if args.command_args:
            value += ' ' + ' '.join(args.command_args)

        # Find all normal arguments
        arg_list = []
        normal_matches = re.finditer(MacroArg.macro_normal_arg_pattern, value)
        max_arg_num = 0
        arg_nums = set()

        while True:
            try:
                cur_match = normal_matches.__next__()

                # Get the number string between the braces
                cur_num_str = (re.findall(MacroArg.digit_pattern, cur_match.group())[0])
                cur_num = int(cur_num_str)
                if cur_num < 1:
                    self.perror("Argument numbers must be greater than 0", traceback_war=False)
                    return

                arg_nums.add(cur_num)
                if cur_num > max_arg_num:
                    max_arg_num = cur_num

                arg_list.append(MacroArg(start_index=cur_match.start(), number_str=cur_num_str, is_escaped=False))

            except StopIteration:
                break

        # Make sure the argument numbers are continuous
        if len(arg_nums) != max_arg_num:
            self.perror("Not all numbers between 1 and {} are present "
                        "in the argument placeholders".format(max_arg_num), traceback_war=False)
            return

        # Find all escaped arguments
        escaped_matches = re.finditer(MacroArg.macro_escaped_arg_pattern, value)

        while True:
            try:
                cur_match = escaped_matches.__next__()

                # Get the number string between the braces
                cur_num_str = re.findall(MacroArg.digit_pattern, cur_match.group())[0]

                arg_list.append(MacroArg(start_index=cur_match.start(), number_str=cur_num_str, is_escaped=True))
            except StopIteration:
                break

        # Set the macro
        result = "overwritten" if args.name in self.macros else "created"
        self.macros[args.name] = Macro(name=args.name, value=value, required_arg_count=max_arg_num, arg_list=arg_list)
        self.poutput("Macro '{}' {}".format(args.name, result))

    def macro_delete(self, args: argparse.Namespace):
        """ Deletes macros """
        if args.all:
            self.macros.clear()
            self.poutput("All macros deleted")
        elif not args.name:
            self.do_help('macro delete')
        else:
            # Get rid of duplicates and strip quotes since the argparse decorator for do_macro() preserves them
            macros_to_delete = [utils.strip_quotes(cur_name) for cur_name in utils.remove_duplicates(args.name)]

            for cur_name in macros_to_delete:
                if cur_name in self.macros:
                    del self.macros[cur_name]
                    self.poutput("Macro '{}' deleted".format(cur_name))
                else:
                    self.perror("Macro '{}' does not exist".format(cur_name), traceback_war=False)

    def macro_list(self, args: argparse.Namespace):
        """ Lists some or all macros """
        if args.name:
            # Get rid of duplicates and strip quotes since the argparse decorator for do_macro() preserves them
            names_to_view = [utils.strip_quotes(cur_name) for cur_name in utils.remove_duplicates(args.name)]

            for cur_name in names_to_view:
                if cur_name in self.macros:
                    self.poutput("macro create {} {}".format(cur_name, self.macros[cur_name].value))
                else:
                    self.perror("Macro '{}' not found".format(cur_name), traceback_war=False)
        else:
            sorted_macros = utils.alphabetical_sort(self.macros)
            for cur_macro in sorted_macros:
                self.poutput("macro create {} {}".format(cur_macro, self.macros[cur_macro].value))

    # Top-level parser for macro
    macro_description = ("Manage macros\n"
                         "\n"
                         "A macro is similar to an alias, but it can take arguments when called.")
    macro_epilog = ("See also:\n"
                    "  alias")
    macro_parser = ACArgumentParser(description=macro_description, epilog=macro_epilog, prog='macro')

    # Add subcommands to macro
    macro_subparsers = macro_parser.add_subparsers()

    # macro -> create
    macro_create_help = "create or overwrite a macro"
    macro_create_description = "Create or overwrite a macro"

    macro_create_epilog = ("A macro is similar to an alias, but it can take arguments when called.\n"
                           "Arguments are expressed when creating a macro using {#} notation where {1}\n"
                           "means the first argument.\n"
                           "\n"
                           "The following creates a macro called my_macro that expects two arguments:\n"
                           "\n"
                           "  macro create my_macro make_dinner -meat {1} -veggie {2}\n"
                           "\n"
                           "When the macro is called, the provided arguments are resolved and the assembled\n"
                           "command is run. For example:\n"
                           "\n"
                           "  my_macro beef broccoli ---> make_dinner -meat beef -veggie broccoli\n"
                           "\n"
                           "Notes:\n"
                           "  To use the literal string {1} in your command, escape it this way: {{1}}.\n"
                           "\n"
                           "  An argument number can be repeated in a macro. In the following example the\n"
                           "  first argument will populate both {1} instances.\n"
                           "\n"
                           "    macro create ft file_taxes -p {1} -q {2} -r {1}\n"
                           "\n"
                           "  To quote an argument in the resolved command, quote it during creation.\n"
                           "\n"
                           "    macro create backup !cp \"{1}\" \"{1}.orig\"\n"
                           "\n"
                           "  Be careful! Since macros can resolve into commands, aliases, and macros,\n"
                           "  it is possible to create a macro that results in infinite recursion.\n"
                           "\n"
                           "  If you want to use redirection or pipes in the macro, then quote them as in\n"
                           "  this example to prevent the 'macro create' command from being redirected.\n"
                           "\n"
                           "    macro create show_results print_results -type {1} \"|\" less\n"
                           "\n"
                           "  Because macros do not resolve until after parsing (hitting Enter), tab\n"
                           "  completion will only complete paths.")

    macro_create_parser = macro_subparsers.add_parser('create', help=macro_create_help,
                                                      description=macro_create_description,
                                                      epilog=macro_create_epilog)
    macro_create_parser.add_argument('name', help='name of this macro')
    setattr(macro_create_parser.add_argument('command', help='what the macro resolves to'),
            ACTION_ARG_CHOICES, get_commands_aliases_and_macros_for_completion)
    setattr(macro_create_parser.add_argument('command_args', nargs=argparse.REMAINDER,
                                             help='arguments to pass to command'),
            ACTION_ARG_CHOICES, ('path_complete',))
    macro_create_parser.set_defaults(func=macro_create)

    # macro -> delete
    macro_delete_help = "delete macros"
    macro_delete_description = "Delete specified macros or all macros if --all is used"
    macro_delete_parser = macro_subparsers.add_parser('delete', help=macro_delete_help,
                                                      description=macro_delete_description)
    setattr(macro_delete_parser.add_argument('name', nargs='*', help='macro to delete'),
            ACTION_ARG_CHOICES, get_macro_names)
    macro_delete_parser.add_argument('-a', '--all', action='store_true', help="delete all macros")
    macro_delete_parser.set_defaults(func=macro_delete)

    # macro -> list
    macro_list_help = "list macros"
    macro_list_description = ("List specified macros in a reusable form that can be saved to a startup script\n"
                              "to preserve macros across sessions\n"
                              "\n"
                              "Without arguments, all macros will be listed.")

    macro_list_parser = macro_subparsers.add_parser('list', help=macro_list_help, description=macro_list_description)
    setattr(macro_list_parser.add_argument('name', nargs="*", help='macro to list'),
            ACTION_ARG_CHOICES, get_macro_names)
    macro_list_parser.set_defaults(func=macro_list)

    # Preserve quotes since we are passing strings to other commands
    @with_argparser(macro_parser, preserve_quotes=True)
    def do_macro(self, args: argparse.Namespace):
        """Manage macros"""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever subcommand function was selected
            func(self, args)
        else:
            # No subcommand was provided, so call help
            self.do_help('macro')

    def complete_help_command(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Completes the command argument of help"""

        # Complete token against topics and visible commands
        topics = set(self.get_help_topics())
        visible_commands = set(self.get_visible_commands())
        strs_to_match = list(topics | visible_commands)
        return self.basic_complete(text, line, begidx, endidx, strs_to_match)

    def complete_help_subcommand(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Completes the subcommand argument of help"""

        # Get all tokens through the one being completed
        tokens, _ = self.tokens_for_completion(line, begidx, endidx)

        if not tokens:
            return []

        # Must have at least 3 args for 'help command subcommand'
        if len(tokens) < 3:
            return []

        # Find where the command is by skipping past any flags
        cmd_index = 1
        for cur_token in tokens[cmd_index:]:
            if not cur_token.startswith('-'):
                break
            cmd_index += 1

        if cmd_index >= len(tokens):
            return []

        command = tokens[cmd_index]
        matches = []

        # Check if this is a command with an argparse function
        func = self.cmd_func(command)
        if func and hasattr(func, 'argparser'):
            completer = AutoCompleter(getattr(func, 'argparser'), cmd2_app=self)
            matches = completer.complete_command_help(tokens[cmd_index:], text, line, begidx, endidx)

        return matches

    help_parser = ACArgumentParser()

    setattr(help_parser.add_argument('command', help="command to retrieve help for", nargs="?"),
            ACTION_ARG_CHOICES, ('complete_help_command',))
    setattr(help_parser.add_argument('subcommand', help="subcommand to retrieve help for",
                                     nargs=argparse.REMAINDER),
            ACTION_ARG_CHOICES, ('complete_help_subcommand',))
    help_parser.add_argument('-v', '--verbose', action='store_true',
                             help="print a list of all commands with descriptions of each")

    @with_argparser(help_parser)
    def do_help(self, args: argparse.Namespace) -> None:
        """List available commands or provide detailed help for a specific command"""
        if not args.command or args.verbose:
            self._help_menu(args.verbose)

        else:
            # Getting help for a specific command
            func = self.cmd_func(args.command)
            if func and hasattr(func, 'argparser'):
                completer = AutoCompleter(getattr(func, 'argparser'), cmd2_app=self)
                tokens = [args.command] + args.subcommand
                self.poutput(completer.format_help(tokens))
            else:
                # No special behavior needed, delegate to cmd base class do_help()
                super().do_help(args.command)

    def _help_menu(self, verbose: bool=False) -> None:
        """Show a list of commands which help can be displayed for.
        """
        # Get a sorted list of help topics
        help_topics = utils.alphabetical_sort(self.get_help_topics())

        # Get a sorted list of visible command names
        visible_commands = utils.alphabetical_sort(self.get_visible_commands())

        cmds_doc = []
        cmds_undoc = []
        cmds_cats = {}

        for command in visible_commands:
            func = self.cmd_func(command)
            if command in help_topics or func.__doc__:
                if command in help_topics:
                    help_topics.remove(command)
                if hasattr(func, HELP_CATEGORY):
                    category = getattr(func, HELP_CATEGORY)
                    cmds_cats.setdefault(category, [])
                    cmds_cats[category].append(command)
                else:
                    cmds_doc.append(command)
            else:
                cmds_undoc.append(command)

        if len(cmds_cats) == 0:
            # No categories found, fall back to standard behavior
            self.poutput("{}\n".format(str(self.doc_leader)))
            self._print_topics(self.doc_header, cmds_doc, verbose)
        else:
            # Categories found, Organize all commands by category
            self.poutput('{}\n'.format(str(self.doc_leader)))
            self.poutput('{}\n\n'.format(str(self.doc_header)))
            for category in sorted(cmds_cats.keys()):
                self._print_topics(category, cmds_cats[category], verbose)
            self._print_topics('Other', cmds_doc, verbose)

        self.print_topics(self.misc_header, help_topics, 15, 80)
        self.print_topics(self.undoc_header, cmds_undoc, 15, 80)

    def _print_topics(self, header: str, cmds: List[str], verbose: bool) -> None:
        """Customized version of print_topics that can switch between verbose or traditional output"""
        import io

        if cmds:
            if not verbose:
                self.print_topics(header, cmds, 15, 80)
            else:
                self.stdout.write('{}\n'.format(str(header)))
                widest = 0
                # measure the commands
                for command in cmds:
                    width = len(command)
                    if width > widest:
                        widest = width
                # add a 4-space pad
                widest += 4
                if widest < 20:
                    widest = 20

                if self.ruler:
                    self.stdout.write('{:{ruler}<{width}}\n'.format('', ruler=self.ruler, width=80))

                # Try to get the documentation string for each command
                topics = self.get_help_topics()

                for command in cmds:
                    # First see if there's a help function implemented
                    if command in topics:
                        func = getattr(self, HELP_FUNC_PREFIX + command)
                        result = io.StringIO()

                        # try to redirect system stdout
                        with redirect_stdout(result):
                            # save our internal stdout
                            stdout_orig = self.stdout
                            try:
                                # redirect our internal stdout
                                self.stdout = result
                                func()
                            finally:
                                # restore internal stdout
                                self.stdout = stdout_orig
                        doc = result.getvalue()

                    else:
                        # Couldn't find a help function
                        func = self.cmd_func(command)
                        doc = func.__doc__

                    # Attempt to locate the first documentation block
                    doc_block = []
                    found_first = False
                    for doc_line in doc.splitlines():
                        stripped_line = doc_line.strip()

                        # Don't include :param type lines
                        if stripped_line.startswith(':'):
                            if found_first:
                                break
                        elif stripped_line:
                            doc_block.append(stripped_line)
                            found_first = True
                        elif found_first:
                            break

                    for doc_line in doc_block:
                        self.stdout.write('{: <{col_width}}{doc}\n'.format(command,
                                                                           col_width=widest,
                                                                           doc=doc_line))
                        command = ''
                self.stdout.write("\n")

    @with_argparser(ACArgumentParser())
    def do_shortcuts(self, _: argparse.Namespace) -> None:
        """List available shortcuts"""
        result = "\n".join('%s: %s' % (sc[0], sc[1]) for sc in sorted(self.shortcuts))
        self.poutput("Shortcuts for other commands:\n{}\n".format(result))

    @with_argparser(ACArgumentParser(epilog=INTERNAL_COMMAND_EPILOG))
    def do_eof(self, _: argparse.Namespace) -> bool:
        """Called when <Ctrl>-D is pressed"""
        # End of script should not exit app, but <Ctrl>-D should.
        return self._STOP_AND_EXIT

    @with_argparser(ACArgumentParser())
    def do_quit(self, _: argparse.Namespace) -> bool:
        """Exit this application"""
        self._should_quit = True
        return self._STOP_AND_EXIT

    def select(self, opts: Union[str, List[str], List[Tuple[Any, Optional[str]]]], prompt: str='Your choice? ') -> str:
        """Presents a numbered menu to the user.  Modeled after
           the bash shell's SELECT.  Returns the item chosen.

           Argument ``opts`` can be:

             | a single string -> will be split into one-word options
             | a list of strings -> will be offered as options
             | a list of tuples -> interpreted as (value, text), so
                                   that the return value can differ from
                                   the text advertised to the user """
        local_opts = opts
        if isinstance(opts, str):
            local_opts = list(zip(opts.split(), opts.split()))
        fulloptions = []
        for opt in local_opts:
            if isinstance(opt, str):
                fulloptions.append((opt, opt))
            else:
                try:
                    fulloptions.append((opt[0], opt[1]))
                except IndexError:
                    fulloptions.append((opt[0], opt[0]))
        for (idx, (_, text)) in enumerate(fulloptions):
            self.poutput('  %2d. %s\n' % (idx + 1, text))
        while True:
            safe_prompt = rl_make_safe_prompt(prompt)
            response = input(safe_prompt)

            if rl_type != RlType.NONE:
                hlen = readline.get_current_history_length()
                if hlen >= 1 and response != '':
                    readline.remove_history_item(hlen - 1)

            try:
                choice = int(response)
                result = fulloptions[choice - 1][0]
                break
            except (ValueError, IndexError):
                self.poutput("{!r} isn't a valid choice. Pick a number between 1 and {}:\n".format(response,
                                                                                                   len(fulloptions)))
        return result

    def cmdenvironment(self) -> str:
        """Get a summary report of read-only settings which the user cannot modify at runtime.

        :return: summary report of read-only settings which the user cannot modify at runtime
        """
        read_only_settings = """
        Commands may be terminated with: {}
        Arguments at invocation allowed: {}
        Output redirection and pipes allowed: {}"""
        return read_only_settings.format(str(self.terminators), self.allow_cli_args, self.allow_redirection)

    def show(self, args: argparse.Namespace, parameter: str='') -> None:
        """Shows current settings of parameters.

        :param args: argparse parsed arguments from the set command
        :param parameter: optional search parameter
        """
        param = parameter.strip().lower()
        result = {}
        maxlen = 0

        for p in self.settable:
            if (not param) or p.startswith(param):
                result[p] = '{}: {}'.format(p, str(getattr(self, p)))
                maxlen = max(maxlen, len(result[p]))

        if result:
            for p in sorted(result):
                if args.long:
                    self.poutput('{} # {}'.format(result[p].ljust(maxlen), self.settable[p]))
                else:
                    self.poutput(result[p])

            # If user has requested to see all settings, also show read-only settings
            if args.all:
                self.poutput('\nRead only settings:{}'.format(self.cmdenvironment()))
        else:
            raise LookupError("Parameter '{}' not supported (type 'set' for list of parameters).".format(param))

    set_description = ("Set a settable parameter or show current settings of parameters\n"
                       "\n"
                       "Accepts abbreviated parameter names so long as there is no ambiguity.\n"
                       "Call without arguments for a list of settable parameters with their values.")

    set_parser = ACArgumentParser(description=set_description)
    set_parser.add_argument('-a', '--all', action='store_true', help='display read-only settings as well')
    set_parser.add_argument('-l', '--long', action='store_true', help='describe function of parameter')
    setattr(set_parser.add_argument('param', nargs='?', help='parameter to set or view'),
            ACTION_ARG_CHOICES, settable)
    set_parser.add_argument('value', nargs='?', help='the new value for settable')

    @with_argparser(set_parser)
    def do_set(self, args: argparse.Namespace) -> None:
        """Set a settable parameter or show current settings of parameters"""

        # Check if param was passed in
        if not args.param:
            return self.show(args)
        param = args.param.strip().lower()

        # Check if value was passed in
        if not args.value:
            return self.show(args, param)
        value = args.value

        # Check if param points to just one settable
        if param not in self.settable:
            hits = [p for p in self.settable if p.startswith(param)]
            if len(hits) == 1:
                param = hits[0]
            else:
                return self.show(args, param)

        # Update the settable's value
        current_value = getattr(self, param)
        value = utils.cast(current_value, value)
        setattr(self, param, value)

        self.poutput('{} - was: {}\nnow: {}\n'.format(param, current_value, value))

        # See if we need to call a change hook for this settable
        if current_value != value:
            onchange_hook = getattr(self, '_onchange_{}'.format(param), None)
            if onchange_hook is not None:
                onchange_hook(old=current_value, new=value)

    shell_parser = ACArgumentParser()
    setattr(shell_parser.add_argument('command', help='the command to run'),
            ACTION_ARG_CHOICES, ('shell_cmd_complete',))
    setattr(shell_parser.add_argument('command_args', nargs=argparse.REMAINDER,
                                      help='arguments to pass to command'),
            ACTION_ARG_CHOICES, ('path_complete',))

    # Preserve quotes since we are passing these strings to the shell
    @with_argparser(shell_parser, preserve_quotes=True)
    def do_shell(self, args: argparse.Namespace) -> None:
        """Execute a command as if at the OS prompt"""
        import subprocess

        # Create a list of arguments to shell
        tokens = [args.command] + args.command_args

        # Support expanding ~ in quoted paths
        for index, _ in enumerate(tokens):
            if tokens[index]:
                # Check if the token is quoted. Since parsing already passed, there isn't
                # an unclosed quote. So we only need to check the first character.
                first_char = tokens[index][0]
                if first_char in constants.QUOTES:
                    tokens[index] = utils.strip_quotes(tokens[index])

                tokens[index] = os.path.expanduser(tokens[index])

                # Restore the quotes
                if first_char in constants.QUOTES:
                    tokens[index] = first_char + tokens[index] + first_char

        expanded_command = ' '.join(tokens)
        proc = subprocess.Popen(expanded_command, stdout=self.stdout, shell=True)
        proc.communicate()

    @staticmethod
    def _reset_py_display() -> None:
        """
        Resets the dynamic objects in the sys module that the py and ipy consoles fight over.
        When a Python console starts it adopts certain display settings if they've already been set.
        If an ipy console has previously been run, then py uses its settings and ends up looking
        like an ipy console in terms of prompt and exception text. This method forces the Python
        console to create its own display settings since they won't exist.

        IPython does not have this problem since it always overwrites the display settings when it
        is run. Therefore this method only needs to be called before creating a Python console.
        """
        # Delete any prompts that have been set
        attributes = ['ps1', 'ps2', 'ps3']
        for cur_attr in attributes:
            try:
                del sys.__dict__[cur_attr]
            except KeyError:
                pass

        # Reset functions
        sys.displayhook = sys.__displayhook__
        sys.excepthook = sys.__excepthook__

    py_parser = ACArgumentParser()
    py_parser.add_argument('command', help="command to run", nargs='?')
    py_parser.add_argument('remainder', help="remainder of command", nargs=argparse.REMAINDER)

    # Preserve quotes since we are passing these strings to Python
    @with_argparser(py_parser, preserve_quotes=True)
    def do_py(self, args: argparse.Namespace) -> bool:
        """Invoke Python command or shell"""
        from .pyscript_bridge import PyscriptBridge, CommandResult
        if self._in_py:
            err = "Recursively entering interactive Python consoles is not allowed."
            self.perror(err, traceback_war=False)
            self._last_result = CommandResult('', err)
            return False
        self._in_py = True

        # noinspection PyBroadException
        try:
            # Support the run command even if called prior to invoking an interactive interpreter
            def run(filename: str):
                """Run a Python script file in the interactive console.

                :param filename: filename of *.py script file to run
                """
                expanded_filename = os.path.expanduser(filename)
                try:
                    with open(expanded_filename) as f:
                        interp.runcode(f.read())
                except OSError as ex:
                    error_msg = "Error opening script file '{}': {}".format(expanded_filename, ex)
                    self.perror(error_msg, traceback_war=False)

            bridge = PyscriptBridge(self)
            self.pystate['run'] = run
            self.pystate[self.pyscript_name] = bridge

            if self.locals_in_py:
                self.pystate['self'] = self
            elif 'self' in self.pystate:
                del self.pystate['self']

            localvars = self.pystate
            from code import InteractiveConsole
            interp = InteractiveConsole(locals=localvars)
            interp.runcode('import sys, os;sys.path.insert(0, os.getcwd())')

            if args.command:
                full_command = args.command
                if args.remainder:
                    full_command += ' ' + ' '.join(args.remainder)

                interp.runcode(full_command)

            # If there are no args, then we will open an interactive Python console
            else:
                # noinspection PyShadowingBuiltins
                def quit():
                    """Function callable from the interactive Python console to exit that environment"""
                    raise EmbeddedConsoleExit

                self.pystate['quit'] = quit
                self.pystate['exit'] = quit

                # Set up readline for Python console
                if rl_type != RlType.NONE:
                    # Save cmd2 history
                    saved_cmd2_history = []
                    for i in range(1, readline.get_current_history_length() + 1):
                        saved_cmd2_history.append(readline.get_history_item(i))

                    readline.clear_history()

                    # Restore py's history
                    for item in self.py_history:
                        readline.add_history(item)

                    if self.use_rawinput and self.completekey:
                        # Set up tab completion for the Python console
                        # rlcompleter relies on the default settings of the Python readline module
                        if rl_type == RlType.GNU:
                            old_basic_quotes = ctypes.cast(rl_basic_quote_characters, ctypes.c_void_p).value
                            rl_basic_quote_characters.value = orig_rl_basic_quotes

                            if 'gnureadline' in sys.modules:
                                # rlcompleter imports readline by name, so it won't use gnureadline
                                # Force rlcompleter to use gnureadline instead so it has our settings and history
                                saved_readline = None
                                if 'readline' in sys.modules:
                                    saved_readline = sys.modules['readline']

                                sys.modules['readline'] = sys.modules['gnureadline']

                        old_delims = readline.get_completer_delims()
                        readline.set_completer_delims(orig_rl_delims)

                        # rlcompleter will not need cmd2's custom display function
                        # This will be restored by cmd2 the next time complete() is called
                        if rl_type == RlType.GNU:
                            readline.set_completion_display_matches_hook(None)
                        elif rl_type == RlType.PYREADLINE:
                            readline.rl.mode._display_completions = self._display_matches_pyreadline

                        # Save off the current completer and set a new one in the Python console
                        # Make sure it tab completes from its locals() dictionary
                        old_completer = readline.get_completer()
                        interp.runcode("from rlcompleter import Completer")
                        interp.runcode("import readline")
                        interp.runcode("readline.set_completer(Completer(locals()).complete)")

                # Set up sys module for the Python console
                self._reset_py_display()
                keepstate = Statekeeper(sys, ('stdin', 'stdout'))
                sys.stdout = self.stdout
                sys.stdin = self.stdin

                cprt = 'Type "help", "copyright", "credits" or "license" for more information.'
                instructions = ('End with `Ctrl-D` (Unix) / `Ctrl-Z` (Windows), `quit()`, `exit()`.\n'
                                'Non-Python commands can be issued with: {}("your command")\n'
                                'Run Python code from external script files with: run("script.py")'
                                .format(self.pyscript_name))

                try:
                    interp.interact(banner="Python {} on {}\n{}\n\n{}\n".
                                    format(sys.version, sys.platform, cprt, instructions))
                except EmbeddedConsoleExit:
                    pass

                finally:
                    keepstate.restore()

                    # Set up readline for cmd2
                    if rl_type != RlType.NONE:
                        # Save py's history
                        self.py_history.clear()
                        for i in range(1, readline.get_current_history_length() + 1):
                            self.py_history.append(readline.get_history_item(i))

                        readline.clear_history()

                        # Restore cmd2's history
                        for item in saved_cmd2_history:
                            readline.add_history(item)

                        if self.use_rawinput and self.completekey:
                            # Restore cmd2's tab completion settings
                            readline.set_completer(old_completer)
                            readline.set_completer_delims(old_delims)

                            if rl_type == RlType.GNU:
                                rl_basic_quote_characters.value = old_basic_quotes

                                if 'gnureadline' in sys.modules:
                                    # Restore what the readline module pointed to
                                    if saved_readline is None:
                                        del(sys.modules['readline'])
                                    else:
                                        sys.modules['readline'] = saved_readline

        except Exception:
            pass
        finally:
            self._in_py = False
        return self._should_quit

    pyscript_parser = ACArgumentParser()
    setattr(pyscript_parser.add_argument('script_path', help='path to the script file'),
            ACTION_ARG_CHOICES, ('path_complete',))
    pyscript_parser.add_argument('script_arguments', nargs=argparse.REMAINDER,
                                 help='arguments to pass to script')

    @with_argparser(pyscript_parser)
    def do_pyscript(self, args: argparse.Namespace) -> None:
        """Run a Python script file inside the console"""
        script_path = os.path.expanduser(args.script_path)

        # Save current command line arguments
        orig_args = sys.argv

        # Overwrite sys.argv to allow the script to take command line arguments
        sys.argv = [script_path] + args.script_arguments

        # Run the script - use repr formatting to escape things which need to be escaped to prevent issues on Windows
        self.do_py("run({!r})".format(script_path))

        # Restore command line arguments to original state
        sys.argv = orig_args

    # Only include the do_ipy() method if IPython is available on the system
    if ipython_available:  # pragma: no cover
        @with_argparser(ACArgumentParser())
        def do_ipy(self, _: argparse.Namespace) -> None:
            """Enter an interactive IPython shell"""
            from .pyscript_bridge import PyscriptBridge
            bridge = PyscriptBridge(self)

            banner = ('Entering an embedded IPython shell. Type quit or <Ctrl>-d to exit.\n'
                      'Run Python code from external files with: run filename.py\n')
            exit_msg = 'Leaving IPython, back to {}'.format(sys.argv[0])

            if self.locals_in_py:
                def load_ipy(self, app):
                    embed(banner1=banner, exit_msg=exit_msg)
                load_ipy(self, bridge)
            else:
                def load_ipy(app):
                    embed(banner1=banner, exit_msg=exit_msg)
                load_ipy(bridge)

    history_parser = ACArgumentParser()
    history_parser_group = history_parser.add_mutually_exclusive_group()
    history_parser_group.add_argument('-r', '--run', action='store_true', help='run selected history items')
    history_parser_group.add_argument('-e', '--edit', action='store_true',
                                      help='edit and then run selected history items')
    history_parser_group.add_argument('-s', '--script', action='store_true', help='output commands in script format')
    history_parser_group.add_argument('-o', '--output-file', metavar='FILE', help='output commands to a script file')
    history_parser_group.add_argument('-t', '--transcript', help='output commands and results to a transcript file')
    history_parser_group.add_argument('-c', '--clear', action="store_true", help='clear all history')
    _history_arg_help = """empty               all history items
a                   one history item by number
a..b, a:b, a:, ..b  items by indices (inclusive)
[string]            items containing string
/regex/             items matching regular expression"""
    history_parser.add_argument('arg', nargs='?', help=_history_arg_help)

    @with_argparser(history_parser)
    def do_history(self, args: argparse.Namespace) -> None:
        """View, run, edit, save, or clear previously entered commands"""

        if args.clear:
            # Clear command and readline history
            self.history.clear()

            if rl_type != RlType.NONE:
                readline.clear_history()
                if self.persistent_history_file:
                    os.remove(self.persistent_history_file)
            return

        # If an argument was supplied, then retrieve partial contents of the history
        cowardly_refuse_to_run = False
        if args.arg:
            # If a character indicating a slice is present, retrieve
            # a slice of the history
            arg = args.arg
            if '..' in arg or ':' in arg:
                try:
                    # Get a slice of history
                    history = self.history.span(arg)
                except IndexError:
                    history = self.history.get(arg)
            else:
                # Get item(s) from history by index or string search
                history = self.history.get(arg)
        else:
            # If no arg given, then retrieve the entire history
            cowardly_refuse_to_run = True
            # Get a copy of the history so it doesn't get mutated while we are using it
            history = self.history[:]

        if args.run:
            if cowardly_refuse_to_run:
                self.perror("Cowardly refusing to run all previously entered commands.", traceback_war=False)
                self.perror("If this is what you want to do, specify '1:' as the range of history.",
                            traceback_war=False)
            else:
                for runme in history:
                    self.pfeedback(runme)
                    if runme:
                        self.onecmd_plus_hooks(runme)
        elif args.edit:
            import tempfile
            fd, fname = tempfile.mkstemp(suffix='.txt', text=True)
            with os.fdopen(fd, 'w') as fobj:
                for command in history:
                    fobj.write('{}\n'.format(command))
            try:
                os.system('"{}" "{}"'.format(self.editor, fname))
                self.do_load(fname)
            except Exception:
                raise
            finally:
                os.remove(fname)
        elif args.output_file:
            try:
                with open(os.path.expanduser(args.output_file), 'w') as fobj:
                    for command in history:
                        fobj.write('{}\n'.format(command))
                plural = 's' if len(history) > 1 else ''
                self.pfeedback('{} command{} saved to {}'.format(len(history), plural, args.output_file))
            except Exception as e:
                self.perror('Saving {!r} - {}'.format(args.output_file, e), traceback_war=False)
        elif args.transcript:
            self._generate_transcript(history, args.transcript)
        else:
            # Display the history items retrieved
            for hi in history:
                if args.script:
                    self.poutput(hi)
                else:
                    self.poutput(hi.pr())

    def _generate_transcript(self, history: List[HistoryItem], transcript_file: str) -> None:
        """Generate a transcript file from a given history of commands."""
        # Save the current echo state, and turn it off. We inject commands into the
        # output using a different mechanism
        import io

        saved_echo = self.echo
        self.echo = False

        # Redirect stdout to the transcript file
        saved_self_stdout = self.stdout

        # The problem with supporting regular expressions in transcripts
        # is that they shouldn't be processed in the command, just the output.
        # In addition, when we generate a transcript, any slashes in the output
        # are not really intended to indicate regular expressions, so they should
        # be escaped.
        #
        # We have to jump through some hoops here in order to catch the commands
        # separately from the output and escape the slashes in the output.
        transcript = ''
        for history_item in history:
            # build the command, complete with prompts. When we replay
            # the transcript, we look for the prompts to separate
            # the command from the output
            first = True
            command = ''
            for line in history_item.splitlines():
                if first:
                    command += '{}{}\n'.format(self.prompt, line)
                    first = False
                else:
                    command += '{}{}\n'.format(self.continuation_prompt, line)
            transcript += command
            # create a new string buffer and set it to stdout to catch the output
            # of the command
            membuf = io.StringIO()
            self.stdout = membuf
            # then run the command and let the output go into our buffer
            self.onecmd_plus_hooks(history_item)
            # rewind the buffer to the beginning
            membuf.seek(0)
            # get the output out of the buffer
            output = membuf.read()
            # and add the regex-escaped output to the transcript
            transcript += output.replace('/', r'\/')

        # Restore stdout to its original state
        self.stdout = saved_self_stdout
        # Set echo back to its original state
        self.echo = saved_echo

        # finally, we can write the transcript out to the file
        try:
            with open(transcript_file, 'w') as fout:
                fout.write(transcript)
        except OSError as ex:
            self.perror('Failed to save transcript: {}'.format(ex), traceback_war=False)
        else:
            # and let the user know what we did
            if len(history) > 1:
                plural = 'commands and their outputs'
            else:
                plural = 'command and its output'
            msg = '{} {} saved to transcript file {!r}'
            self.pfeedback(msg.format(len(history), plural, transcript_file))

    edit_description = ("Edit a file in a text editor\n"
                        "\n"
                        "The editor used is determined by a settable parameter. To set it:\n"
                        "\n"
                        "  set editor (program-name)")

    edit_parser = ACArgumentParser(description=edit_description)
    setattr(edit_parser.add_argument('file_path', help="path to a file to open in editor", nargs="?"),
            ACTION_ARG_CHOICES, ('path_complete',))

    @with_argparser(edit_parser)
    def do_edit(self, args: argparse.Namespace) -> None:
        """Edit a file in a text editor"""
        if not self.editor:
            raise EnvironmentError("Please use 'set editor' to specify your text editing program of choice.")

        editor = utils.quote_string_if_needed(self.editor)
        if args.file_path:
            expanded_path = utils.quote_string_if_needed(os.path.expanduser(args.file_path))
            os.system('{} {}'.format(editor, expanded_path))
        else:
            os.system('{}'.format(editor))

    @property
    def _current_script_dir(self) -> Optional[str]:
        """Accessor to get the current script directory from the _script_dir LIFO queue."""
        if self._script_dir:
            return self._script_dir[-1]
        else:
            return None

    @with_argparser(ACArgumentParser(epilog=INTERNAL_COMMAND_EPILOG))
    def do_eos(self, _: argparse.Namespace) -> None:
        """Handle cleanup when a script has finished executing"""
        if self._script_dir:
            self._script_dir.pop()

    load_description = ("Run commands in script file that is encoded as either ASCII or UTF-8 text\n"
                        "\n"
                        "Script should contain one command per line, just like the command would be\n"
                        "typed in the console.")

    load_parser = ACArgumentParser(description=load_description)
    setattr(load_parser.add_argument('script_path', help="path to the script file"),
            ACTION_ARG_CHOICES, ('path_complete',))

    @with_argparser(load_parser)
    def do_load(self, args: argparse.Namespace) -> None:
        """Run commands in script file that is encoded as either ASCII or UTF-8 text"""
        expanded_path = os.path.abspath(os.path.expanduser(args.script_path))

        # Make sure the path exists and we can access it
        if not os.path.exists(expanded_path):
            self.perror("'{}' does not exist or cannot be accessed".format(expanded_path), traceback_war=False)
            return

        # Make sure expanded_path points to a file
        if not os.path.isfile(expanded_path):
            self.perror("'{}' is not a file".format(expanded_path), traceback_war=False)
            return

        # Make sure the file is not empty
        if os.path.getsize(expanded_path) == 0:
            self.perror("'{}' is empty".format(expanded_path), traceback_war=False)
            return

        # Make sure the file is ASCII or UTF-8 encoded text
        if not utils.is_text_file(expanded_path):
            self.perror("'{}' is not an ASCII or UTF-8 encoded text file".format(expanded_path), traceback_war=False)
            return

        try:
            # Read all lines of the script and insert into the head of the
            # command queue. Add an "end of script (eos)" command to cleanup the
            # self._script_dir list when done.
            with open(expanded_path, encoding='utf-8') as target:
                self.cmdqueue = target.read().splitlines() + ['eos'] + self.cmdqueue
        except OSError as ex:  # pragma: no cover
            self.perror("Problem accessing script from '{}': {}".format(expanded_path, ex))
            return

        self._script_dir.append(os.path.dirname(expanded_path))

    relative_load_description = load_description
    relative_load_description += ("\n\n"
                                  "If this is called from within an already-running script, the filename will be\n"
                                  "interpreted relative to the already-running script's directory.")

    relative_load_epilog = ("Notes:\n"
                            "  This command is intended to only be used within text file scripts.")

    relative_load_parser = ACArgumentParser(description=relative_load_description, epilog=relative_load_epilog)
    relative_load_parser.add_argument('file_path', help='a file path pointing to a script')

    @with_argparser(relative_load_parser)
    def do__relative_load(self, args: argparse.Namespace) -> None:
        """Run commands in script file that is encoded as either ASCII or UTF-8 text"""
        file_path = args.file_path
        # NOTE: Relative path is an absolute path, it is just relative to the current script directory
        relative_path = os.path.join(self._current_script_dir or '', file_path)
        self.do_load(relative_path)

    def run_transcript_tests(self, callargs: List[str]) -> None:
        """Runs transcript tests for provided file(s).

        This is called when either -t is provided on the command line or the transcript_files argument is provided
        during construction of the cmd2.Cmd instance.

        :param callargs: list of transcript test file names
        """
        import unittest
        from .transcript import Cmd2TestCase

        class TestMyAppCase(Cmd2TestCase):
            cmdapp = self

        self.__class__.testfiles = callargs
        sys.argv = [sys.argv[0]]  # the --test argument upsets unittest.main()
        testcase = TestMyAppCase()
        runner = unittest.TextTestRunner()
        runner.run(testcase)

    def _clear_input_lines_str(self) -> str:  # pragma: no cover
        """
        Returns a string that if printed will clear the prompt and input lines in the terminal,
        leaving the cursor at the beginning of the first input line
        :return: the string to print
        """
        if not (vt100_support and self.use_rawinput):
            return ''

        import shutil
        import colorama.ansi as ansi
        from colorama import Cursor

        visible_prompt = self.visible_prompt

        # Get the size of the terminal
        terminal_size = shutil.get_terminal_size()

        # Figure out how many lines the prompt and user input take up
        total_str_size = len(visible_prompt) + len(readline.get_line_buffer())
        num_input_lines = int(total_str_size / terminal_size.columns) + 1

        # Get the cursor's offset from the beginning of the first input line
        cursor_input_offset = len(visible_prompt) + rl_get_point()

        # Calculate what input line the cursor is on
        cursor_input_line = int(cursor_input_offset / terminal_size.columns) + 1

        # Create a string that will clear all input lines and print the alert
        terminal_str = ''

        # Move the cursor down to the last input line
        if cursor_input_line != num_input_lines:
            terminal_str += Cursor.DOWN(num_input_lines - cursor_input_line)

        # Clear each input line from the bottom up so that the cursor ends up on the original first input line
        terminal_str += (ansi.clear_line() + Cursor.UP(1)) * (num_input_lines - 1)
        terminal_str += ansi.clear_line()

        # Move the cursor to the beginning of the first input line
        terminal_str += '\r'

        return terminal_str

    def async_alert(self, alert_msg: str, new_prompt: Optional[str] = None) -> None:  # pragma: no cover
        """
        Used to display an important message to the user while they are at the prompt in between commands.
        To the user it appears as if an alert message is printed above the prompt and their current input
        text and cursor location is left alone.

        IMPORTANT: Do not call this unless you have acquired self.terminal_lock
                   first, which ensures a prompt is onscreen

        :param alert_msg: the message to display to the user
        :param new_prompt: if you also want to change the prompt that is displayed, then include it here
                           see async_update_prompt() docstring for guidance on updating a prompt
        :raises RuntimeError if called while another thread holds terminal_lock
        """
        if not (vt100_support and self.use_rawinput):
            return

        # Sanity check that can't fail if self.terminal_lock was acquired before calling this function
        if self.terminal_lock.acquire(blocking=False):

            # Generate a string to clear the prompt and input lines and replace with the alert
            terminal_str = self._clear_input_lines_str()
            if alert_msg:
                terminal_str += alert_msg + '\n'

            # Set the new prompt now that _clear_input_lines_str is done using the old prompt
            if new_prompt is not None:
                self.prompt = new_prompt
                rl_set_prompt(self.prompt)

            # Print terminal_str to erase the lines
            if rl_type == RlType.GNU:
                sys.stderr.write(terminal_str)
            elif rl_type == RlType.PYREADLINE:
                readline.rl.mode.console.write(terminal_str)

            # Redraw the prompt and input lines
            rl_force_redisplay()

            self.terminal_lock.release()

        else:
            raise RuntimeError("another thread holds terminal_lock")

    def async_update_prompt(self, new_prompt: str) -> None:  # pragma: no cover
        """
        Updates the prompt while the user is still typing at it. This is good for alerting the user to system
        changes dynamically in between commands. For instance you could alter the color of the prompt to indicate
        a system status or increase a counter to report an event. If you do alter the actual text of the prompt,
        it is best to keep the prompt the same width as what's on screen. Otherwise the user's input text will
        be shifted and the update will not be seamless.

        IMPORTANT: Do not call this unless you have acquired self.terminal_lock
                   first, which ensures a prompt is onscreen

        :param new_prompt: what to change the prompt to
        """
        self.async_alert('', new_prompt)

    @staticmethod
    def set_window_title(title: str) -> None:  # pragma: no cover
        """
        Sets the terminal window title
        :param title: the new window title
        """
        if not vt100_support:
            return

        import colorama.ansi as ansi
        try:
            sys.stderr.write(ansi.set_title(title))
        except AttributeError:
            # Debugging in Pycharm has issues with setting terminal title
            pass

    def cmdloop(self, intro: Optional[str]=None) -> None:
        """This is an outer wrapper around _cmdloop() which deals with extra features provided by cmd2.

        _cmdloop() provides the main loop equivalent to cmd.cmdloop().  This is a wrapper around that which deals with
        the following extra features provided by cmd2:
        - commands at invocation
        - transcript testing
        - intro banner

        :param intro: if provided this overrides self.intro and serves as the intro banner printed once at start
        """
        if self.allow_cli_args:
            parser = argparse.ArgumentParser()
            parser.add_argument('-t', '--test', action="store_true",
                                help='Test against transcript(s) in FILE (wildcards OK)')
            callopts, callargs = parser.parse_known_args()

            # If transcript testing was called for, use other arguments as transcript files
            if callopts.test:
                self._transcript_files = callargs

            # If commands were supplied at invocation, then add them to the command queue
            if callargs:
                self.cmdqueue.extend(callargs)

        # Register a SIGINT signal handler for Ctrl+C
        import signal
        original_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self.sigint_handler)

        # Grab terminal lock before the prompt has been drawn by readline
        self.terminal_lock.acquire()

        # Always run the preloop first
        for func in self._preloop_hooks:
            func()
        self.preloop()

        # If transcript-based regression testing was requested, then do that instead of the main loop
        if self._transcript_files is not None:
            self.run_transcript_tests(self._transcript_files)
        else:
            # If an intro was supplied in the method call, allow it to override the default
            if intro is not None:
                self.intro = intro

            # Print the intro, if there is one, right after the preloop
            if self.intro is not None:
                self.poutput(str(self.intro) + "\n")

            # And then call _cmdloop() to enter the main loop
            self._cmdloop()

        # Run the postloop() no matter what
        for func in self._postloop_hooks:
            func()
        self.postloop()

        # Release terminal lock now that postloop code should have stopped any terminal updater threads
        # This will also zero the lock count in case cmdloop() is called again
        self.terminal_lock.release()

        # Restore the original signal handler
        signal.signal(signal.SIGINT, original_sigint_handler)

        if self.exit_code is not None:
            sys.exit(self.exit_code)

    ###
    #
    # plugin related functions
    #
    ###
    def _initialize_plugin_system(self) -> None:
        """Initialize the plugin system"""
        self._preloop_hooks = []
        self._postloop_hooks = []
        self._postparsing_hooks = []
        self._precmd_hooks = []
        self._postcmd_hooks = []
        self._cmdfinalization_hooks = []

    @classmethod
    def _validate_callable_param_count(cls, func: Callable, count: int) -> None:
        """Ensure a function has the given number of parameters."""
        signature = inspect.signature(func)
        # validate that the callable has the right number of parameters
        nparam = len(signature.parameters)
        if nparam != count:
            raise TypeError('{} has {} positional arguments, expected {}'.format(
                func.__name__,
                nparam,
                count,
            ))

    @classmethod
    def _validate_prepostloop_callable(cls, func: Callable[[None], None]) -> None:
        """Check parameter and return types for preloop and postloop hooks."""
        cls._validate_callable_param_count(func, 0)
        # make sure there is no return notation
        signature = inspect.signature(func)
        if signature.return_annotation is not None:
            raise TypeError("{} must declare return a return type of 'None'".format(
                func.__name__,
            ))

    def register_preloop_hook(self, func: Callable[[None], None]) -> None:
        """Register a function to be called at the beginning of the command loop."""
        self._validate_prepostloop_callable(func)
        self._preloop_hooks.append(func)

    def register_postloop_hook(self, func: Callable[[None], None]) -> None:
        """Register a function to be called at the end of the command loop."""
        self._validate_prepostloop_callable(func)
        self._postloop_hooks.append(func)

    @classmethod
    def _validate_postparsing_callable(cls, func: Callable[[plugin.PostparsingData], plugin.PostparsingData]) -> None:
        """Check parameter and return types for postparsing hooks"""
        cls._validate_callable_param_count(func, 1)
        signature = inspect.signature(func)
        _, param = list(signature.parameters.items())[0]
        if param.annotation != plugin.PostparsingData:
            raise TypeError("{} must have one parameter declared with type 'cmd2.plugin.PostparsingData'".format(
                func.__name__
            ))
        if signature.return_annotation != plugin.PostparsingData:
            raise TypeError("{} must declare return a return type of 'cmd2.plugin.PostparsingData'".format(
                func.__name__
            ))

    def register_postparsing_hook(self, func: Callable[[plugin.PostparsingData], plugin.PostparsingData]) -> None:
        """Register a function to be called after parsing user input but before running the command"""
        self._validate_postparsing_callable(func)
        self._postparsing_hooks.append(func)

    @classmethod
    def _validate_prepostcmd_hook(cls, func: Callable, data_type: Type) -> None:
        """Check parameter and return types for pre and post command hooks."""
        signature = inspect.signature(func)
        # validate that the callable has the right number of parameters
        cls._validate_callable_param_count(func, 1)
        # validate the parameter has the right annotation
        paramname = list(signature.parameters.keys())[0]
        param = signature.parameters[paramname]
        if param.annotation != data_type:
            raise TypeError('argument 1 of {} has incompatible type {}, expected {}'.format(
                func.__name__,
                param.annotation,
                data_type,
            ))
        # validate the return value has the right annotation
        if signature.return_annotation == signature.empty:
            raise TypeError('{} does not have a declared return type, expected {}'.format(
                func.__name__,
                data_type,
            ))
        if signature.return_annotation != data_type:
            raise TypeError('{} has incompatible return type {}, expected {}'.format(
                func.__name__,
                signature.return_annotation,
                data_type,
            ))

    def register_precmd_hook(self, func: Callable[[plugin.PrecommandData], plugin.PrecommandData]) -> None:
        """Register a hook to be called before the command function."""
        self._validate_prepostcmd_hook(func, plugin.PrecommandData)
        self._precmd_hooks.append(func)

    def register_postcmd_hook(self, func: Callable[[plugin.PostcommandData], plugin.PostcommandData]) -> None:
        """Register a hook to be called after the command function."""
        self._validate_prepostcmd_hook(func, plugin.PostcommandData)
        self._postcmd_hooks.append(func)

    @classmethod
    def _validate_cmdfinalization_callable(cls, func: Callable[[plugin.CommandFinalizationData],
                                                               plugin.CommandFinalizationData]) -> None:
        """Check parameter and return types for command finalization hooks."""
        cls._validate_callable_param_count(func, 1)
        signature = inspect.signature(func)
        _, param = list(signature.parameters.items())[0]
        if param.annotation != plugin.CommandFinalizationData:
            raise TypeError("{} must have one parameter declared with type "
                            "'cmd2.plugin.CommandFinalizationData'".format(func.__name__))
        if signature.return_annotation != plugin.CommandFinalizationData:
            raise TypeError("{} must declare return a return type of "
                            "'cmd2.plugin.CommandFinalizationData'".format(func.__name__))

    def register_cmdfinalization_hook(self, func: Callable[[plugin.CommandFinalizationData],
                                                           plugin.CommandFinalizationData]) -> None:
        """Register a hook to be called after a command is completed, whether it completes successfully or not."""
        self._validate_cmdfinalization_callable(func)
        self._cmdfinalization_hooks.append(func)


class History(list):
    """ A list of HistoryItems that knows how to respond to user requests. """

    # noinspection PyMethodMayBeStatic
    def _zero_based_index(self, onebased: int) -> int:
        """Convert a one-based index to a zero-based index."""
        result = onebased
        if result > 0:
            result -= 1
        return result

    def _to_index(self, raw: str) -> Optional[int]:
        if raw:
            result = self._zero_based_index(int(raw))
        else:
            result = None
        return result

    spanpattern = re.compile(r'^\s*(?P<start>-?\d+)?\s*(?P<separator>:|(\.{2,}))?\s*(?P<end>-?\d+)?\s*$')

    def span(self, raw: str) -> List[HistoryItem]:
        """Parses the input string search for a span pattern and if if found, returns a slice from the History list.

        :param raw: string potentially containing a span of the forms a..b, a:b, a:, ..b
        :return: slice from the History list
        """
        if raw.lower() in ('*', '-', 'all'):
            raw = ':'
        results = self.spanpattern.search(raw)
        if not results:
            raise IndexError
        if not results.group('separator'):
            return [self[self._to_index(results.group('start'))]]
        start = self._to_index(results.group('start')) or 0  # Ensure start is not None
        end = self._to_index(results.group('end'))
        reverse = False
        if end is not None:
            if end < start:
                (start, end) = (end, start)
                reverse = True
            end += 1
        result = self[start:end]
        if reverse:
            result.reverse()
        return result

    rangePattern = re.compile(r'^\s*(?P<start>[\d]+)?\s*-\s*(?P<end>[\d]+)?\s*$')

    def append(self, new: str) -> None:
        """Append a HistoryItem to end of the History list

        :param new: command line to convert to HistoryItem and add to the end of the History list
        """
        new = HistoryItem(new)
        list.append(self, new)
        new.idx = len(self)

    def get(self, getme: Optional[Union[int, str]]=None) -> List[HistoryItem]:
        """Get an item or items from the History list using 1-based indexing.

        :param getme: optional item(s) to get (either an integer index or string to search for)
        :return: list of HistoryItems matching the retrieval criteria
        """
        if not getme:
            return self
        try:
            getme = int(getme)
            if getme < 0:
                return self[:(-1 * getme)]
            else:
                return [self[getme - 1]]
        except IndexError:
            return []
        except ValueError:
            range_result = self.rangePattern.search(getme)
            if range_result:
                start = range_result.group('start') or None
                end = range_result.group('start') or None
                if start:
                    start = int(start) - 1
                if end:
                    end = int(end)
                return self[start:end]

            # noinspection PyUnresolvedReferences
            getme = getme.strip()

            if getme.startswith(r'/') and getme.endswith(r'/'):
                finder = re.compile(getme[1:-1], re.DOTALL | re.MULTILINE | re.IGNORECASE)

                def isin(hi):
                    """Listcomp filter function for doing a regular expression search of History.

                    :param hi: HistoryItem
                    :return: bool - True if search matches
                    """
                    return finder.search(hi)
            else:
                def isin(hi):
                    """Listcomp filter function for doing a case-insensitive string search of History.

                    :param hi: HistoryItem
                    :return: bool - True if search matches
                    """
                    return getme.lower() in hi.lowercase
            return [itm for itm in self if isin(itm)]


class Statekeeper(object):
    """Class used to save and restore state during load and py commands as well as when redirecting output or pipes."""
    def __init__(self, obj: Any, attribs: Iterable) -> None:
        """Use the instance attributes as a generic key-value store to copy instance attributes from outer object.

        :param obj: instance of cmd2.Cmd derived class (your application instance)
        :param attribs: tuple of strings listing attributes of obj to save a copy of
        """
        self.obj = obj
        self.attribs = attribs
        if self.obj:
            self._save()

    def _save(self) -> None:
        """Create copies of attributes from self.obj inside this Statekeeper instance."""
        for attrib in self.attribs:
            setattr(self, attrib, getattr(self.obj, attrib))

    def restore(self) -> None:
        """Overwrite attributes in self.obj with the saved values stored in this Statekeeper instance."""
        if self.obj:
            for attrib in self.attribs:
                setattr(self.obj, attrib, getattr(self, attrib))
