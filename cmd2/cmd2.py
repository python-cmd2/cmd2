"""cmd2 - quickly build feature-rich and user-friendly interactive command line applications in Python.

cmd2 is a tool for building interactive command line applications in Python. Its goal is to make it quick and easy for
developers to build feature-rich and user-friendly interactive command line applications. It provides a simple API which
is an extension of Python's built-in cmd module. cmd2 provides a wealth of features on top of cmd to make your life easier
and eliminates much of the boilerplate code which would be necessary when using cmd.

Extra features include:
- Searchable command history (commands: "history")
- Run commands from file, save to file, edit commands in file
- Multi-line commands
- Special-character shortcut commands (beyond cmd's "?" and "!")
- Settable environment parameters
- Parsing commands with `argparse` argument parsers (flags)
- Redirection to file or paste buffer (clipboard) with > or >>
- Easy transcript-based testing of applications (see examples/transcript_example.py)
- Bash-style ``select`` available

Note, if self.stdout is different than sys.stdout, then redirection with > and |
will only work if `self.poutput()` is used in place of `print`.

GitHub: https://github.com/python-cmd2/cmd2
Documentation: https://cmd2.readthedocs.io/
"""

# This module has many imports, quite a few of which are only
# infrequently utilized. To reduce the initial overhead of
# import this module, many of these imports are lazy-loaded
# i.e. we only import the module when we use it.
import argparse
import contextlib
import copy
import functools
import glob
import inspect
import os
import pydoc
import re
import sys
import tempfile
import threading
from code import InteractiveConsole
from collections import (
    OrderedDict,
    namedtuple,
)
from collections.abc import (
    Callable,
    Iterable,
    Mapping,
)
from types import (
    FrameType,
)
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    ClassVar,
    TextIO,
    TypeVar,
    Union,
    cast,
)

import rich.box
from rich.console import Console, Group, RenderableType
from rich.highlighter import ReprHighlighter
from rich.rule import Rule
from rich.style import Style, StyleType
from rich.table import (
    Column,
    Table,
)
from rich.text import Text
from rich.traceback import Traceback

from . import (
    argparse_completer,
    argparse_custom,
    constants,
    plugin,
    utils,
)
from . import rich_utils as ru
from . import string_utils as su
from .argparse_custom import (
    ChoicesProviderFunc,
    Cmd2ArgumentParser,
    CompleterFunc,
    CompletionItem,
)
from .clipboard import (
    get_paste_buffer,
    write_to_paste_buffer,
)
from .command_definition import (
    CommandFunc,
    CommandSet,
)
from .constants import (
    CLASS_ATTR_DEFAULT_HELP_CATEGORY,
    COMMAND_FUNC_PREFIX,
    COMPLETER_FUNC_PREFIX,
    HELP_FUNC_PREFIX,
)
from .decorators import (
    CommandParent,
    as_subcommand_to,
    with_argparser,
)
from .exceptions import (
    Cmd2ShlexError,
    CommandSetRegistrationError,
    CompletionError,
    EmbeddedConsoleExit,
    EmptyStatement,
    PassThroughException,
    RedirectionError,
    SkipPostcommandHooks,
)
from .history import (
    History,
    HistoryItem,
)
from .parsing import (
    Macro,
    MacroArg,
    Statement,
    StatementParser,
    shlex_split,
)
from .rich_utils import (
    Cmd2ExceptionConsole,
    Cmd2GeneralConsole,
    RichPrintKwargs,
)
from .styles import Cmd2Style

with contextlib.suppress(ImportError):
    from IPython import start_ipython

from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, DummyCompleter
from prompt_toolkit.formatted_text import ANSI, FormattedText
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.input import DummyInput
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import CompleteStyle, PromptSession, set_title

try:
    if sys.platform == "win32":
        from prompt_toolkit.output.win32 import NoConsoleScreenBufferError  # type: ignore[attr-defined]
    else:
        # Trigger the except block for non-Windows platforms
        raise ImportError  # noqa: TRY301
except ImportError:

    class NoConsoleScreenBufferError(Exception):  # type: ignore[no-redef]
        """Dummy exception to use when prompt_toolkit.output.win32.NoConsoleScreenBufferError is not available."""

        def __init__(self, msg: str = '') -> None:
            """Initialize NoConsoleScreenBufferError custom exception instance."""
            super().__init__(msg)


from .pt_utils import (
    Cmd2Completer,
    Cmd2History,
    Cmd2Lexer,
)
from .utils import (
    Settable,
    get_defining_class,
    get_types,
    strip_doc_annotations,
    suggest_similar,
)


class _SavedCmd2Env:
    """cmd2 environment settings that are backed up when entering an interactive Python shell."""

    def __init__(self) -> None:
        self.history: list[str] = []
        self.completer: Callable[[str, int], str | None] | None = None


# Contains data about a disabled command which is used to restore its original functions when the command is enabled
DisabledCommand = namedtuple('DisabledCommand', ['command_function', 'help_function', 'completer_function'])  # noqa: PYI024


if TYPE_CHECKING:  # pragma: no cover
    StaticArgParseBuilder = staticmethod[[], argparse.ArgumentParser]
    ClassArgParseBuilder = classmethod['Cmd' | CommandSet, [], argparse.ArgumentParser]
else:
    StaticArgParseBuilder = staticmethod
    ClassArgParseBuilder = classmethod


class _CommandParsers:
    """Create and store all command method argument parsers for a given Cmd instance.

    Parser creation and retrieval are accomplished through the get() method.
    """

    def __init__(self, cmd: 'Cmd') -> None:
        self._cmd = cmd

        # Keyed by the fully qualified method names. This is more reliable than
        # the methods themselves, since wrapping a method will change its address.
        self._parsers: dict[str, argparse.ArgumentParser] = {}

    @staticmethod
    def _fully_qualified_name(command_method: CommandFunc) -> str:
        """Return the fully qualified name of a method or None if a method wasn't passed in."""
        try:
            return f"{command_method.__module__}.{command_method.__qualname__}"
        except AttributeError:
            return ""

    def __contains__(self, command_method: CommandFunc) -> bool:
        """Return whether a given method's parser is in self.

        If the parser does not yet exist, it will be created if applicable.
        This is basically for checking if a method is argarse-based.
        """
        parser = self.get(command_method)
        return bool(parser)

    def get(self, command_method: CommandFunc) -> argparse.ArgumentParser | None:
        """Return a given method's parser or None if the method is not argparse-based.

        If the parser does not yet exist, it will be created.
        """
        full_method_name = self._fully_qualified_name(command_method)
        if not full_method_name:
            return None

        if full_method_name not in self._parsers:
            if not command_method.__name__.startswith(COMMAND_FUNC_PREFIX):
                return None
            command = command_method.__name__[len(COMMAND_FUNC_PREFIX) :]

            parser_builder = getattr(command_method, constants.CMD_ATTR_ARGPARSER, None)
            if parser_builder is None:
                return None

            parent = self._cmd.find_commandset_for_command(command) or self._cmd
            parser = self._cmd._build_parser(parent, parser_builder, command)

            # If the description has not been set, then use the method docstring if one exists
            if parser.description is None and command_method.__doc__:
                parser.description = strip_doc_annotations(command_method.__doc__)

            self._parsers[full_method_name] = parser

        return self._parsers.get(full_method_name)

    def remove(self, command_method: CommandFunc) -> None:
        """Remove a given method's parser if it exists."""
        full_method_name = self._fully_qualified_name(command_method)
        if full_method_name in self._parsers:
            del self._parsers[full_method_name]


class Cmd:
    """An easy but powerful framework for writing line-oriented command interpreters.

    Extends the Python Standard Library's cmd package by adding a lot of useful features
    to the out of the box configuration.

    Line-oriented command interpreters are often useful for test harnesses, internal tools, and rapid prototypes.
    """

    DEFAULT_COMPLETEKEY = 'tab'

    DEFAULT_EDITOR = utils.find_editor()

    # Sorting keys for strings
    ALPHABETICAL_SORT_KEY = su.norm_fold
    NATURAL_SORT_KEY = utils.natural_keys

    # List for storing transcript test file names
    testfiles: ClassVar[list[str]] = []

    DEFAULT_PROMPT = '(Cmd) '

    def __init__(
        self,
        completekey: str = DEFAULT_COMPLETEKEY,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
        *,
        allow_cli_args: bool = True,
        allow_clipboard: bool = True,
        allow_redirection: bool = True,
        auto_load_commands: bool = False,
        auto_suggest: bool = True,
        bottom_toolbar: bool = False,
        command_sets: Iterable[CommandSet] | None = None,
        include_ipy: bool = False,
        include_py: bool = False,
        intro: RenderableType = '',
        multiline_commands: list[str] | None = None,
        persistent_history_file: str = '',
        persistent_history_length: int = 1000,
        shortcuts: dict[str, str] | None = None,
        silence_startup_script: bool = False,
        startup_script: str = '',
        suggest_similar_command: bool = False,
        terminators: list[str] | None = None,
        transcript_files: list[str] | None = None,
    ) -> None:
        """Easy but powerful framework for writing line-oriented command interpreters, extends Python's cmd package.

        :param completekey: name of a completion key, default to Tab
        :param stdin: alternate input file object, if not specified, sys.stdin is used
        :param stdout: alternate output file object, if not specified, sys.stdout is used
        :param allow_cli_args: if ``True``, then [cmd2.Cmd.__init__][] will process command
                               line arguments as either commands to be run or, if ``-t`` or
                               ``--test`` are given, transcript files to run. This should be
                               set to ``False`` if your application parses its own command line
                               arguments.
        :param allow_clipboard: If False, cmd2 will disable clipboard interactions
        :param allow_redirection: If ``False``, prevent output redirection and piping to shell
                                  commands. This parameter prevents redirection and piping, but
                                  does not alter parsing behavior. A user can still type
                                  redirection and piping tokens, and they will be parsed as such
                                  but they won't do anything.
        :param auto_load_commands: If True, cmd2 will check for all subclasses of `CommandSet`
                                   that are currently loaded by Python and automatically
                                   instantiate and register all commands. If False, CommandSets
                                   must be manually installed with `register_command_set`.
        :param auto_suggest: If True, cmd2 will provide fish shell style auto-suggestions
                            based on history. If False, these will not be provided.
        :param bottom_toolbar: if ``True``, then a bottom toolbar will be displayed.
        :param command_sets: Provide CommandSet instances to load during cmd2 initialization.
                             This allows CommandSets with custom constructor parameters to be
                             loaded.  This also allows the a set of CommandSets to be provided
                             when `auto_load_commands` is set to False
        :param include_ipy: should the "ipy" command be included for an embedded IPython shell
        :param include_py: should the "py" command be included for an embedded Python shell
        :param intro: introduction to display at startup
        :param multiline_commands: list of commands allowed to accept multi-line input
        :param persistent_history_file: file path to load a persistent cmd2 command history from
        :param persistent_history_length: max number of history items to write
                                          to the persistent history file
        :param shortcuts: dictionary containing shortcuts for commands. If not supplied,
                          then defaults to constants.DEFAULT_SHORTCUTS. If you do not want
                          any shortcuts, pass an empty dictionary.
        :param silence_startup_script: if ``True``, then the startup script's output will be
                                       suppressed. Anything written to stderr will still display.
        :param startup_script: file path to a script to execute at startup
        :param suggest_similar_command: if ``True``, then when a command is not found,
                                        [cmd2.Cmd][] will look for similar commands and suggest them.
        :param terminators: list of characters that terminate a command. These are mainly
                            intended for terminating multiline commands, but will also
                            terminate single-line commands. If not supplied, the default
                            is a semicolon. If your app only contains single-line commands
                            and you want terminators to be treated as literals by the parser,
                            then set this to an empty list.
        :param transcript_files: pass a list of transcript files to be run on initialization.
                                 This allows running transcript tests when ``allow_cli_args``
                                 is ``False``. If ``allow_cli_args`` is ``True`` this parameter
                                 is ignored.
        """
        # Check if py or ipy need to be disabled in this instance
        if not include_py:
            setattr(self, 'do_py', None)  # noqa: B010
        if not include_ipy:
            setattr(self, 'do_ipy', None)  # noqa: B010

        # initialize plugin system
        # needs to be done before we most of the other stuff below
        self._initialize_plugin_system()

        # Configure a few defaults
        self.prompt = Cmd.DEFAULT_PROMPT
        self.intro = intro
        self.use_rawinput = True

        # What to use for standard input
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin

        # What to use for standard output
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout

        # Key used for tab completion
        self.completekey = completekey
        key_bindings = None
        if self.completekey != self.DEFAULT_COMPLETEKEY:
            # Configure prompt_toolkit `KeyBindings` with the custom key for completion
            key_bindings = KeyBindings()

            @key_bindings.add(self.completekey)
            def _(event: Any) -> None:  # pragma: no cover
                """Trigger completion."""
                b = event.current_buffer
                if b.complete_state:
                    b.complete_next()
                else:
                    b.start_completion(select_first=False)

        # Attributes which should NOT be dynamically settable via the set command at runtime
        self.default_to_shell = False  # Attempt to run unrecognized commands as shell commands
        self.allow_redirection = allow_redirection  # Security setting to prevent redirection of stdout

        # Attributes which ARE dynamically settable via the set command at runtime
        self.always_show_hint = False
        self.debug = False
        self.echo = False
        self.editor = Cmd.DEFAULT_EDITOR
        self.feedback_to_output = False  # Do not include nonessentials in >, | output by default (things like timing)
        self.quiet = False  # Do not suppress nonessential output
        self.scripts_add_to_history = True  # Scripts and pyscripts add commands to history
        self.timing = False  # Prints elapsed time for each command

        # The maximum number of CompletionItems to display during tab completion. If the number of completion
        # suggestions exceeds this number, they will be displayed in the typical columnized format and will
        # not include the description value of the CompletionItems.
        self.max_completion_items: int = 50

        # The maximum number of completion results to display in a single column (CompleteStyle.COLUMN).
        # If the number of results exceeds this, CompleteStyle.MULTI_COLUMN will be used.
        self.max_column_completion_results: int = 7

        # A dictionary mapping settable names to their Settable instance
        self._settables: dict[str, Settable] = {}
        self._always_prefix_settables: bool = False

        # CommandSet containers
        self._installed_command_sets: set[CommandSet] = set()
        self._cmd_to_command_sets: dict[str, CommandSet] = {}

        self.build_settables()

        # Use as prompt for multiline commands on the 2nd+ line of input
        self.continuation_prompt: str = '> '

        # Allow access to your application in embedded Python shells and pyscripts via self
        self.self_in_py = False

        # Commands to exclude from the help menu and tab completion
        self.hidden_commands = ['eof', '_relative_run_script']

        # Initialize history from a persistent history file (if present)
        self.persistent_history_file = ''
        self._persistent_history_length = persistent_history_length
        self._initialize_history(persistent_history_file)

        # Initialize prompt-toolkit PromptSession
        self.history_adapter = Cmd2History(self)
        self.completer = Cmd2Completer(self)
        self.lexer = Cmd2Lexer(self)
        self.bottom_toolbar = bottom_toolbar

        self.auto_suggest = None
        if auto_suggest:
            self.auto_suggest = AutoSuggestFromHistory()

        try:
            self.session: PromptSession[str] = PromptSession(
                auto_suggest=self.auto_suggest,
                bottom_toolbar=self.get_bottom_toolbar if self.bottom_toolbar else None,
                complete_in_thread=True,
                complete_style=CompleteStyle.MULTI_COLUMN,
                complete_while_typing=False,
                completer=self.completer,
                history=self.history_adapter,
                key_bindings=key_bindings,
                lexer=self.lexer,
            )
        except (NoConsoleScreenBufferError, AttributeError, ValueError):
            # Fallback to dummy input/output if PromptSession initialization fails.
            # This can happen in some CI environments (like GitHub Actions on Windows)
            # where isatty() is True but there is no real console.
            self.session = PromptSession(
                auto_suggest=self.auto_suggest,
                bottom_toolbar=self.get_bottom_toolbar if self.bottom_toolbar else None,
                complete_in_thread=True,
                complete_style=CompleteStyle.MULTI_COLUMN,
                complete_while_typing=False,
                completer=self.completer,
                history=self.history_adapter,
                input=DummyInput(),
                key_bindings=key_bindings,
                lexer=self.lexer,
                output=DummyOutput(),
            )

        # Commands to exclude from the history command
        self.exclude_from_history = ['eof', 'history']

        # Dictionary of macro names and their values
        self.macros: dict[str, Macro] = {}

        # Keeps track of typed command history in the Python shell
        self._py_history: list[str] = []

        # The name by which Python environments refer to the PyBridge to call app commands
        self.py_bridge_name = 'app'

        # Defines app-specific variables/functions available in Python shells and pyscripts
        self.py_locals: dict[str, Any] = {}

        # True if running inside a Python shell or pyscript, False otherwise
        self._in_py = False

        self.statement_parser: StatementParser = StatementParser(
            terminators=terminators, multiline_commands=multiline_commands, shortcuts=shortcuts
        )

        # Stores results from the last command run to enable usage of results in Python shells and pyscripts
        self.last_result: Any = None

        # Used by run_script command to store current script dir as a LIFO queue to support _relative_run_script command
        self._script_dir: list[str] = []

        # Context manager used to protect critical sections in the main thread from stopping due to a KeyboardInterrupt
        self.sigint_protection: utils.ContextFlag = utils.ContextFlag()

        # If the current command created a process to pipe to, then this will be a ProcReader object.
        # Otherwise it will be None. It's used to know when a pipe process can be killed and/or waited upon.
        self._cur_pipe_proc_reader: utils.ProcReader | None = None

        # Used to keep track of whether we are redirecting or piping output
        self._redirecting = False

        # Used to keep track of whether a continuation prompt is being displayed
        self._at_continuation_prompt = False

        # The multiline command currently being typed which is used to tab complete multiline commands.
        self._multiline_in_progress = ''

        # Characters used to draw a horizontal rule. Should not be blank.
        self.ruler = "─"

        # Set text which prints right before all of the help tables are listed.
        self.doc_leader = ""

        # Set header for table listing documented commands.
        self.doc_header = "Documented Commands"

        # Set header for table listing help topics not related to a command.
        self.misc_header = "Miscellaneous Help Topics"

        # Set header for table listing commands that have no help info.
        self.undoc_header = "Undocumented Commands"

        # If any command has been categorized, then all other documented commands that
        # haven't been categorized will display under this section in the help output.
        self.default_category = "Uncategorized Commands"

        # The error that prints when no help information can be found
        self.help_error = "No help on {}"

        # The error that prints when a non-existent command is run
        self.default_error = "{} is not a recognized command, alias, or macro."

        # If non-empty, this string will be displayed if a broken pipe error occurs
        self.broken_pipe_warning = ''

        # Commands that will run at the beginning of the command loop
        self._startup_commands: list[str] = []

        # Store initial termios settings to restore after each command.
        # This is a faster way of accomplishing what "stty sane" does.
        self._initial_termios_settings = None
        if not sys.platform.startswith('win') and self.stdin.isatty():
            try:
                import io
                import termios

                self._initial_termios_settings = termios.tcgetattr(self.stdin.fileno())
            except (ImportError, io.UnsupportedOperation, termios.error):
                # This can happen if termios isn't available or stdin is a pseudo-TTY
                self._initial_termios_settings = None

        # If a startup script is provided and exists, then execute it in the startup commands
        if startup_script:
            startup_script = os.path.abspath(os.path.expanduser(startup_script))
            if os.path.exists(startup_script):
                script_cmd = f"run_script {su.quote(startup_script)}"
                if silence_startup_script:
                    script_cmd += f" {constants.REDIRECTION_OUTPUT} {os.devnull}"
                self._startup_commands.append(script_cmd)

        # Transcript files to run instead of interactive command loop
        self._transcript_files: list[str] | None = None

        # Check for command line args
        if allow_cli_args:
            parser = argparse_custom.DEFAULT_ARGUMENT_PARSER()
            parser.add_argument('-t', '--test', action="store_true", help='Test against transcript(s) in FILE (wildcards OK)')
            callopts, callargs = parser.parse_known_args()

            # If transcript testing was called for, use other arguments as transcript files
            if callopts.test:
                self._transcript_files = callargs
            # If commands were supplied at invocation, then add them to the command queue
            elif callargs:
                self._startup_commands.extend(callargs)
        elif transcript_files:
            self._transcript_files = transcript_files

        # Set the pager(s) for use when displaying output using a pager
        if sys.platform.startswith('win'):
            self.pager = self.pager_chop = 'more'
        else:
            # Here is the meaning of the various flags we are using with the less command:
            # -S causes lines longer than the screen width to be chopped (truncated) rather than wrapped
            # -R causes ANSI "style" escape sequences to be output in raw form (i.e. colors are displayed)
            # -X disables sending the termcap initialization and deinitialization strings to the terminal
            # -F causes less to automatically exit if the entire file can be displayed on the first screen
            self.pager = 'less -RXF'
            self.pager_chop = 'less -SRXF'

        # This boolean flag stores whether cmd2 will allow clipboard related features
        self.allow_clipboard = allow_clipboard

        # This determines the value returned by cmdloop() when exiting the application
        self.exit_code = 0

        # This flag is set to True when the prompt is displayed and the application is waiting for user input.
        # It is used by async_alert() to determine if it is safe to alert the user.
        self._in_prompt = False
        self._in_prompt_lock = threading.Lock()

        # Commands that have been disabled from use. This is to support commands that are only available
        # during specific states of the application. This dictionary's keys are the command names and its
        # values are DisabledCommand objects.
        self.disabled_commands: dict[str, DisabledCommand] = {}

        # The default key for sorting string results. Its default value performs a case-insensitive alphabetical sort.
        # If natural sorting is preferred, then set this to NATURAL_SORT_KEY.
        # cmd2 uses this key for sorting:
        #     command and category names
        #     alias, macro, settable, and shortcut names
        #     tab completion results when self.matches_sorted is False
        self.default_sort_key: Callable[[str], str] = Cmd.ALPHABETICAL_SORT_KEY

        ############################################################################################################
        # The following variables are used by tab completion functions. They are reset each time complete() is run
        # in _reset_completion_defaults() and it is up to completer functions to set them before returning results.
        ############################################################################################################

        # If True and a single match is returned to complete(), then a space will be appended
        # if the match appears at the end of the line
        self.allow_appended_space = True

        # If True and a single match is returned to complete(), then a closing quote
        # will be added if there is an unmatched opening quote
        self.allow_closing_quote = True

        # An optional hint which prints above tab completion suggestions
        self.completion_hint: str = ''

        # Normally cmd2 uses prompt-toolkit's formatter to columnize the list of completion suggestions.
        # If a custom format is preferred, write the formatted completions to this string. cmd2 will
        # then print it instead of the prompt-toolkit format. ANSI style sequences and newlines are supported
        # when using this value. Even when using formatted_completions, the full matches must still be returned
        # from your completer function. ArgparseCompleter writes its tab completion tables to this string.
        self.formatted_completions: str = ''

        # Used by complete() for prompt-toolkit tab completion
        self.completion_matches: list[str] = []

        # Use this list if you need to display tab completion suggestions that are different than the actual text
        # of the matches. For instance, if you are completing strings that contain a common delimiter and you only
        # want to display the final portion of the matches as the tab completion suggestions. The full matches
        # still must be returned from your completer function. For an example, look at path_complete() which
        # uses this to show only the basename of paths as the suggestions. delimiter_complete() also populates
        # this list. These are ignored if self.formatted_completions is populated.
        self.display_matches: list[str] = []

        # Used by functions like path_complete() and delimiter_complete() to properly
        # quote matches that are completed in a delimited fashion
        self.matches_delimited = False

        # Set to True before returning matches to complete() in cases where matches have already been sorted.
        # If False, then complete() will sort the matches using self.default_sort_key before they are displayed.
        # This does not affect self.formatted_completions.
        self.matches_sorted: bool = False

        # Command parsers for this Cmd instance.
        self._command_parsers: _CommandParsers = _CommandParsers(self)

        # Add functions decorated to be subcommands
        self._register_subcommands(self)

        ############################################################################################################
        # The following code block loads CommandSets, verifies command names, and registers subcommands.
        # This block should appear after all attributes have been created since the registration code
        # depends on them and it's possible a module's on_register() method may need to access some.
        ############################################################################################################
        # Load modular commands
        if command_sets:
            for command_set in command_sets:
                self.register_command_set(command_set)

        if auto_load_commands:
            self._autoload_commands()

        # Verify commands don't have invalid names (like starting with a shortcut)
        for cur_cmd in self.get_all_commands():
            valid, errmsg = self.statement_parser.is_valid_command(cur_cmd)
            if not valid:
                raise ValueError(f"Invalid command name '{cur_cmd}': {errmsg}")

        self.suggest_similar_command = suggest_similar_command
        self.default_suggestion_message = "Did you mean {}?"

        # the current command being executed
        self.current_command: Statement | None = None

    def find_commandsets(self, commandset_type: type[CommandSet], *, subclass_match: bool = False) -> list[CommandSet]:
        """Find all CommandSets that match the provided CommandSet type.

        By default, locates a CommandSet that is an exact type match but may optionally return all CommandSets that
        are sub-classes of the provided type
        :param commandset_type: CommandSet sub-class type to search for
        :param subclass_match: If True, return all sub-classes of provided type, otherwise only search for exact match
        :return: Matching CommandSets
        """
        return [
            cmdset
            for cmdset in self._installed_command_sets
            if type(cmdset) == commandset_type or (subclass_match and isinstance(cmdset, commandset_type))  # noqa: E721
        ]

    def find_commandset_for_command(self, command_name: str) -> CommandSet | None:
        """Find the CommandSet that registered the command name.

        :param command_name: command name to search
        :return: CommandSet that provided the command
        """
        return self._cmd_to_command_sets.get(command_name)

    def _autoload_commands(self) -> None:
        """Load modular command definitions."""
        # Search for all subclasses of CommandSet, instantiate them if they weren't already provided in the constructor
        all_commandset_defs = CommandSet.__subclasses__()
        existing_commandset_types = [type(command_set) for command_set in self._installed_command_sets]

        def load_commandset_by_type(commandset_types: list[type[CommandSet]]) -> None:
            for cmdset_type in commandset_types:
                # check if the type has sub-classes. We will only auto-load leaf class types.
                subclasses = cmdset_type.__subclasses__()
                if subclasses:
                    load_commandset_by_type(subclasses)
                else:
                    init_sig = inspect.signature(cmdset_type.__init__)
                    if not (
                        cmdset_type in existing_commandset_types
                        or len(init_sig.parameters) != 1
                        or 'self' not in init_sig.parameters
                    ):
                        cmdset = cmdset_type()
                        self.register_command_set(cmdset)

        load_commandset_by_type(all_commandset_defs)

    def register_command_set(self, cmdset: CommandSet) -> None:
        """Installs a CommandSet, loading all commands defined in the CommandSet.

        :param cmdset: CommandSet to load
        """
        existing_commandset_types = [type(command_set) for command_set in self._installed_command_sets]
        if type(cmdset) in existing_commandset_types:
            raise CommandSetRegistrationError('CommandSet ' + type(cmdset).__name__ + ' is already installed')

        all_settables = self.settables
        if self.always_prefix_settables:
            if not cmdset.settable_prefix.strip():
                raise CommandSetRegistrationError('CommandSet settable prefix must not be empty')
            for key in cmdset.settables:
                prefixed_name = f'{cmdset.settable_prefix}.{key}'
                if prefixed_name in all_settables:
                    raise CommandSetRegistrationError(f'Duplicate settable: {key}')

        else:
            for key in cmdset.settables:
                if key in all_settables:
                    raise CommandSetRegistrationError(f'Duplicate settable {key} is already registered')

        cmdset.on_register(self)
        methods = cast(
            list[tuple[str, Callable[..., Any]]],
            inspect.getmembers(
                cmdset,
                predicate=lambda meth: isinstance(meth, Callable)  # type: ignore[arg-type]
                and hasattr(meth, '__name__')
                and meth.__name__.startswith(COMMAND_FUNC_PREFIX),
            ),
        )

        default_category = getattr(cmdset, CLASS_ATTR_DEFAULT_HELP_CATEGORY, None)

        installed_attributes = []
        try:
            for cmd_func_name, command_method in methods:
                command = cmd_func_name[len(COMMAND_FUNC_PREFIX) :]

                self._install_command_function(cmd_func_name, command_method, type(cmdset).__name__)
                installed_attributes.append(cmd_func_name)

                completer_func_name = COMPLETER_FUNC_PREFIX + command
                cmd_completer = getattr(cmdset, completer_func_name, None)
                if cmd_completer is not None:
                    self._install_completer_function(command, cmd_completer)
                    installed_attributes.append(completer_func_name)

                help_func_name = HELP_FUNC_PREFIX + command
                cmd_help = getattr(cmdset, help_func_name, None)
                if cmd_help is not None:
                    self._install_help_function(command, cmd_help)
                    installed_attributes.append(help_func_name)

                self._cmd_to_command_sets[command] = cmdset

                if default_category and not hasattr(command_method, constants.CMD_ATTR_HELP_CATEGORY):
                    utils.categorize(command_method, default_category)

            self._installed_command_sets.add(cmdset)

            self._register_subcommands(cmdset)
            cmdset.on_registered()
        except Exception:
            cmdset.on_unregister()
            for attrib in installed_attributes:
                delattr(self, attrib)
            if cmdset in self._installed_command_sets:
                self._installed_command_sets.remove(cmdset)
            if cmdset in self._cmd_to_command_sets.values():
                self._cmd_to_command_sets = {key: val for key, val in self._cmd_to_command_sets.items() if val is not cmdset}
            cmdset.on_unregistered()
            raise

    def _build_parser(
        self,
        parent: CommandParent,
        parser_builder: argparse.ArgumentParser
        | Callable[[], argparse.ArgumentParser]
        | StaticArgParseBuilder
        | ClassArgParseBuilder,
        prog: str,
    ) -> argparse.ArgumentParser:
        """Build argument parser for a command/subcommand.

        :param parent: CommandParent object which owns the command using the parser.
                       When parser_builder is a classmethod, this function passes
                       parent's class to it.
        :param parser_builder: means used to build the parser
        :param prog: prog value to set in new parser
        :return: new parser
        :raises TypeError: if parser_builder is invalid type
        """
        if isinstance(parser_builder, staticmethod):
            parser = parser_builder.__func__()
        elif isinstance(parser_builder, classmethod):
            parser = parser_builder.__func__(parent.__class__)
        elif callable(parser_builder):
            parser = parser_builder()
        elif isinstance(parser_builder, argparse.ArgumentParser):
            parser = copy.deepcopy(parser_builder)
        else:
            raise TypeError(f"Invalid type for parser_builder: {type(parser_builder)}")

        argparse_custom.set_parser_prog(parser, prog)

        return parser

    def _install_command_function(self, command_func_name: str, command_method: CommandFunc, context: str = '') -> None:
        """Install a new command function into the CLI.

        :param command_func_name: name of command function to add
                                  This points to the command method and may differ from the method's
                                  name if it's being used as a synonym. (e.g. do_exit = do_quit)
        :param command_method: the actual command method which runs when the command function is called
        :param context: optional info to provide in error message. (e.g. class this function belongs to)
        :raises CommandSetRegistrationError: if the command function fails to install
        """
        # command_func_name must begin with COMMAND_FUNC_PREFIX to be identified as a command by cmd2.
        if not command_func_name.startswith(COMMAND_FUNC_PREFIX):
            raise CommandSetRegistrationError(f"{command_func_name} does not begin with '{COMMAND_FUNC_PREFIX}'")

        # command_method must start with COMMAND_FUNC_PREFIX for use in self._command_parsers.
        if not command_method.__name__.startswith(COMMAND_FUNC_PREFIX):
            raise CommandSetRegistrationError(f"{command_method.__name__} does not begin with '{COMMAND_FUNC_PREFIX}'")

        command = command_func_name[len(COMMAND_FUNC_PREFIX) :]

        # Make sure command function doesn't share name with existing attribute
        if hasattr(self, command_func_name):
            raise CommandSetRegistrationError(f'Attribute already exists: {command_func_name} ({context})')

        # Check if command has an invalid name
        valid, errmsg = self.statement_parser.is_valid_command(command)
        if not valid:
            raise CommandSetRegistrationError(f"Invalid command name '{command}': {errmsg}")

        # Check if command shares a name with an alias
        if command in self.aliases:
            self.pwarning(f"Deleting alias '{command}' because it shares its name with a new command")
            del self.aliases[command]

        # Check if command shares a name with a macro
        if command in self.macros:
            self.pwarning(f"Deleting macro '{command}' because it shares its name with a new command")
            del self.macros[command]

        setattr(self, command_func_name, command_method)

    def _install_completer_function(self, cmd_name: str, cmd_completer: CompleterFunc) -> None:
        completer_func_name = COMPLETER_FUNC_PREFIX + cmd_name

        if hasattr(self, completer_func_name):
            raise CommandSetRegistrationError(f'Attribute already exists: {completer_func_name}')
        setattr(self, completer_func_name, cmd_completer)

    def _install_help_function(self, cmd_name: str, cmd_help: Callable[..., None]) -> None:
        help_func_name = HELP_FUNC_PREFIX + cmd_name

        if hasattr(self, help_func_name):
            raise CommandSetRegistrationError(f'Attribute already exists: {help_func_name}')
        setattr(self, help_func_name, cmd_help)

    def unregister_command_set(self, cmdset: CommandSet) -> None:
        """Uninstalls a CommandSet and unloads all associated commands.

        :param cmdset: CommandSet to uninstall
        """
        if cmdset in self._installed_command_sets:
            self._check_uninstallable(cmdset)
            cmdset.on_unregister()
            self._unregister_subcommands(cmdset)

            methods: list[tuple[str, Callable[..., Any]]] = inspect.getmembers(
                cmdset,
                predicate=lambda meth: isinstance(meth, Callable)  # type: ignore[arg-type]
                and hasattr(meth, '__name__')
                and meth.__name__.startswith(COMMAND_FUNC_PREFIX),
            )

            for cmd_func_name, command_method in methods:
                command = cmd_func_name[len(COMMAND_FUNC_PREFIX) :]

                # Enable the command before uninstalling it to make sure we remove both
                # the real functions and the ones used by the DisabledCommand object.
                if command in self.disabled_commands:
                    self.enable_command(command)

                if command in self._cmd_to_command_sets:
                    del self._cmd_to_command_sets[command]

                # Only remove the parser if this is the actual
                # command since command synonyms don't own it.
                if cmd_func_name == command_method.__name__:
                    self._command_parsers.remove(command_method)

                if hasattr(self, COMPLETER_FUNC_PREFIX + command):
                    delattr(self, COMPLETER_FUNC_PREFIX + command)
                if hasattr(self, HELP_FUNC_PREFIX + command):
                    delattr(self, HELP_FUNC_PREFIX + command)

                delattr(self, cmd_func_name)

            cmdset.on_unregistered()
            self._installed_command_sets.remove(cmdset)

    def _check_uninstallable(self, cmdset: CommandSet) -> None:
        def check_parser_uninstallable(parser: argparse.ArgumentParser) -> None:
            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    for subparser in action.choices.values():
                        attached_cmdset = getattr(subparser, constants.PARSER_ATTR_COMMANDSET, None)
                        if attached_cmdset is not None and attached_cmdset is not cmdset:
                            raise CommandSetRegistrationError(
                                'Cannot uninstall CommandSet when another CommandSet depends on it'
                            )
                        check_parser_uninstallable(subparser)
                    break

        methods: list[tuple[str, Callable[..., Any]]] = inspect.getmembers(
            cmdset,
            predicate=lambda meth: isinstance(meth, Callable)  # type: ignore[arg-type]
            and hasattr(meth, '__name__')
            and meth.__name__.startswith(COMMAND_FUNC_PREFIX),
        )

        for cmd_func_name, command_method in methods:
            # We only need to check if it's safe to remove the parser if this
            # is the actual command since command synonyms don't own it.
            if cmd_func_name == command_method.__name__:
                command_parser = self._command_parsers.get(command_method)
                if command_parser is not None:
                    check_parser_uninstallable(command_parser)

    def _register_subcommands(self, cmdset: Union[CommandSet, 'Cmd']) -> None:
        """Register subcommands with their base command.

        :param cmdset: CommandSet or cmd2.Cmd subclass containing subcommands
        """
        if not (cmdset is self or cmdset in self._installed_command_sets):
            raise CommandSetRegistrationError('Cannot register subcommands with an unregistered CommandSet')

        # find methods that have the required attributes necessary to be recognized as a sub-command
        methods = inspect.getmembers(
            cmdset,
            predicate=lambda meth: isinstance(meth, Callable)  # type: ignore[arg-type]
            and hasattr(meth, constants.SUBCMD_ATTR_NAME)
            and hasattr(meth, constants.SUBCMD_ATTR_COMMAND)
            and hasattr(meth, constants.CMD_ATTR_ARGPARSER),
        )

        # iterate through all matching methods
        for _method_name, method in methods:
            subcommand_name: str = getattr(method, constants.SUBCMD_ATTR_NAME)
            full_command_name: str = getattr(method, constants.SUBCMD_ATTR_COMMAND)
            subcmd_parser_builder = getattr(method, constants.CMD_ATTR_ARGPARSER)

            subcommand_valid, errmsg = self.statement_parser.is_valid_command(subcommand_name, is_subcommand=True)
            if not subcommand_valid:
                raise CommandSetRegistrationError(f'Subcommand {subcommand_name} is not valid: {errmsg}')

            command_tokens = full_command_name.split()
            command_name = command_tokens[0]
            subcommand_names = command_tokens[1:]

            # Search for the base command function and verify it has an argparser defined
            if command_name in self.disabled_commands:
                command_func = self.disabled_commands[command_name].command_function
            else:
                command_func = self.cmd_func(command_name)

            if command_func is None:
                raise CommandSetRegistrationError(f"Could not find command '{command_name}' needed by subcommand: {method}")
            command_parser = self._command_parsers.get(command_func)
            if command_parser is None:
                raise CommandSetRegistrationError(
                    f"Could not find argparser for command '{command_name}' needed by subcommand: {method}"
                )

            def find_subcommand(action: argparse.ArgumentParser, subcmd_names: list[str]) -> argparse.ArgumentParser:
                if not subcmd_names:
                    return action
                cur_subcmd = subcmd_names.pop(0)
                for sub_action in action._actions:
                    if isinstance(sub_action, argparse._SubParsersAction):
                        for choice_name, choice in sub_action.choices.items():
                            if choice_name == cur_subcmd:
                                return find_subcommand(choice, subcmd_names)
                        break
                raise CommandSetRegistrationError(f"Could not find subcommand '{action}'")

            target_parser = find_subcommand(command_parser, subcommand_names)

            # Create the subcommand parser and configure it
            subcmd_parser = self._build_parser(cmdset, subcmd_parser_builder, f'{command_name} {subcommand_name}')
            if subcmd_parser.description is None and method.__doc__:
                subcmd_parser.description = strip_doc_annotations(method.__doc__)

            # Set the subcommand handler
            defaults = {constants.NS_ATTR_SUBCMD_HANDLER: method}
            subcmd_parser.set_defaults(**defaults)

            # Set what instance the handler is bound to
            setattr(subcmd_parser, constants.PARSER_ATTR_COMMANDSET, cmdset)

            # Find the argparse action that handles subcommands
            for action in target_parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    # Get the kwargs for add_parser()
                    add_parser_kwargs = getattr(method, constants.SUBCMD_ATTR_ADD_PARSER_KWARGS, {})

                    # Use add_parser to register the subcommand name and any aliases
                    action.add_parser(subcommand_name, **add_parser_kwargs)

                    # Replace the parser created by add_parser() with our pre-configured one
                    action._name_parser_map[subcommand_name] = subcmd_parser

                    # Also remap any aliases to our pre-configured parser
                    for alias in add_parser_kwargs.get("aliases", []):
                        action._name_parser_map[alias] = subcmd_parser

                    break

    def _unregister_subcommands(self, cmdset: Union[CommandSet, 'Cmd']) -> None:
        """Unregister subcommands from their base command.

        :param cmdset: CommandSet containing subcommands
        """
        if not (cmdset is self or cmdset in self._installed_command_sets):
            raise CommandSetRegistrationError('Cannot unregister subcommands with an unregistered CommandSet')

        # find methods that have the required attributes necessary to be recognized as a sub-command
        methods = inspect.getmembers(
            cmdset,
            predicate=lambda meth: isinstance(meth, Callable)  # type: ignore[arg-type]
            and hasattr(meth, constants.SUBCMD_ATTR_NAME)
            and hasattr(meth, constants.SUBCMD_ATTR_COMMAND)
            and hasattr(meth, constants.CMD_ATTR_ARGPARSER),
        )

        # iterate through all matching methods
        for _method_name, method in methods:
            subcommand_name = getattr(method, constants.SUBCMD_ATTR_NAME)
            command_name = getattr(method, constants.SUBCMD_ATTR_COMMAND)

            # Search for the base command function and verify it has an argparser defined
            if command_name in self.disabled_commands:
                command_func = self.disabled_commands[command_name].command_function
            else:
                command_func = self.cmd_func(command_name)

            if command_func is None:  # pragma: no cover
                # This really shouldn't be possible since _register_subcommands would prevent this from happening
                # but keeping in case it does for some strange reason
                raise CommandSetRegistrationError(f"Could not find command '{command_name}' needed by subcommand: {method}")
            command_parser = self._command_parsers.get(command_func)
            if command_parser is None:  # pragma: no cover
                # This really shouldn't be possible since _register_subcommands would prevent this from happening
                # but keeping in case it does for some strange reason
                raise CommandSetRegistrationError(
                    f"Could not find argparser for command '{command_name}' needed by subcommand: {method}"
                )

            for action in command_parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    action.remove_parser(subcommand_name)  # type: ignore[attr-defined]
                    break

    @property
    def always_prefix_settables(self) -> bool:
        """Flags whether CommandSet settable values should always be prefixed.

        :return: True if CommandSet settable values will always be prefixed. False if not.
        """
        return self._always_prefix_settables

    @always_prefix_settables.setter
    def always_prefix_settables(self, new_value: bool) -> None:
        """Set whether CommandSet settable values should always be prefixed.

        :param new_value: True if CommandSet settable values should always be prefixed. False if not.
        :raises ValueError: If a registered CommandSet does not have a defined prefix
        """
        if not self._always_prefix_settables and new_value:
            for cmd_set in self._installed_command_sets:
                if not cmd_set.settable_prefix:
                    raise ValueError(
                        f'Cannot force settable prefixes. CommandSet {cmd_set.__class__.__name__} does '
                        f'not have a settable prefix defined.'
                    )
        self._always_prefix_settables = new_value

    @property
    def settables(self) -> Mapping[str, Settable]:
        """Get all available user-settable attributes. This includes settables defined in installed CommandSets.

        :return: Mapping from attribute-name to Settable of all user-settable attributes from
        """
        all_settables = dict(self._settables)
        for cmd_set in self._installed_command_sets:
            cmdset_settables = cmd_set.settables
            for settable_name, settable in cmdset_settables.items():
                if self.always_prefix_settables:
                    all_settables[f'{cmd_set.settable_prefix}.{settable_name}'] = settable
                else:
                    all_settables[settable_name] = settable
        return all_settables

    def add_settable(self, settable: Settable) -> None:
        """Add a settable parameter to ``self.settables``.

        :param settable: Settable object being added
        """
        if not self.always_prefix_settables and settable.name in self.settables and settable.name not in self._settables:
            raise KeyError(f'Duplicate settable: {settable.name}')
        self._settables[settable.name] = settable

    def remove_settable(self, name: str) -> None:
        """Remove a settable parameter from ``self.settables``.

        :param name: name of the settable being removed
        :raises KeyError: if the Settable matches this name
        """
        try:
            del self._settables[name]
        except KeyError as exc:
            raise KeyError(name + " is not a settable parameter") from exc

    def build_settables(self) -> None:
        """Create the dictionary of user-settable parameters."""

        def get_allow_style_choices(_cli_self: Cmd) -> list[str]:
            """Tab complete allow_style values."""
            return [val.name.lower() for val in ru.AllowStyle]

        def allow_style_type(value: str) -> ru.AllowStyle:
            """Convert a string value into an ru.AllowStyle."""
            try:
                return ru.AllowStyle[value.upper()]
            except KeyError as ex:
                raise ValueError(
                    f"must be {ru.AllowStyle.ALWAYS}, {ru.AllowStyle.NEVER}, or {ru.AllowStyle.TERMINAL} (case-insensitive)"
                ) from ex

        self.add_settable(
            Settable(
                'allow_style',
                allow_style_type,
                'Allow ANSI text style sequences in output (valid values: '
                f'{ru.AllowStyle.ALWAYS}, {ru.AllowStyle.NEVER}, {ru.AllowStyle.TERMINAL})',
                self,
                choices_provider=cast(ChoicesProviderFunc, get_allow_style_choices),
            )
        )

        self.add_settable(
            Settable('always_show_hint', bool, 'Display tab completion hint even when completion suggestions print', self)
        )
        self.add_settable(Settable('debug', bool, "Show full traceback on exception", self))
        self.add_settable(Settable('echo', bool, "Echo command issued into output", self))
        self.add_settable(Settable('editor', str, "Program used by 'edit'", self))
        self.add_settable(Settable('feedback_to_output', bool, "Include nonessentials in '|' and '>' results", self))
        self.add_settable(
            Settable('max_completion_items', int, "Maximum number of CompletionItems to display during tab completion", self)
        )
        self.add_settable(
            Settable(
                'max_column_completion_results',
                int,
                "Maximum number of completion results to display in a single column",
                self,
            )
        )
        self.add_settable(Settable('quiet', bool, "Don't print nonessential feedback", self))
        self.add_settable(Settable('scripts_add_to_history', bool, 'Scripts and pyscripts add commands to history', self))
        self.add_settable(Settable('timing', bool, "Report execution times", self))

    # -----  Methods related to presenting output to the user -----

    @property
    def allow_style(self) -> ru.AllowStyle:
        """Read-only property needed to support do_set when it reads allow_style."""
        return ru.ALLOW_STYLE

    @allow_style.setter
    def allow_style(self, new_val: ru.AllowStyle) -> None:
        """Setter property needed to support do_set when it updates allow_style."""
        ru.ALLOW_STYLE = new_val

    def _completion_supported(self) -> bool:
        """Return whether tab completion is supported."""
        return self.use_rawinput and bool(self.completekey)

    @property
    def visible_prompt(self) -> str:
        """Read-only property to get the visible prompt with any ANSI style sequences stripped.

        Used by transcript testing to make it easier and more reliable when users are doing things like
        coloring the prompt.

        :return: the stripped prompt
        """
        return su.strip_style(self.prompt)

    def print_to(
        self,
        file: IO[str],
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: StyleType | None = None,
        soft_wrap: bool = True,
        emoji: bool = False,
        markup: bool = False,
        highlight: bool = False,
        rich_print_kwargs: RichPrintKwargs | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Print objects to a given file stream.

        This method is configured for general-purpose printing. By default, it enables
        soft wrap and disables Rich's automatic detection for markup, emoji, and highlighting.
        These defaults can be overridden by passing explicit keyword arguments.

        :param file: file stream being written to
        :param objects: objects to print
        :param sep: string to write between printed text. Defaults to " ".
        :param end: string to write at end of printed text. Defaults to a newline.
        :param style: optional style to apply to output
        :param soft_wrap: Enable soft wrap mode. Defaults to True.
                          If True, text that doesn't fit will run on to the following line,
                          just like with print(). This is useful for raw text and logs.
                          If False, Rich wraps text to fit the terminal width.
                          Set this to False when printing structured Renderables like
                          Tables, Panels, or Columns to ensure they render as expected.
                          For example, when soft_wrap is True Panels truncate text
                          which is wider than the terminal.
        :param emoji: If True, Rich will replace emoji codes (e.g., :smiley:) with their
                      corresponding Unicode characters. Defaults to False.
        :param markup: If True, Rich will interpret strings with tags (e.g., [bold]hello[/bold])
                       as styled output. Defaults to False.
        :param highlight: If True, Rich will automatically apply highlighting to elements within
                          strings, such as common Python data types like numbers, booleans, or None.
                          This is particularly useful when pretty printing objects like lists and
                          dictionaries to display them in color. Defaults to False.
        :param rich_print_kwargs: optional additional keyword arguments to pass to Rich's Console.print().
        :param kwargs: Arbitrary keyword arguments. This allows subclasses to extend the signature of this
                       method and still call `super()` without encountering unexpected keyword argument errors.
                       These arguments are not passed to Rich's Console.print().

        See the Rich documentation for more details on emoji codes, markup tags, and highlighting.
        """
        prepared_objects = ru.prepare_objects_for_rendering(*objects)

        try:
            Cmd2GeneralConsole(file).print(
                *prepared_objects,
                sep=sep,
                end=end,
                style=style,
                soft_wrap=soft_wrap,
                emoji=emoji,
                markup=markup,
                highlight=highlight,
                **(rich_print_kwargs if rich_print_kwargs is not None else {}),
            )
        except BrokenPipeError:
            # This occurs if a command's output is being piped to another
            # process which closes the pipe before the command is finished
            # writing. If you would like your application to print a
            # warning message, then set the broken_pipe_warning attribute
            # to the message you want printed.
            if self.broken_pipe_warning and file != sys.stderr:
                Cmd2GeneralConsole(sys.stderr).print(self.broken_pipe_warning)

    def poutput(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: StyleType | None = None,
        soft_wrap: bool = True,
        emoji: bool = False,
        markup: bool = False,
        highlight: bool = False,
        rich_print_kwargs: RichPrintKwargs | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Print objects to self.stdout.

        For details on the parameters, refer to the `print_to` method documentation.
        """
        self.print_to(
            self.stdout,
            *objects,
            sep=sep,
            end=end,
            style=style,
            soft_wrap=soft_wrap,
            emoji=emoji,
            markup=markup,
            highlight=highlight,
            rich_print_kwargs=rich_print_kwargs,
        )

    def perror(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: StyleType | None = Cmd2Style.ERROR,
        soft_wrap: bool = True,
        emoji: bool = False,
        markup: bool = False,
        highlight: bool = False,
        rich_print_kwargs: RichPrintKwargs | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Print objects to sys.stderr.

        :param style: optional style to apply to output. Defaults to Cmd2Style.ERROR.

        For details on the other parameters, refer to the `print_to` method documentation.
        """
        self.print_to(
            sys.stderr,
            *objects,
            sep=sep,
            end=end,
            style=style,
            soft_wrap=soft_wrap,
            emoji=emoji,
            markup=markup,
            highlight=highlight,
            rich_print_kwargs=rich_print_kwargs,
        )

    def psuccess(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        soft_wrap: bool = True,
        emoji: bool = False,
        markup: bool = False,
        highlight: bool = False,
        rich_print_kwargs: RichPrintKwargs | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Wrap poutput, but apply Cmd2Style.SUCCESS.

        For details on the parameters, refer to the `print_to` method documentation.
        """
        self.poutput(
            *objects,
            sep=sep,
            end=end,
            style=Cmd2Style.SUCCESS,
            soft_wrap=soft_wrap,
            emoji=emoji,
            markup=markup,
            highlight=highlight,
            rich_print_kwargs=rich_print_kwargs,
        )

    def pwarning(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        soft_wrap: bool = True,
        emoji: bool = False,
        markup: bool = False,
        highlight: bool = False,
        rich_print_kwargs: RichPrintKwargs | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Wrap perror, but apply Cmd2Style.WARNING.

        For details on the parameters, refer to the `print_to` method documentation.
        """
        self.perror(
            *objects,
            sep=sep,
            end=end,
            style=Cmd2Style.WARNING,
            soft_wrap=soft_wrap,
            emoji=emoji,
            markup=markup,
            highlight=highlight,
            rich_print_kwargs=rich_print_kwargs,
        )

    def pexcept(
        self,
        exception: BaseException,
        *,
        console: Console | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Print an exception to sys.stderr.

        If `debug` is true, a full traceback is also printed, if one exists.

        :param exception: the exception to be printed.
        :param console: optional Rich console to use for printing. If None, a new Cmd2ExceptionConsole
                        instance is created which writes to sys.stderr.
        :param kwargs: Arbitrary keyword arguments. This allows subclasses to extend the signature of this
                       method and still call `super()` without encountering unexpected keyword argument errors.
        """
        if console is None:
            console = Cmd2ExceptionConsole(sys.stderr)

        # Only print a traceback if we're in debug mode and one exists.
        if self.debug and sys.exc_info() != (None, None, None):
            traceback = Traceback(
                width=None,  # Use all available width
                code_width=None,  # Use all available width
                show_locals=True,
                max_frames=0,  # 0 means full traceback.
                word_wrap=True,  # Wrap long lines of code instead of truncate
            )
            console.print(traceback)
            console.print()
            return

        # Print the exception in the same style Rich uses after a traceback.
        exception_str = str(exception)

        if exception_str:
            highlighter = ReprHighlighter()

            final_msg = Text.assemble(
                (f"{type(exception).__name__}: ", "traceback.exc_type"),
                highlighter(exception_str),
            )
        else:
            final_msg = Text(f"{type(exception).__name__}", style="traceback.exc_type")

        # If not in debug mode and the 'debug' setting is available,
        # inform the user how to enable full tracebacks.
        if not self.debug and 'debug' in self.settables:
            help_msg = Text.assemble(
                "\n\n",
                ("To enable full traceback, run the following command: ", Cmd2Style.WARNING),
                ("set debug true", Cmd2Style.COMMAND_LINE),
            )
            final_msg.append(help_msg)

        console.print(final_msg)
        console.print()

    def pfeedback(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: StyleType | None = None,
        soft_wrap: bool = True,
        emoji: bool = False,
        markup: bool = False,
        highlight: bool = False,
        rich_print_kwargs: RichPrintKwargs | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Print nonessential feedback.

        The output can be silenced with the `quiet` setting and its inclusion in redirected output
        is controlled by the `feedback_to_output` setting.

        For details on the parameters, refer to the `print_to` method documentation.
        """
        if not self.quiet:
            if self.feedback_to_output:
                self.poutput(
                    *objects,
                    sep=sep,
                    end=end,
                    style=style,
                    soft_wrap=soft_wrap,
                    emoji=emoji,
                    markup=markup,
                    highlight=highlight,
                    rich_print_kwargs=rich_print_kwargs,
                )
            else:
                self.perror(
                    *objects,
                    sep=sep,
                    end=end,
                    style=style,
                    soft_wrap=soft_wrap,
                    emoji=emoji,
                    markup=markup,
                    highlight=highlight,
                    rich_print_kwargs=rich_print_kwargs,
                )

    def ppaged(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: StyleType | None = None,
        chop: bool = False,
        soft_wrap: bool = True,
        emoji: bool = False,
        markup: bool = False,
        highlight: bool = False,
        rich_print_kwargs: RichPrintKwargs | None = None,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Print output using a pager.

        A pager is used when the terminal is interactive and may exit immediately if the output
        fits on the screen. A pager is not used inside a script (Python or text) or when output is
        redirected or piped, and in these cases, output is sent to `poutput`.

        :param chop: True -> causes lines longer than the screen width to be chopped (truncated) rather than wrapped
                              - truncated text is still accessible by scrolling with the right & left arrow keys
                              - chopping is ideal for displaying wide tabular data as is done in utilities like pgcli
                     False -> causes lines longer than the screen width to wrap to the next line
                              - wrapping is ideal when you want to keep users from having to use horizontal scrolling
                     WARNING: On Windows, the text always wraps regardless of what the chop argument is set to
        :param soft_wrap: Enable soft wrap mode. If True, lines of text will not be word-wrapped or cropped to
                          fit the terminal width. Defaults to True.

                          Note: If chop is True and a pager is used, soft_wrap is automatically set to True to
                          prevent wrapping and allow for horizontal scrolling.

        For details on the other parameters, refer to the `print_to` method documentation.
        """
        # Detect if we are running within an interactive terminal.
        # Don't try to use the pager when being run by a continuous integration system like Jenkins + pexpect.
        functional_terminal = (
            self.stdin.isatty()
            and self.stdout.isatty()
            and (sys.platform.startswith('win') or os.environ.get('TERM') is not None)
        )

        # A pager application blocks, so only run one if not redirecting or running a script (either text or Python).
        can_block = not (self._redirecting or self.in_pyscript() or self.in_script())

        # Check if we are outputting to a pager.
        if functional_terminal and can_block:
            prepared_objects = ru.prepare_objects_for_rendering(*objects)

            # Chopping overrides soft_wrap
            if chop:
                soft_wrap = True

            # Generate the bytes to send to the pager
            console = Cmd2GeneralConsole(self.stdout)
            with console.capture() as capture:
                console.print(
                    *prepared_objects,
                    sep=sep,
                    end=end,
                    style=style,
                    soft_wrap=soft_wrap,
                    emoji=emoji,
                    markup=markup,
                    highlight=highlight,
                    **(rich_print_kwargs if rich_print_kwargs is not None else {}),
                )
            output_bytes = capture.get().encode('utf-8', 'replace')

            # Prevent KeyboardInterrupts while in the pager. The pager application will
            # still receive the SIGINT since it is in the same process group as us.
            with self.sigint_protection:
                import subprocess

                pipe_proc = subprocess.Popen(  # noqa: S602
                    self.pager_chop if chop else self.pager,
                    shell=True,
                    stdin=subprocess.PIPE,
                    stdout=self.stdout,
                )
                pipe_proc.communicate(output_bytes)

                # If the pager was killed (e.g. SIGKILL), the terminal might be in a bad state.
                # Attempt to restore terminal settings and foreground process group.
                if self._initial_termios_settings is not None and self.stdin.isatty():  # type: ignore[unreachable]
                    try:  # type: ignore[unreachable]
                        import signal
                        import termios

                        # Ensure we are in the foreground process group
                        if hasattr(os, 'tcsetpgrp') and hasattr(os, 'getpgrp'):
                            # Ignore SIGTTOU to avoid getting stopped when calling tcsetpgrp from background
                            old_handler = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
                            try:
                                os.tcsetpgrp(self.stdin.fileno(), os.getpgrp())
                            finally:
                                signal.signal(signal.SIGTTOU, old_handler)

                        # Restore terminal attributes
                        if self._initial_termios_settings is not None:
                            termios.tcsetattr(self.stdin.fileno(), termios.TCSANOW, self._initial_termios_settings)

                    except (OSError, termios.error):
                        pass

        else:
            self.poutput(
                *objects,
                sep=sep,
                end=end,
                style=style,
                soft_wrap=soft_wrap,
                emoji=emoji,
                markup=markup,
                highlight=highlight,
                rich_print_kwargs=rich_print_kwargs,
            )

    # -----  Methods related to tab completion -----

    def _reset_completion_defaults(self) -> None:
        """Reset tab completion settings.

        Needs to be called each time prompt-toolkit runs tab completion.
        """
        self.allow_appended_space = True
        self.allow_closing_quote = True
        self.completion_hint = ''
        self.formatted_completions = ''
        self.completion_matches = []
        self.display_matches = []
        self.completion_header = ''
        self.matches_delimited = False
        self.matches_sorted = False

    def get_bottom_toolbar(self) -> list[str | tuple[str, str]] | None:
        """Get the bottom toolbar content.

        If self.bottom_toolbar is False, returns None.

        Otherwise returns tokens for prompt-toolkit to populate in the bottom toolbar.

        NOTE: This content can extend over multiple lines.  However we would recommend
        keeping it to a single line or two lines maximum.
        """
        if self.bottom_toolbar:
            import datetime
            import shutil

            # Get the current time in ISO format with 0.01s precision
            dt = datetime.datetime.now(datetime.timezone.utc).astimezone()
            now = dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-4] + dt.strftime('%z')
            left_text = sys.argv[0]

            # Get terminal width to calculate padding for right-alignment
            cols, _ = shutil.get_terminal_size()
            padding_size = cols - len(left_text) - len(now) - 1
            if padding_size < 1:
                padding_size = 1
            padding = ' ' * padding_size

            # Return formatted text for prompt-toolkit
            return [
                ('ansigreen', left_text),
                ('', padding),
                ('ansicyan', now),
            ]
        return None

    def get_rprompt(self) -> str | FormattedText | None:
        """Provide text to populate prompt-toolkit right prompt with.

        Override this if you want a right-prompt displaying contetual information useful for your application.
        This could be information like current Git branch, time, current working directory, etc that is displayed
        without cluttering the main input area.

        :return: any type of formatted text to display as the right prompt
        """
        return None

    def tokens_for_completion(self, line: str, begidx: int, endidx: int) -> tuple[list[str], list[str]]:
        """Get all tokens through the one being completed, used by tab completion functions.

        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :return: A 2 item tuple where the items are
                 **On Success**
                 - tokens: list of unquoted tokens - this is generally the list needed for tab completion functions
                 - raw_tokens: list of tokens with any quotes preserved = this can be used to know if a token was quoted
                 or is missing a closing quote
                 Both lists are guaranteed to have at least 1 item. The last item in both lists is the token being tab
                 completed
                 **On Failure**
                 - Two empty lists
        """
        import copy

        unclosed_quote = ''
        quotes_to_try = copy.copy(constants.QUOTES)

        tmp_line = line[:endidx]
        tmp_endidx = endidx

        # Parse the line into tokens
        while True:
            try:
                initial_tokens = shlex_split(tmp_line[:tmp_endidx])

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
                else:  # pragma: no cover
                    # The parsing error is not caused by unclosed quotes.
                    # Return empty lists since this means the line is malformed.
                    return [], []

        # Further split tokens on punctuation characters
        raw_tokens = self.statement_parser.split_on_punctuation(initial_tokens)

        # Save the unquoted tokens
        tokens = [su.strip_quotes(cur_token) for cur_token in raw_tokens]

        # If the token being completed had an unclosed quote, we need
        # to remove the closing quote that was added in order for it
        # to match what was on the command line.
        if unclosed_quote:
            raw_tokens[-1] = raw_tokens[-1][:-1]

        return tokens, raw_tokens

    def basic_complete(
        self,
        text: str,
        line: str,  # noqa: ARG002
        begidx: int,  # noqa: ARG002
        endidx: int,  # noqa: ARG002
        match_against: Iterable[str],
    ) -> list[str]:
        """Tab completion function that matches against a list of strings without considering line contents or cursor position.

        The args required by this function are defined in the header of Python's cmd.py.

        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param match_against: the strings being matched against
        :return: a list of possible tab completions
        """
        return [cur_match for cur_match in match_against if cur_match.startswith(text)]

    def delimiter_complete(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
        match_against: Iterable[str],
        delimiter: str,
    ) -> list[str]:
        """Perform tab completion against a list but each match is split on a delimiter.

        Only the portion of the match being tab completed is shown as the completion suggestions.
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

        :param text: the string prefix we are attempting to match (all matches must begin with it)
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

    def flag_based_complete(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
        flag_dict: dict[str, Iterable[str] | CompleterFunc],
        *,
        all_else: None | Iterable[str] | CompleterFunc = None,
    ) -> list[str]:
        """Tab completes based on a particular flag preceding the token being completed.

        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param flag_dict: dictionary whose structure is the following:
                          `keys` - flags (ex: -c, --create) that result in tab completion for the next argument in the
                          command line
                          `values` - there are two types of values:
                          1. iterable list of strings to match against (dictionaries, lists, etc.)
                          2. function that performs tab completion (ex: path_complete)
        :param all_else: an optional parameter for tab completing any token that isn't preceded by a flag in flag_dict
        :return: a list of possible tab completions
        """
        # Get all tokens through the one being completed
        tokens, _ = self.tokens_for_completion(line, begidx, endidx)
        if not tokens:  # pragma: no cover
            return []

        completions_matches = []
        match_against = all_else

        # Must have at least 2 args for a flag to precede the token being completed
        if len(tokens) > 1:
            flag = tokens[-2]
            if flag in flag_dict:
                match_against = flag_dict[flag]

        # Perform tab completion using an Iterable
        if isinstance(match_against, Iterable):
            completions_matches = self.basic_complete(text, line, begidx, endidx, match_against)

        # Perform tab completion using a function
        elif callable(match_against):
            completions_matches = match_against(text, line, begidx, endidx)

        return completions_matches

    def index_based_complete(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
        index_dict: Mapping[int, Iterable[str] | CompleterFunc],
        *,
        all_else: Iterable[str] | CompleterFunc | None = None,
    ) -> list[str]:
        """Tab completes based on a fixed position in the input string.

        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param index_dict: dictionary whose structure is the following:
                           `keys` - 0-based token indexes into command line that determine which tokens perform tab
                           completion
                           `values` - there are two types of values:
                           1. iterable list of strings to match against (dictionaries, lists, etc.)
                           2. function that performs tab completion (ex: path_complete)
        :param all_else: an optional parameter for tab completing any token that isn't at an index in index_dict
        :return: a list of possible tab completions
        """
        # Get all tokens through the one being completed
        tokens, _ = self.tokens_for_completion(line, begidx, endidx)
        if not tokens:  # pragma: no cover
            return []

        matches = []

        # Get the index of the token being completed
        index = len(tokens) - 1

        # Check if token is at an index in the dictionary
        match_against: Iterable[str] | CompleterFunc | None
        match_against = index_dict.get(index, all_else)

        # Perform tab completion using a Iterable
        if isinstance(match_against, Iterable):
            matches = self.basic_complete(text, line, begidx, endidx, match_against)

        # Perform tab completion using a function
        elif callable(match_against):
            matches = match_against(text, line, begidx, endidx)

        return matches

    def path_complete(
        self,
        text: str,
        line: str,
        begidx: int,  # noqa: ARG002
        endidx: int,
        *,
        path_filter: Callable[[str], bool] | None = None,
    ) -> list[str]:
        """Perform completion of local file system paths.

        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param path_filter: optional filter function that determines if a path belongs in the results
                            this function takes a path as its argument and returns True if the path should
                            be kept in the results
        :return: a list of possible tab completions
        """

        # Used to complete ~ and ~user strings
        def complete_users() -> list[str]:
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

            if users:
                # We are returning ~user strings that resolve to directories,
                # so don't append a space or quote in the case of a single result.
                self.allow_appended_space = False
                self.allow_closing_quote = False

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
            # Purposely don't match any path containing wildcards
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
                search_str = os.path.expanduser(search_str)

                # Get what we need to restore the original tilde path later
                orig_tilde_path = text[:sep_index]
                expanded_tilde_path = os.path.expanduser(orig_tilde_path)

            # If the search text does not have a directory, then use the cwd
            elif not os.path.dirname(text):
                search_str = os.path.join(os.getcwd(), search_str)
                cwd_added = True

        # Find all matching path completions
        matches = glob.glob(search_str)

        # Filter out results that don't belong
        if path_filter is not None:
            matches = [c for c in matches if path_filter(c)]

        if matches:
            # Set this to True for proper quoting of paths with spaces
            self.matches_delimited = True

            # Don't append a space or closing quote to directory
            if len(matches) == 1 and os.path.isdir(matches[0]):
                self.allow_appended_space = False
                self.allow_closing_quote = False

            # Sort the matches before any trailing slashes are added
            matches.sort(key=self.default_sort_key)
            self.matches_sorted = True

            # Build display_matches and add a slash to directories
            for index, cur_match in enumerate(matches):
                # Display only the basename of this path in the tab completion suggestions
                self.display_matches.append(os.path.basename(cur_match))

                # Add a separator after directories if the next character isn't already a separator
                if os.path.isdir(cur_match) and add_trailing_sep_if_dir:
                    matches[index] += os.path.sep
                    self.display_matches[index] += os.path.sep

            # Remove cwd if it was added to match the text prompt-toolkit expects
            if cwd_added:
                to_replace = cwd if cwd == os.path.sep else cwd + os.path.sep
                matches = [cur_path.replace(to_replace, '', 1) for cur_path in matches]

            # Restore the tilde string if we expanded one to match the text prompt-toolkit expects
            if expanded_tilde_path:
                matches = [cur_path.replace(expanded_tilde_path, orig_tilde_path, 1) for cur_path in matches]

        return matches

    def shell_cmd_complete(self, text: str, line: str, begidx: int, endidx: int, *, complete_blank: bool = False) -> list[str]:
        """Perform completion of executables either in a user's path or a given path.

        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param complete_blank: If True, then a blank will complete all shell commands in a user's path. If False, then
                               no completion is performed. Defaults to False to match Bash shell behavior.
        :return: a list of possible tab completions
        """
        # Don't tab complete anything if no shell command has been started
        if not complete_blank and not text:
            return []

        # If there are no path characters in the search text, then do shell command completion in the user's path
        if not text.startswith('~') and os.path.sep not in text:
            return utils.get_exes_in_path(text)

        # Otherwise look for executables in the given path
        return self.path_complete(
            text, line, begidx, endidx, path_filter=lambda path: os.path.isdir(path) or os.access(path, os.X_OK)
        )

    def _redirect_complete(self, text: str, line: str, begidx: int, endidx: int, compfunc: CompleterFunc) -> list[str]:
        """First tab completion function for all commands, called by complete().

        It determines if it should tab complete for redirection (|, >, >>) or use the
        completer function for the current command.

        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param compfunc: the completer function for the current command
                         this will be called if we aren't completing for redirection
        :return: a list of possible tab completions
        """
        # Get all tokens through the one being completed. We want the raw tokens
        # so we can tell if redirection strings are quoted and ignore them.
        _, raw_tokens = self.tokens_for_completion(line, begidx, endidx)
        if not raw_tokens:  # pragma: no cover
            return []

        # Must at least have the command
        if len(raw_tokens) > 1:
            # True when command line contains any redirection tokens
            has_redirection = False

            # Keep track of state while examining tokens
            in_pipe = False
            in_file_redir = False
            do_shell_completion = False
            do_path_completion = False
            prior_token = None

            for cur_token in raw_tokens:
                # Process redirection tokens
                if cur_token in constants.REDIRECTION_TOKENS:
                    has_redirection = True

                    # Check if we are at a pipe
                    if cur_token == constants.REDIRECTION_PIPE:
                        # Do not complete bad syntax (e.g cmd | |)
                        if prior_token == constants.REDIRECTION_PIPE:
                            return []

                        in_pipe = True
                        in_file_redir = False

                    # Otherwise this is a file redirection token
                    else:
                        if prior_token in constants.REDIRECTION_TOKENS or in_file_redir:
                            # Do not complete bad syntax (e.g cmd | >) (e.g cmd > blah >)
                            return []

                        in_pipe = False
                        in_file_redir = True

                # Only tab complete after redirection tokens if redirection is allowed
                elif self.allow_redirection:
                    do_shell_completion = False
                    do_path_completion = False

                    if prior_token == constants.REDIRECTION_PIPE:
                        do_shell_completion = True
                    elif in_pipe or prior_token in (constants.REDIRECTION_OUTPUT, constants.REDIRECTION_APPEND):
                        do_path_completion = True

                prior_token = cur_token

            if do_shell_completion:
                return self.shell_cmd_complete(text, line, begidx, endidx)

            if do_path_completion:
                return self.path_complete(text, line, begidx, endidx)

            # If there were redirection strings anywhere on the command line, then we
            # are no longer tab completing for the current command
            if has_redirection:
                return []

        # Call the command's completer function
        return compfunc(text, line, begidx, endidx)

    @staticmethod
    def _determine_ap_completer_type(parser: argparse.ArgumentParser) -> type[argparse_completer.ArgparseCompleter]:
        """Determine what type of ArgparseCompleter to use on a given parser.

        If the parser does not have one set, then use argparse_completer.DEFAULT_AP_COMPLETER.
        :param parser: the parser to examine
        :return: type of ArgparseCompleter
        """
        Completer = type[argparse_completer.ArgparseCompleter] | None  # noqa: N806
        completer_type: Completer = parser.get_ap_completer_type()  # type: ignore[attr-defined]

        if completer_type is None:
            completer_type = argparse_completer.DEFAULT_AP_COMPLETER
        return completer_type

    def _perform_completion(
        self, text: str, line: str, begidx: int, endidx: int, custom_settings: utils.CustomCompletionSettings | None = None
    ) -> None:
        """Perform the actual completion, helper function for complete().

        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param custom_settings: optional prepopulated completion settings
        """
        # If custom_settings is None, then we are completing a command's argument.
        # Parse the command line to get the command token.
        command = ''
        if custom_settings is None:
            statement = self.statement_parser.parse_command_only(line)
            command = statement.command

            # Malformed command line (e.g. quoted command token)
            if not command:
                return

            expanded_line = statement.command_and_args

            if not expanded_line[-1:].isspace():
                # Unquoted trailing whitespace gets stripped by parse_command_only().
                # Restore it since line is only supposed to be lstripped when passed
                # to completer functions according to the Python cmd docs. Regardless
                # of what type of whitespace (' ', \n) was stripped, just append spaces
                # since shlex treats whitespace characters the same when splitting.
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
        if not tokens:  # pragma: no cover
            return

        # Determine the completer function to use for the command's argument
        if custom_settings is None:
            # Check if a macro was entered
            if command in self.macros:
                completer_func = self.macro_arg_complete

            # Check if a command was entered
            elif command in self.get_all_commands():
                # Get the completer function for this command
                func_attr = getattr(self, constants.COMPLETER_FUNC_PREFIX + command, None)

                if func_attr is not None:
                    completer_func = func_attr
                else:
                    # There's no completer function, next see if the command uses argparse
                    func = self.cmd_func(command)
                    argparser = None if func is None else self._command_parsers.get(func)

                    if func is not None and argparser is not None:
                        # Get arguments for complete()
                        preserve_quotes = getattr(func, constants.CMD_ATTR_PRESERVE_QUOTES)
                        cmd_set = self.find_commandset_for_command(command)

                        # Create the argparse completer
                        completer_type = self._determine_ap_completer_type(argparser)
                        completer = completer_type(argparser, self)

                        completer_func = functools.partial(
                            completer.complete, tokens=raw_tokens[1:] if preserve_quotes else tokens[1:], cmd_set=cmd_set
                        )
                    else:
                        completer_func = self.completedefault  # type: ignore[assignment]

            # Not a recognized macro or command
            # Check if this command should be run as a shell command
            elif self.default_to_shell and command in utils.get_exes_in_path(command):
                completer_func = self.path_complete
            else:
                completer_func = self.completedefault  # type: ignore[assignment]

        # Otherwise we are completing the command token or performing custom completion
        else:
            # Create the argparse completer
            completer_type = self._determine_ap_completer_type(custom_settings.parser)
            completer = completer_type(custom_settings.parser, self)

            completer_func = functools.partial(
                completer.complete, tokens=raw_tokens if custom_settings.preserve_quotes else tokens, cmd_set=None
            )

        # Text we need to remove from completions later
        text_to_remove = ''

        # Get the token being completed with any opening quote preserved
        raw_completion_token = raw_tokens[-1]

        # Used for adding quotes to the completion token
        completion_token_quote = ''

        # Check if the token being completed has an opening quote
        if raw_completion_token and raw_completion_token[0] in constants.QUOTES:
            # Since the token is still being completed, we know the opening quote is unclosed.
            # Save the quote so we can add a matching closing quote later.
            completion_token_quote = raw_completion_token[0]

            # prompt-toolkit still performs word breaks after a quote. Therefore, something like quoted search
            # text with a space would have resulted in begidx pointing to the middle of the token we
            # we want to complete. Figure out where that token actually begins and save the beginning
            # portion of it that was not part of the text prompt-toolkit gave us. We will remove it from the
            # completions later since prompt-toolkit expects them to start with the original text.
            actual_begidx = line[:endidx].rfind(tokens[-1])

            if actual_begidx != begidx:
                text_to_remove = line[actual_begidx:begidx]

                # Adjust text and where it begins so the completer routines
                # get unbroken search text to complete on.
                text = text_to_remove + text
                begidx = actual_begidx

        # Attempt tab completion for redirection first, and if that isn't occurring,
        # call the completer function for the current command
        self.completion_matches = self._redirect_complete(text, line, begidx, endidx, completer_func)

        if self.completion_matches:
            # Eliminate duplicates
            self.completion_matches = utils.remove_duplicates(self.completion_matches)
            self.display_matches = utils.remove_duplicates(self.display_matches)

            if not self.display_matches:
                # Since self.display_matches is empty, set it to self.completion_matches
                # before we alter them. That way the suggestions will reflect how we parsed
                # the token being completed and not how prompt-toolkit did.
                import copy

                self.display_matches = copy.copy(self.completion_matches)

            # Check if we need to add an opening quote
            if not completion_token_quote:
                add_quote = False

                # This is the tab completion text that will appear on the command line.
                common_prefix = os.path.commonprefix(self.completion_matches)

                if self.matches_delimited:
                    # For delimited matches, we check for a space in what appears before the display
                    # matches (common_prefix) as well as in the display matches themselves.
                    if ' ' in common_prefix or any(' ' in match for match in self.display_matches):
                        add_quote = True

                # If there is a tab completion and any match has a space, then add an opening quote
                elif any(' ' in match for match in self.completion_matches):
                    add_quote = True

                if add_quote:
                    # Figure out what kind of quote to add and save it as the unclosed_quote
                    completion_token_quote = "'" if any('"' in match for match in self.completion_matches) else '"'

                    self.completion_matches = [completion_token_quote + match for match in self.completion_matches]

            # Check if we need to remove text from the beginning of tab completions
            elif text_to_remove:
                self.completion_matches = [match.replace(text_to_remove, '', 1) for match in self.completion_matches]

            # If we have one result, then add a closing quote if needed and allowed
            if len(self.completion_matches) == 1 and self.allow_closing_quote and completion_token_quote:
                self.completion_matches[0] += completion_token_quote

    def complete(
        self,
        text: str,
        state: int,
        line: str | None = None,
        begidx: int | None = None,
        endidx: int | None = None,
        custom_settings: utils.CustomCompletionSettings | None = None,
    ) -> str | None:
        """Override of cmd's complete method which returns the next possible completion for 'text'.

        This completer function is called by prompt-toolkit as complete(text, state), for state in 0, 1, 2, …,
        until it returns a non-string value. It should return the next possible completion starting with text.

        Since prompt-toolkit suppresses any exception raised in completer functions, they can be difficult to debug.
        Therefore, this function wraps the actual tab completion logic and prints to stderr any exception that
        occurs before returning control to prompt-toolkit.

        :param text: the current word that user is typing
        :param state: non-negative integer
        :param line: optional current input line
        :param begidx: optional beginning index of text
        :param endidx: optional ending index of text
        :param custom_settings: used when not tab completing the main command line
        :return: the next possible completion for text or None
        """
        try:
            if state == 0:
                self._reset_completion_defaults()

                # If line is provided, use it and indices. Otherwise fallback to empty (for safety)
                if line is None:
                    line = ""
                if begidx is None:
                    begidx = 0
                if endidx is None:
                    endidx = 0

                # Check if we are completing a multiline command
                if self._at_continuation_prompt:
                    # lstrip and prepend the previously typed portion of this multiline command
                    lstripped_previous = self._multiline_in_progress.lstrip()
                    line = lstripped_previous + line

                    # Increment the indexes to account for the prepended text
                    begidx = len(lstripped_previous) + begidx
                    endidx = len(lstripped_previous) + endidx
                else:
                    # lstrip the original line
                    orig_line = line
                    line = orig_line.lstrip()
                    num_stripped = len(orig_line) - len(line)

                    # Calculate new indexes for the stripped line. If the cursor is at a position before the end of a
                    # line of spaces, then the following math could result in negative indexes. Enforce a max of 0.
                    begidx = max(begidx - num_stripped, 0)
                    endidx = max(endidx - num_stripped, 0)

                # Shortcuts are not word break characters when tab completing. Therefore, shortcuts become part
                # of the text variable if there isn't a word break, like a space, after it. We need to remove it
                # from text and update the indexes. This only applies if we are at the beginning of the command line.
                shortcut_to_restore = ''
                if begidx == 0 and custom_settings is None:
                    for shortcut, _ in self.statement_parser.shortcuts:
                        if text.startswith(shortcut):
                            # Save the shortcut to restore later
                            shortcut_to_restore = shortcut

                            # Adjust text and where it begins
                            text = text[len(shortcut_to_restore) :]
                            begidx += len(shortcut_to_restore)
                            break
                    else:
                        # No shortcut was found. Complete the command token.
                        parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(add_help=False)
                        parser.add_argument(
                            'command',
                            metavar="COMMAND",
                            help="command, alias, or macro name",
                            choices=self._get_commands_aliases_and_macros_for_completion(),
                            suppress_tab_hint=True,
                        )
                        custom_settings = utils.CustomCompletionSettings(parser)

                self._perform_completion(text, line, begidx, endidx, custom_settings)

                # Check if we need to restore a shortcut in the tab completions
                # so it doesn't get erased from the command line
                if shortcut_to_restore:
                    self.completion_matches = [shortcut_to_restore + match for match in self.completion_matches]

                # If we have one result and we are at the end of the line, then add a space if allowed
                if len(self.completion_matches) == 1 and endidx == len(line) and self.allow_appended_space:
                    self.completion_matches[0] += ' '

                # Sort matches if they haven't already been sorted
                if not self.matches_sorted:
                    self.completion_matches.sort(key=self.default_sort_key)
                    self.display_matches.sort(key=self.default_sort_key)
                    self.matches_sorted = True

                # Swap between COLUMN and MULTI_COLUMN style based on the number of matches if not using READLINE_LIKE
                if len(self.completion_matches) > self.max_column_completion_results:
                    self.session.complete_style = CompleteStyle.MULTI_COLUMN
                else:
                    self.session.complete_style = CompleteStyle.COLUMN

            try:
                return self.completion_matches[state]
            except IndexError:
                return None

        except CompletionError as ex:
            # Don't print error and redraw the prompt unless the error has length
            err_str = str(ex)
            if err_str:
                # If apply_style is True, then this is an error message that should be printed
                # above the prompt so it remains in the scrollback.
                if ex.apply_style:
                    # Render the error with style to a string using Rich
                    general_console = ru.Cmd2GeneralConsole()
                    with general_console.capture() as capture:
                        general_console.print("\n" + err_str, style=Cmd2Style.ERROR)
                    self.completion_header = capture.get()

                # Otherwise, this is a hint that should be displayed below the prompt.
                else:
                    self.completion_hint = err_str
            return None
        except Exception as ex:  # noqa: BLE001
            # Insert a newline so the exception doesn't print in the middle of the command line being tab completed
            exception_console = ru.Cmd2ExceptionConsole()
            with exception_console.capture() as capture:
                exception_console.print()
                self.pexcept(ex, console=exception_console)
            self.completion_header = capture.get()
            return None

    def in_script(self) -> bool:
        """Return whether a text script is running."""
        return self._current_script_dir is not None

    def in_pyscript(self) -> bool:
        """Return whether running inside a Python shell or pyscript."""
        return self._in_py

    @property
    def aliases(self) -> dict[str, str]:
        """Read-only property to access the aliases stored in the StatementParser."""
        return self.statement_parser.aliases

    def get_names(self) -> list[str]:
        """Return an alphabetized list of names comprising the attributes of the cmd2 class instance."""
        return dir(self)

    def get_all_commands(self) -> list[str]:
        """Return a list of all commands."""
        return [
            name[len(constants.COMMAND_FUNC_PREFIX) :]
            for name in self.get_names()
            if name.startswith(constants.COMMAND_FUNC_PREFIX) and callable(getattr(self, name))
        ]

    def get_visible_commands(self) -> list[str]:
        """Return a list of commands that have not been hidden or disabled."""
        return [
            command
            for command in self.get_all_commands()
            if command not in self.hidden_commands and command not in self.disabled_commands
        ]

    def _get_alias_completion_items(self) -> list[CompletionItem]:
        """Return list of alias names and values as CompletionItems."""
        results: list[CompletionItem] = []

        for name, value in self.aliases.items():
            descriptive_data = [value]
            results.append(CompletionItem(name, descriptive_data))

        return results

    def _get_macro_completion_items(self) -> list[CompletionItem]:
        """Return list of macro names and values as CompletionItems."""
        results: list[CompletionItem] = []

        for name, macro in self.macros.items():
            descriptive_data = [macro.value]
            results.append(CompletionItem(name, descriptive_data))

        return results

    def _get_settable_completion_items(self) -> list[CompletionItem]:
        """Return list of Settable names, values, and descriptions as CompletionItems."""
        results: list[CompletionItem] = []

        for name, settable in self.settables.items():
            descriptive_data = [
                str(settable.value),
                settable.description,
            ]
            results.append(CompletionItem(name, descriptive_data))

        return results

    def _get_commands_aliases_and_macros_for_completion(self) -> list[CompletionItem]:
        """Return a list of visible commands, aliases, and macros for tab completion."""
        results: list[CompletionItem] = []

        # Add commands
        for command in self.get_visible_commands():
            # Get the command method
            func = getattr(self, constants.COMMAND_FUNC_PREFIX + command)
            description = strip_doc_annotations(func.__doc__).splitlines()[0] if func.__doc__ else ''
            results.append(CompletionItem(command, [description]))

        # Add aliases
        for name, value in self.aliases.items():
            results.append(CompletionItem(name, [f"Alias for: {value}"]))

        # Add macros
        for name, macro in self.macros.items():
            results.append(CompletionItem(name, [f"Macro: {macro.value}"]))

        return results

    def get_help_topics(self) -> list[str]:
        """Return a list of help topics."""
        all_topics = [
            name[len(constants.HELP_FUNC_PREFIX) :]
            for name in self.get_names()
            if name.startswith(constants.HELP_FUNC_PREFIX) and callable(getattr(self, name))
        ]

        # Filter out hidden and disabled commands
        return [topic for topic in all_topics if topic not in self.hidden_commands and topic not in self.disabled_commands]

    def sigint_handler(
        self,
        signum: int,  # noqa: ARG002,
        frame: FrameType | None,  # noqa: ARG002,
    ) -> None:
        """Signal handler for SIGINTs which typically come from Ctrl-C events.

        If you need custom SIGINT behavior, then override this method.

        :param signum: signal number
        :param frame: the current stack frame or None
        """
        if self._cur_pipe_proc_reader is not None:
            # Pass the SIGINT to the current pipe process
            self._cur_pipe_proc_reader.send_sigint()

        # Check if we are allowed to re-raise the KeyboardInterrupt
        if not self.sigint_protection:
            raise_interrupt = True
            if self.current_command is not None:
                command_set = self.find_commandset_for_command(self.current_command.command)
                if command_set is not None:
                    raise_interrupt = not command_set.sigint_handler()
            if raise_interrupt:
                self._raise_keyboard_interrupt()

    def termination_signal_handler(self, signum: int, _: FrameType | None) -> None:
        """Signal handler for SIGHUP and SIGTERM. Only runs on Linux and Mac.

        SIGHUP - received when terminal window is closed
        SIGTERM - received when this app has been requested to terminate

        The basic purpose of this method is to call sys.exit() so our exit handler will run
        and save the persistent history file. If you need more complex behavior like killing
        threads and performing cleanup, then override this method.

        :param signum: signal number
        :param _: the current stack frame or None
        """
        # POSIX systems add 128 to signal numbers for the exit code
        sys.exit(128 + signum)

    def _raise_keyboard_interrupt(self) -> None:
        """Raise a KeyboardInterrupt."""
        self.poutput()  # Ensure new prompt is on a line by itself
        raise KeyboardInterrupt("Got a keyboard interrupt")

    def pre_prompt(self) -> None:
        """Ran just before the prompt is displayed (and after the event loop has started)."""

    def precmd(self, statement: Statement | str) -> Statement:
        """Ran just before the command is executed by [cmd2.Cmd.onecmd][] and after adding it to history (cmd  Hook method).

        :param statement: subclass of str which also contains the parsed input
        :return: a potentially modified version of the input Statement object

        See [cmd2.Cmd.register_postparsing_hook][] and [cmd2.Cmd.register_precmd_hook][] for more robust ways
        to run hooks before the command is executed. See [Hooks](../features/hooks.md) for more information.
        """
        return Statement(statement) if not isinstance(statement, Statement) else statement

    def postcmd(self, stop: bool, statement: Statement | str) -> bool:  # noqa: ARG002
        """Ran just after a command is executed by [cmd2.Cmd.onecmd][] (cmd inherited Hook method).

        :param stop: return `True` to request the command loop terminate
        :param statement: subclass of str which also contains the parsed input

        See [cmd2.Cmd.register_postcmd_hook][] and [cmd2.Cmd.register_cmdfinalization_hook][] for more robust ways
        to run hooks after the command is executed. See [Hooks](../features/hooks.md) for more information.
        """
        return stop

    def preloop(self) -> None:
        """Ran once when the [cmd2.Cmd.cmdloop][] method is called (cmd inherited Hook method).

        This method is a stub that does nothing and exists to be overridden by subclasses.

        See [cmd2.Cmd.register_preloop_hook][] for a more robust wayto run hooks before the command loop begins.
        See [Hooks](../features/hooks.md) for more information.
        """

    def postloop(self) -> None:
        """Ran once when the [cmd2.Cmd.cmdloop][] method is about to return (cmd inherited Hook Method).

        This method is a stub that does nothing and exists to be overridden by subclasses.

        See [cmd2.Cmd.register_postloop_hook][] for a more robust way to run hooks after the command loop completes.
        See [Hooks](../features/hooks.md) for more information.
        """

    def parseline(self, line: str) -> tuple[str, str, str]:
        """Parse the line into a command name and a string containing the arguments.

        :param line: line read by prompt-toolkit
        :return: tuple containing (command, args, line)
        """
        statement = self.statement_parser.parse_command_only(line)
        return statement.command, statement.args, statement.command_and_args

    def onecmd_plus_hooks(
        self,
        line: str,
        *,
        add_to_history: bool = True,
        raise_keyboard_interrupt: bool = False,
        py_bridge_call: bool = False,
    ) -> bool:
        """Top-level function called by cmdloop() to handle parsing a line and running the command and all of its hooks.

        :param line: command line to run
        :param add_to_history: If True, then add this command to history. Defaults to True.
        :param raise_keyboard_interrupt: if True, then KeyboardInterrupt exceptions will be raised if stop isn't already
                                         True. This is used when running commands in a loop to be able to stop the whole
                                         loop and not just the current command. Defaults to False.
        :param py_bridge_call: This should only ever be set to True by PyBridge to signify the beginning
                               of an app() call from Python. It is used to enable/disable the storage of the
                               command's stdout.
        :return: True if running of commands should stop
        """
        import datetime

        stop = False
        statement = None

        try:
            # Convert the line into a Statement
            statement = self._input_line_to_statement(line)

            # call the postparsing hooks
            postparsing_data = plugin.PostparsingData(False, statement)
            for postparsing_func in self._postparsing_hooks:
                postparsing_data = postparsing_func(postparsing_data)
                if postparsing_data.stop:
                    break

            # unpack the postparsing_data object
            statement = postparsing_data.statement
            stop = postparsing_data.stop
            if stop:
                # we should not run the command, but
                # we need to run the finalization hooks
                raise EmptyStatement  # noqa: TRY301

            redir_saved_state: utils.RedirectionSavedState | None = None

            try:
                # Get sigint protection while we set up redirection
                with self.sigint_protection:
                    if py_bridge_call:
                        # Start saving command's stdout at this point
                        self.stdout.pause_storage = False  # type: ignore[attr-defined]

                    redir_saved_state = self._redirect_output(statement)

                timestart = datetime.datetime.now(tz=datetime.timezone.utc)

                # precommand hooks
                precmd_data = plugin.PrecommandData(statement)
                for precmd_func in self._precmd_hooks:
                    precmd_data = precmd_func(precmd_data)
                statement = precmd_data.statement

                # call precmd() for compatibility with cmd.Cmd
                statement = self.precmd(statement)

                # go run the command function
                stop = self.onecmd(statement, add_to_history=add_to_history)

                # postcommand hooks
                postcmd_data = plugin.PostcommandData(stop, statement)
                for postcmd_func in self._postcmd_hooks:
                    postcmd_data = postcmd_func(postcmd_data)

                # retrieve the final value of stop, ignoring any statement modification from the hooks
                stop = postcmd_data.stop

                # call postcmd() for compatibility with cmd.Cmd
                stop = self.postcmd(stop, statement)

                if self.timing:
                    self.pfeedback(f'Elapsed: {datetime.datetime.now(tz=datetime.timezone.utc) - timestart}')
            finally:
                # Get sigint protection while we restore stuff
                with self.sigint_protection:
                    if redir_saved_state is not None:
                        self._restore_output(statement, redir_saved_state)

                    if py_bridge_call:
                        # Stop saving command's stdout before command finalization hooks run
                        self.stdout.pause_storage = True  # type: ignore[attr-defined]
        except (SkipPostcommandHooks, EmptyStatement):
            # Don't do anything, but do allow command finalization hooks to run
            pass
        except Cmd2ShlexError as ex:
            self.perror(f"Invalid syntax: {ex}")
        except RedirectionError as ex:
            self.perror(ex)
        except KeyboardInterrupt:
            if raise_keyboard_interrupt and not stop:
                raise
        except SystemExit as ex:
            if isinstance(ex.code, int):
                self.exit_code = ex.code
            stop = True
        except PassThroughException as ex:
            raise ex.wrapped_ex from None
        except Exception as ex:  # noqa: BLE001
            self.pexcept(ex)
        finally:
            try:
                stop = self._run_cmdfinalization_hooks(stop, statement)
            except KeyboardInterrupt:
                if raise_keyboard_interrupt and not stop:
                    raise
            except SystemExit as ex:
                if isinstance(ex.code, int):
                    self.exit_code = ex.code
                stop = True
            except PassThroughException as ex:
                raise ex.wrapped_ex from None
            except Exception as ex:  # noqa: BLE001
                self.pexcept(ex)

        return stop

    def _run_cmdfinalization_hooks(self, stop: bool, statement: Statement | None) -> bool:
        """Run the command finalization hooks."""
        if self._initial_termios_settings is not None and self.stdin.isatty():  # type: ignore[unreachable]
            import io  # type: ignore[unreachable]
            import termios

            # Before the next command runs, fix any terminal problems like those
            # caused by certain binary characters having been printed to it.
            with self.sigint_protection, contextlib.suppress(io.UnsupportedOperation, termios.error):
                # This can fail if stdin is a pseudo-TTY, in which case we just ignore it
                termios.tcsetattr(self.stdin.fileno(), termios.TCSANOW, self._initial_termios_settings)

        data = plugin.CommandFinalizationData(stop, statement)
        for func in self._cmdfinalization_hooks:
            data = func(data)
        # retrieve the final value of stop, ignoring any
        # modifications to the statement
        return data.stop

    def runcmds_plus_hooks(
        self,
        cmds: list[HistoryItem] | list[str],
        *,
        add_to_history: bool = True,
        stop_on_keyboard_interrupt: bool = False,
    ) -> bool:
        """Run commands in an automated fashion from sources like text scripts or history replays.

        The prompt and command line for each command will be printed if echo is True.

        :param cmds: commands to run
        :param add_to_history: If True, then add these commands to history. Defaults to True.
        :param stop_on_keyboard_interrupt: if True, then stop running contents of cmds if Ctrl-C is pressed instead of moving
                                           to the next command in the list. This is used when the commands are part of a
                                           group, like a text script, which should stop upon Ctrl-C. Defaults to False.
        :return: True if running of commands should stop
        """
        for line in cmds:
            if isinstance(line, HistoryItem):
                line = line.raw  # noqa: PLW2901

            if self.echo:
                self.poutput(f'{self.prompt}{line}')

            try:
                if self.onecmd_plus_hooks(
                    line, add_to_history=add_to_history, raise_keyboard_interrupt=stop_on_keyboard_interrupt
                ):
                    return True
            except KeyboardInterrupt as ex:
                if stop_on_keyboard_interrupt:
                    self.perror(ex)
                    break

        return False

    def _complete_statement(self, line: str) -> Statement:
        """Keep accepting lines of input until the command is complete.

        There is some pretty hacky code here to handle some quirks of
        self._read_command_line(). It returns a literal 'eof' if the input
        pipe runs out. We can't refactor it because we need to retain
        backwards compatibility with the standard library version of cmd.

        :param line: the line being parsed
        :return: the completed Statement
        :raises Cmd2ShlexError: if a shlex error occurs (e.g. No closing quotation)
        :raises EmptyStatement: when the resulting Statement is blank
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
            except Cmd2ShlexError:
                # we have an unclosed quotation mark, let's parse only the command
                # and see if it's a multiline
                statement = self.statement_parser.parse_command_only(line)
                if not statement.multiline_command:
                    # not a multiline command, so raise the exception
                    raise

            # if we get here we must have:
            #   - a multiline command with no terminator
            #   - a multiline command with unclosed quotation marks
            try:
                self._at_continuation_prompt = True

                # Save the command line up to this point for tab completion
                self._multiline_in_progress = line + '\n'

                # Get next line of this command
                nextline = self._read_command_line(self.continuation_prompt)
                if nextline == 'eof':
                    # they entered either a blank line, or we hit an EOF
                    # for some other reason. Turn the literal 'eof'
                    # into a blank line, which serves as a command
                    # terminator
                    nextline = '\n'
                    self.poutput(nextline)

                line += f'\n{nextline}'

            except KeyboardInterrupt:
                self.poutput('^C')
                statement = self.statement_parser.parse('')
                break
            finally:
                self._at_continuation_prompt = False

        if not statement.command:
            raise EmptyStatement

        return statement

    def _input_line_to_statement(self, line: str) -> Statement:
        """Parse the user's input line and convert it to a Statement, ensuring that all macros are also resolved.

        :param line: the line being parsed
        :return: parsed command line as a Statement
        :raises Cmd2ShlexError: if a shlex error occurs (e.g. No closing quotation)
        :raises EmptyStatement: when the resulting Statement is blank
        """
        used_macros = []
        orig_line = None

        # Continue until all macros are resolved
        while True:
            # Make sure all input has been read and convert it to a Statement
            statement = self._complete_statement(line)

            # If this is the first loop iteration, save the original line and stop
            # combining multiline history entries in the remaining iterations.
            if orig_line is None:
                orig_line = statement.raw

            # Check if this command matches a macro and wasn't already processed to avoid an infinite loop
            if statement.command in self.macros and statement.command not in used_macros:
                used_macros.append(statement.command)
                resolve_result = self._resolve_macro(statement)
                if resolve_result is None:
                    raise EmptyStatement
                line = resolve_result
            else:
                break

        # This will be true when a macro was used
        if orig_line != statement.raw:
            # Build a Statement that contains the resolved macro line
            # but the originally typed line for its raw member.
            statement = Statement(
                statement.args,
                raw=orig_line,
                command=statement.command,
                arg_list=statement.arg_list,
                multiline_command=statement.multiline_command,
                terminator=statement.terminator,
                suffix=statement.suffix,
                pipe_to=statement.pipe_to,
                output=statement.output,
                output_to=statement.output_to,
            )
        return statement

    def _resolve_macro(self, statement: Statement) -> str | None:
        """Resolve a macro and return the resulting string.

        :param statement: the parsed statement from the command line
        :return: the resolved macro or None on error
        """
        if statement.command not in self.macros:
            raise KeyError(f"{statement.command} is not a macro")

        macro = self.macros[statement.command]

        # Make sure enough arguments were passed in
        if len(statement.arg_list) < macro.minimum_arg_count:
            plural = '' if macro.minimum_arg_count == 1 else 's'
            self.perror(f"The macro '{statement.command}' expects at least {macro.minimum_arg_count} argument{plural}")
            return None

        # Resolve the arguments in reverse and read their values from statement.argv since those
        # are unquoted. Macro args should have been quoted when the macro was created.
        resolved = macro.value
        reverse_arg_list = sorted(macro.arg_list, key=lambda ma: ma.start_index, reverse=True)

        for macro_arg in reverse_arg_list:
            if macro_arg.is_escaped:
                to_replace = '{{' + macro_arg.number_str + '}}'
                replacement = '{' + macro_arg.number_str + '}'
            else:
                to_replace = '{' + macro_arg.number_str + '}'
                replacement = statement.argv[int(macro_arg.number_str)]

            parts = resolved.rsplit(to_replace, maxsplit=1)
            resolved = parts[0] + replacement + parts[1]

        # Append extra arguments and use statement.arg_list since these arguments need their quotes preserved
        for stmt_arg in statement.arg_list[macro.minimum_arg_count :]:
            resolved += ' ' + stmt_arg

        # Restore any terminator, suffix, redirection, etc.
        return resolved + statement.post_command

    def _redirect_output(self, statement: Statement) -> utils.RedirectionSavedState:
        """Set up a command's output redirection for >, >>, and |.

        :param statement: a parsed statement from the user
        :return: A bool telling if an error occurred and a utils.RedirectionSavedState object
        :raises RedirectionError: if an error occurs trying to pipe or redirect
        """
        import subprocess

        # Only redirect sys.stdout if it's the same as self.stdout
        stdouts_match = self.stdout == sys.stdout

        # Initialize the redirection saved state
        redir_saved_state = utils.RedirectionSavedState(
            self.stdout, stdouts_match, self._cur_pipe_proc_reader, self._redirecting
        )

        # The ProcReader for this command
        cmd_pipe_proc_reader: utils.ProcReader | None = None

        if not self.allow_redirection:
            # Don't return since we set some state variables at the end of the function
            pass

        elif statement.pipe_to:
            # Create a pipe with read and write sides
            read_fd, write_fd = os.pipe()

            # Open each side of the pipe
            subproc_stdin = open(read_fd)  # noqa: SIM115
            new_stdout: TextIO = cast(TextIO, open(write_fd, 'w'))  # noqa: SIM115

            # Create pipe process in a separate group to isolate our signals from it. If a Ctrl-C event occurs,
            # our sigint handler will forward it only to the most recent pipe process. This makes sure pipe
            # processes close in the right order (most recent first).
            kwargs: dict[str, Any] = {}
            if sys.platform == 'win32':
                kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs['start_new_session'] = True

                # Attempt to run the pipe process in the user's preferred shell instead of the default behavior of using sh.
                shell = os.environ.get("SHELL")
                if shell:
                    kwargs['executable'] = shell

            # For any stream that is a StdSim, we will use a pipe so we can capture its output
            proc = subprocess.Popen(  # noqa: S602
                statement.pipe_to,
                stdin=subproc_stdin,
                stdout=subprocess.PIPE if isinstance(self.stdout, utils.StdSim) else self.stdout,  # type: ignore[unreachable]
                stderr=subprocess.PIPE if isinstance(sys.stderr, utils.StdSim) else sys.stderr,
                shell=True,
                **kwargs,
            )

            # Popen was called with shell=True so the user can chain pipe commands and redirect their output
            # like: !ls -l | grep user | wc -l > out.txt. But this makes it difficult to know if the pipe process
            # started OK, since the shell itself always starts. Therefore, we will wait a short time and check
            # if the pipe process is still running.
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(0.2)

            # Check if the pipe process already exited
            if proc.returncode is not None:
                subproc_stdin.close()
                new_stdout.close()
                raise RedirectionError(f'Pipe process exited with code {proc.returncode} before command could run')
            redir_saved_state.redirecting = True
            cmd_pipe_proc_reader = utils.ProcReader(proc, self.stdout, sys.stderr)

            self.stdout = new_stdout
            if stdouts_match:
                sys.stdout = self.stdout

        elif statement.output:
            if statement.output_to:
                # redirecting to a file
                # statement.output can only contain REDIRECTION_APPEND or REDIRECTION_OUTPUT
                mode = 'a' if statement.output == constants.REDIRECTION_APPEND else 'w'
                try:
                    # Use line buffering
                    new_stdout = cast(TextIO, open(su.strip_quotes(statement.output_to), mode=mode, buffering=1))  # noqa: SIM115
                except OSError as ex:
                    raise RedirectionError('Failed to redirect output') from ex

                redir_saved_state.redirecting = True

                self.stdout = new_stdout
                if stdouts_match:
                    sys.stdout = self.stdout

            else:
                # Redirecting to a paste buffer
                # we are going to direct output to a temporary file, then read it back in and
                # put it in the paste buffer later
                if not self.allow_clipboard:
                    raise RedirectionError("Clipboard access not allowed")

                # attempt to get the paste buffer, this forces pyperclip to go figure
                # out if it can actually interact with the paste buffer, and will throw exceptions
                # if it's not gonna work. That way we throw the exception before we go
                # run the command and queue up all the output. if this is going to fail,
                # no point opening up the temporary file
                current_paste_buffer = get_paste_buffer()
                # create a temporary file to store output
                new_stdout = cast(TextIO, tempfile.TemporaryFile(mode="w+"))  # noqa: SIM115
                redir_saved_state.redirecting = True

                self.stdout = new_stdout
                if stdouts_match:
                    sys.stdout = self.stdout

                if statement.output == constants.REDIRECTION_APPEND:
                    self.stdout.write(current_paste_buffer)
                    self.stdout.flush()

        # These are updated regardless of whether the command redirected
        self._cur_pipe_proc_reader = cmd_pipe_proc_reader
        self._redirecting = redir_saved_state.redirecting

        return redir_saved_state

    def _restore_output(self, statement: Statement, saved_redir_state: utils.RedirectionSavedState) -> None:
        """Handle restoring state after output redirection.

        :param statement: Statement object which contains the parsed input from the user
        :param saved_redir_state: contains information needed to restore state data
        """
        if saved_redir_state.redirecting:
            # If we redirected output to the clipboard
            if statement.output and not statement.output_to:
                self.stdout.seek(0)
                write_to_paste_buffer(self.stdout.read())

            with contextlib.suppress(BrokenPipeError):
                # Close the file or pipe that stdout was redirected to
                self.stdout.close()

            # Restore the stdout values
            self.stdout = cast(TextIO, saved_redir_state.saved_self_stdout)
            if saved_redir_state.stdouts_match:
                sys.stdout = self.stdout

            # Check if we need to wait for the process being piped to
            if self._cur_pipe_proc_reader is not None:
                self._cur_pipe_proc_reader.wait()

        # These are restored regardless of whether the command redirected
        self._cur_pipe_proc_reader = saved_redir_state.saved_pipe_proc_reader
        self._redirecting = saved_redir_state.saved_redirecting

    def cmd_func(self, command: str) -> CommandFunc | None:
        """Get the function for a command.

        :param command: the name of the command

        Example:
        ```py
        helpfunc = self.cmd_func('help')
        ```

        helpfunc now contains a reference to the ``do_help`` method

        """
        func_name = constants.COMMAND_FUNC_PREFIX + command
        func = getattr(self, func_name, None)
        return cast(CommandFunc, func) if callable(func) else None

    def onecmd(self, statement: Statement | str, *, add_to_history: bool = True) -> bool:
        """Execute the actual do_* method for a command.

        If the command provided doesn't exist, then it executes default() instead.

        :param statement: intended to be a Statement instance parsed command from the input stream, alternative
                          acceptance of a str is present only for backward compatibility with cmd
        :param add_to_history: If True, then add this command to history. Defaults to True.
        :return: a flag indicating whether the interpretation of commands should stop
        """
        # For backwards compatibility with cmd, allow a str to be passed in
        if not isinstance(statement, Statement):
            statement = self._input_line_to_statement(statement)

        func = self.cmd_func(statement.command)
        if func:
            # Check to see if this command should be stored in history
            if (
                statement.command not in self.exclude_from_history
                and statement.command not in self.disabled_commands
                and add_to_history
            ):
                self.history.append(statement)

            try:
                self.current_command = statement
                stop = func(statement)
            finally:
                self.current_command = None

        else:
            stop = self.default(statement)

        return stop if stop is not None else False

    def default(self, statement: Statement) -> bool | None:
        """Execute when the command given isn't a recognized command implemented by a do_* method.

        :param statement: Statement object with parsed input
        """
        if self.default_to_shell:
            if 'shell' not in self.exclude_from_history:
                self.history.append(statement)
            return self.do_shell(statement.command_and_args)

        err_msg = self.default_error.format(statement.command)
        if self.suggest_similar_command and (suggested_command := self._suggest_similar_command(statement.command)):
            err_msg += f"\n{self.default_suggestion_message.format(suggested_command)}"

        self.perror(err_msg, style=None)
        return None

    def completedefault(self, *_ignored: list[str]) -> list[str]:
        """Call to complete an input line when no command-specific complete_*() method is available.

        This method is only called for non-argparse-based commands.

        By default, it returns an empty list.
        """
        return []

    def _suggest_similar_command(self, command: str) -> str | None:
        return suggest_similar(command, self.get_visible_commands())

    def read_input(
        self,
        prompt: str = '',
        *,
        history: list[str] | None = None,
        completion_mode: utils.CompletionMode = utils.CompletionMode.NONE,
        preserve_quotes: bool = False,
        choices: Iterable[Any] | None = None,
        choices_provider: ChoicesProviderFunc | None = None,
        completer: CompleterFunc | None = None,
        parser: argparse.ArgumentParser | None = None,
    ) -> str:
        """Read input from appropriate stdin value.

        Also supports tab completion and up-arrow history while input is being entered.

        :param prompt: prompt to display to user
        :param history: optional list of strings to use for up-arrow history. If completion_mode is
                        CompletionMode.COMMANDS and this is None, then cmd2's command list history will
                        be used. The passed in history will not be edited. It is the caller's responsibility
                        to add the returned input to history if desired. Defaults to None.
        :param completion_mode: tells what type of tab completion to support. Tab completion only works when
                                self.use_rawinput is True and sys.stdin is a terminal. Defaults to
                                CompletionMode.NONE.
        The following optional settings apply when completion_mode is CompletionMode.CUSTOM:
        :param preserve_quotes: if True, then quoted tokens will keep their quotes when processed by
                                ArgparseCompleter. This is helpful in cases when you're tab completing
                                flag-like tokens (e.g. -o, --option) and you don't want them to be
                                treated as argparse flags when quoted. Set this to True if you plan
                                on passing the string to argparse with the tokens still quoted.
        A maximum of one of these should be provided:
        :param choices: iterable of accepted values for single argument
        :param choices_provider: function that provides choices for single argument
        :param completer: tab completion function that provides choices for single argument
        :param parser: an argument parser which supports the tab completion of multiple arguments
        :return: the line read from stdin with all trailing new lines removed
        :raises Exception: any exceptions raised by prompt()
        """
        self._reset_completion_defaults()
        with self._in_prompt_lock:
            self._in_prompt = True
        try:
            if self.use_rawinput and self.stdin.isatty():
                # Determine completer
                completer_to_use: Completer
                if completion_mode == utils.CompletionMode.NONE:
                    completer_to_use = DummyCompleter()

                    # No up-arrow history when CompletionMode.NONE and history is None
                    if history is None:
                        history = []
                elif completion_mode == utils.CompletionMode.COMMANDS:
                    completer_to_use = self.completer
                else:
                    # Custom completion
                    if parser is None:
                        parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(add_help=False)
                        parser.add_argument(
                            'arg',
                            suppress_tab_hint=True,
                            choices=choices,
                            choices_provider=choices_provider,
                            completer=completer,
                        )
                    custom_settings = utils.CustomCompletionSettings(parser, preserve_quotes=preserve_quotes)
                    completer_to_use = Cmd2Completer(self, custom_settings=custom_settings)

                # Use dynamic prompt if the prompt matches self.prompt
                def get_prompt() -> ANSI | str:
                    return ANSI(self.prompt)

                prompt_to_use: Callable[[], ANSI | str] | ANSI | str = ANSI(prompt)
                if prompt == self.prompt:
                    prompt_to_use = get_prompt

                with patch_stdout():
                    if history is not None:
                        # If custom history is provided, we use the prompt() shortcut
                        # which can take a history object.
                        history_to_use = InMemoryHistory()
                        for item in history:
                            history_to_use.append_string(item)

                        temp_session1: PromptSession[str] = PromptSession(
                            complete_style=self.session.complete_style,
                            complete_while_typing=self.session.complete_while_typing,
                            history=history_to_use,
                            input=self.session.input,
                            lexer=self.lexer,
                            output=self.session.output,
                        )

                        return temp_session1.prompt(
                            prompt_to_use,
                            bottom_toolbar=self.get_bottom_toolbar if self.bottom_toolbar else None,
                            completer=completer_to_use,
                            lexer=self.lexer,
                            pre_run=self.pre_prompt,
                            rprompt=self.get_rprompt,
                        )

                    # history is None
                    return self.session.prompt(
                        prompt_to_use,
                        bottom_toolbar=self.get_bottom_toolbar if self.bottom_toolbar else None,
                        completer=completer_to_use,
                        lexer=self.lexer,
                        pre_run=self.pre_prompt,
                        rprompt=self.get_rprompt,
                    )

            # Otherwise read from self.stdin
            elif self.stdin.isatty():
                # on a tty, print the prompt first, then read the line
                temp_session2: PromptSession[str] = PromptSession(
                    input=self.session.input,
                    output=self.session.output,
                    lexer=self.lexer,
                    complete_style=self.session.complete_style,
                    complete_while_typing=self.session.complete_while_typing,
                )
                line = temp_session2.prompt(
                    prompt,
                    bottom_toolbar=self.get_bottom_toolbar if self.bottom_toolbar else None,
                    pre_run=self.pre_prompt,
                    rprompt=self.get_rprompt,
                )
                if len(line) == 0:
                    raise EOFError
                return line.rstrip('\n')
            else:
                # not a tty, just read the line
                temp_session3: PromptSession[str] = PromptSession(
                    complete_style=self.session.complete_style,
                    complete_while_typing=self.session.complete_while_typing,
                    input=self.session.input,
                    lexer=self.lexer,
                    output=self.session.output,
                )
                line = temp_session3.prompt(
                    bottom_toolbar=self.get_bottom_toolbar if self.bottom_toolbar else None,
                    pre_run=self.pre_prompt,
                    rprompt=self.get_rprompt,
                )
                if len(line) == 0:
                    raise EOFError
                line = line.rstrip('\n')

                if self.echo:
                    self.poutput(f'{prompt}{line}')

                return line

        finally:
            with self._in_prompt_lock:
                self._in_prompt = False

    def _read_command_line(self, prompt: str) -> str:
        """Read command line from appropriate stdin.

        :param prompt: prompt to display to user
        :return: command line text of 'eof' if an EOFError was caught
        :raises Exception: whatever exceptions are raised by input() except for EOFError
        """
        try:
            return self.read_input(prompt, completion_mode=utils.CompletionMode.COMMANDS)
        except EOFError:
            return 'eof'

    def _cmdloop(self) -> None:
        """Repeatedly issue a prompt, accept input, parse it, and dispatch to apporpriate commands.

        Parse an initial prefix off the received input and dispatch to action methods, passing them
        the remainder of the line as argument.

        This serves the same role as cmd.cmdloop().
        """
        try:
            # Run startup commands
            stop = self.runcmds_plus_hooks(self._startup_commands)
            self._startup_commands.clear()

            while not stop:
                # Get commands from user
                try:
                    line = self._read_command_line(self.prompt)
                except KeyboardInterrupt:
                    self.poutput('^C')
                    line = ''

                # Run the command along with all associated pre and post hooks
                stop = self.onecmd_plus_hooks(line)
        finally:
            pass

    #############################################################
    # Parsers and functions for alias command and subcommands
    #############################################################

    # Top-level parser for alias
    @staticmethod
    def _build_alias_parser() -> Cmd2ArgumentParser:
        alias_description = Text.assemble(
            "Manage aliases.",
            "\n\n",
            "An alias is a command that enables replacement of a word by another string.",
        )
        alias_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description=alias_description)
        alias_parser.epilog = alias_parser.create_text_group(
            "See Also",
            "macro",
        )
        alias_parser.add_subparsers(metavar='SUBCOMMAND', required=True)

        return alias_parser

    # Preserve quotes since we are passing strings to other commands
    @with_argparser(_build_alias_parser, preserve_quotes=True)
    def do_alias(self, args: argparse.Namespace) -> None:
        """Manage aliases."""
        # Call handler for whatever subcommand was selected
        handler = args.cmd2_handler.get()
        handler(args)

    # alias -> create
    @classmethod
    def _build_alias_create_parser(cls) -> Cmd2ArgumentParser:
        alias_create_description = "Create or overwrite an alias."
        alias_create_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description=alias_create_description)

        # Add Notes epilog
        alias_create_notes = Text.assemble(
            "If you want to use redirection, pipes, or terminators in the value of the alias, then quote them.",
            "\n\n",
            ("    alias create save_results print_results \">\" out.txt\n", Cmd2Style.COMMAND_LINE),
            "\n\n",
            (
                "Since aliases are resolved during parsing, tab completion will function as it would "
                "for the actual command the alias resolves to."
            ),
        )
        alias_create_parser.epilog = alias_create_parser.create_text_group("Notes", alias_create_notes)

        # Add arguments
        alias_create_parser.add_argument('name', help='name of this alias')
        alias_create_parser.add_argument(
            'command',
            help='command, alias, or macro to run',
            choices_provider=cls._get_commands_aliases_and_macros_for_completion,
        )
        alias_create_parser.add_argument(
            'command_args',
            nargs=argparse.REMAINDER,
            help='arguments to pass to command',
            completer=cls.path_complete,
        )

        return alias_create_parser

    @as_subcommand_to('alias', 'create', _build_alias_create_parser, help="create or overwrite an alias")
    def _alias_create(self, args: argparse.Namespace) -> None:
        """Create or overwrite an alias."""
        self.last_result = False

        # Validate the alias name
        valid, errmsg = self.statement_parser.is_valid_command(args.name)
        if not valid:
            self.perror(f"Invalid alias name: {errmsg}")
            return

        if args.name in self.get_all_commands():
            self.perror("Alias cannot have the same name as a command")
            return

        if args.name in self.macros:
            self.perror("Alias cannot have the same name as a macro")
            return

        # Unquote redirection and terminator tokens
        tokens_to_unquote = constants.REDIRECTION_TOKENS
        tokens_to_unquote.extend(self.statement_parser.terminators)
        utils.unquote_specific_tokens(args.command_args, tokens_to_unquote)

        # Build the alias value string
        value = args.command
        if args.command_args:
            value += ' ' + ' '.join(args.command_args)

        # Set the alias
        result = "overwritten" if args.name in self.aliases else "created"
        self.poutput(f"Alias '{args.name}' {result}")

        self.aliases[args.name] = value
        self.last_result = True

    # alias -> delete
    @classmethod
    def _build_alias_delete_parser(cls) -> Cmd2ArgumentParser:
        alias_delete_description = "Delete specified aliases or all aliases if --all is used."

        alias_delete_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description=alias_delete_description)
        alias_delete_parser.add_argument('-a', '--all', action='store_true', help="delete all aliases")
        alias_delete_parser.add_argument(
            'names',
            nargs=argparse.ZERO_OR_MORE,
            help='alias(es) to delete',
            choices_provider=cls._get_alias_completion_items,
            descriptive_headers=["Value"],
        )

        return alias_delete_parser

    @as_subcommand_to('alias', 'delete', _build_alias_delete_parser, help="delete aliases")
    def _alias_delete(self, args: argparse.Namespace) -> None:
        """Delete aliases."""
        self.last_result = True

        if args.all:
            self.aliases.clear()
            self.poutput("All aliases deleted")
        elif not args.names:
            self.perror("Either --all or alias name(s) must be specified")
            self.last_result = False
        else:
            for cur_name in utils.remove_duplicates(args.names):
                if cur_name in self.aliases:
                    del self.aliases[cur_name]
                    self.poutput(f"Alias '{cur_name}' deleted")
                else:
                    self.perror(f"Alias '{cur_name}' does not exist")

    # alias -> list
    @classmethod
    def _build_alias_list_parser(cls) -> Cmd2ArgumentParser:
        alias_list_description = Text.assemble(
            (
                "List specified aliases in a reusable form that can be saved to a startup "
                "script to preserve aliases across sessions."
            ),
            "\n\n",
            "Without arguments, all aliases will be listed.",
        )

        alias_list_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description=alias_list_description)
        alias_list_parser.add_argument(
            'names',
            nargs=argparse.ZERO_OR_MORE,
            help='alias(es) to list',
            choices_provider=cls._get_alias_completion_items,
            descriptive_headers=["Value"],
        )

        return alias_list_parser

    @as_subcommand_to('alias', 'list', _build_alias_list_parser, help="list aliases")
    def _alias_list(self, args: argparse.Namespace) -> None:
        """List some or all aliases as 'alias create' commands."""
        self.last_result = {}  # dict[alias_name, alias_value]

        tokens_to_quote = constants.REDIRECTION_TOKENS
        tokens_to_quote.extend(self.statement_parser.terminators)

        to_list = utils.remove_duplicates(args.names) if args.names else sorted(self.aliases, key=self.default_sort_key)

        not_found: list[str] = []
        for name in to_list:
            if name not in self.aliases:
                not_found.append(name)
                continue

            # Quote redirection and terminator tokens for the 'alias create' command
            tokens = shlex_split(self.aliases[name])
            command = tokens[0]
            command_args = tokens[1:]
            utils.quote_specific_tokens(command_args, tokens_to_quote)

            val = command
            if command_args:
                val += ' ' + ' '.join(command_args)

            self.poutput(f"alias create {name} {val}")
            self.last_result[name] = val

        for name in not_found:
            self.perror(f"Alias '{name}' not found")

    #############################################################
    # Parsers and functions for macro command and subcommands
    #############################################################

    def macro_arg_complete(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        """Tab completes arguments to a macro.

        Its default behavior is to call path_complete, but you can override this as needed.

        The args required by this function are defined in the header of Python's cmd.py.

        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :return: a list of possible tab completions
        """
        return self.path_complete(text, line, begidx, endidx)

    # Top-level parser for macro
    @staticmethod
    def _build_macro_parser() -> Cmd2ArgumentParser:
        macro_description = Text.assemble(
            "Manage macros.",
            "\n\n",
            "A macro is similar to an alias, but it can contain argument placeholders.",
        )
        macro_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description=macro_description)
        macro_parser.epilog = macro_parser.create_text_group(
            "See Also",
            "alias",
        )
        macro_parser.add_subparsers(metavar='SUBCOMMAND', required=True)

        return macro_parser

    # Preserve quotes since we are passing strings to other commands
    @with_argparser(_build_macro_parser, preserve_quotes=True)
    def do_macro(self, args: argparse.Namespace) -> None:
        """Manage macros."""
        # Call handler for whatever subcommand was selected
        handler = args.cmd2_handler.get()
        handler(args)

    # macro -> create
    @classmethod
    def _build_macro_create_parser(cls) -> Cmd2ArgumentParser:
        macro_create_description = Text.assemble(
            "Create or overwrite a macro.",
            "\n\n",
            "A macro is similar to an alias, but it can contain argument placeholders.",
            "\n\n",
            "Arguments are expressed when creating a macro using {#} notation where {1} means the first argument.",
            "\n\n",
            "The following creates a macro called my_macro that expects two arguments:",
            "\n\n",
            ("    macro create my_macro make_dinner --meat {1} --veggie {2}", Cmd2Style.COMMAND_LINE),
            "\n\n",
            "When the macro is called, the provided arguments are resolved and the assembled command is run. For example:",
            "\n\n",
            ("    my_macro beef broccoli", Cmd2Style.COMMAND_LINE),
            (" ───> ", Style(bold=True)),
            ("make_dinner --meat beef --veggie broccoli", Cmd2Style.COMMAND_LINE),
        )
        macro_create_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description=macro_create_description)

        # Add Notes epilog
        macro_create_notes = Text.assemble(
            "To use the literal string {1} in your command, escape it this way: {{1}}.",
            "\n\n",
            "Extra arguments passed to a macro are appended to resolved command.",
            "\n\n",
            (
                "An argument number can be repeated in a macro. In the following example the "
                "first argument will populate both {1} instances."
            ),
            "\n\n",
            ("    macro create ft file_taxes -p {1} -q {2} -r {1}", Cmd2Style.COMMAND_LINE),
            "\n\n",
            "To quote an argument in the resolved command, quote it during creation.",
            "\n\n",
            ("    macro create backup !cp \"{1}\" \"{1}.orig\"", Cmd2Style.COMMAND_LINE),
            "\n\n",
            "If you want to use redirection, pipes, or terminators in the value of the macro, then quote them.",
            "\n\n",
            ("    macro create show_results print_results -type {1} \"|\" less", Cmd2Style.COMMAND_LINE),
            "\n\n",
            (
                "Since macros don't resolve until after you press Enter, their arguments tab complete as paths. "
                "This default behavior changes if custom tab completion for macro arguments has been implemented."
            ),
        )
        macro_create_parser.epilog = macro_create_parser.create_text_group("Notes", macro_create_notes)

        # Add arguments
        macro_create_parser.add_argument('name', help='name of this macro')
        macro_create_parser.add_argument(
            'command',
            help='command, alias, or macro to run',
            choices_provider=cls._get_commands_aliases_and_macros_for_completion,
        )
        macro_create_parser.add_argument(
            'command_args',
            nargs=argparse.REMAINDER,
            help='arguments to pass to command',
            completer=cls.path_complete,
        )

        return macro_create_parser

    @as_subcommand_to('macro', 'create', _build_macro_create_parser, help="create or overwrite a macro")
    def _macro_create(self, args: argparse.Namespace) -> None:
        """Create or overwrite a macro."""
        self.last_result = False

        # Validate the macro name
        valid, errmsg = self.statement_parser.is_valid_command(args.name)
        if not valid:
            self.perror(f"Invalid macro name: {errmsg}")
            return

        if args.name in self.get_all_commands():
            self.perror("Macro cannot have the same name as a command")
            return

        if args.name in self.aliases:
            self.perror("Macro cannot have the same name as an alias")
            return

        # Unquote redirection and terminator tokens
        tokens_to_unquote = constants.REDIRECTION_TOKENS
        tokens_to_unquote.extend(self.statement_parser.terminators)
        utils.unquote_specific_tokens(args.command_args, tokens_to_unquote)

        # Build the macro value string
        value = args.command
        if args.command_args:
            value += ' ' + ' '.join(args.command_args)

        # Find all normal arguments
        arg_list = []
        normal_matches = re.finditer(MacroArg.macro_normal_arg_pattern, value)
        max_arg_num = 0
        arg_nums = set()

        try:
            while True:
                cur_match = normal_matches.__next__()

                # Get the number string between the braces
                cur_num_str = re.findall(MacroArg.digit_pattern, cur_match.group())[0]
                cur_num = int(cur_num_str)
                if cur_num < 1:
                    self.perror("Argument numbers must be greater than 0")
                    return

                arg_nums.add(cur_num)
                max_arg_num = max(max_arg_num, cur_num)

                arg_list.append(MacroArg(start_index=cur_match.start(), number_str=cur_num_str, is_escaped=False))
        except StopIteration:
            pass

        # Make sure the argument numbers are continuous
        if len(arg_nums) != max_arg_num:
            self.perror(f"Not all numbers between 1 and {max_arg_num} are present in the argument placeholders")
            return

        # Find all escaped arguments
        escaped_matches = re.finditer(MacroArg.macro_escaped_arg_pattern, value)

        try:
            while True:
                cur_match = escaped_matches.__next__()

                # Get the number string between the braces
                cur_num_str = re.findall(MacroArg.digit_pattern, cur_match.group())[0]

                arg_list.append(MacroArg(start_index=cur_match.start(), number_str=cur_num_str, is_escaped=True))
        except StopIteration:
            pass

        # Set the macro
        result = "overwritten" if args.name in self.macros else "created"
        self.poutput(f"Macro '{args.name}' {result}")

        self.macros[args.name] = Macro(name=args.name, value=value, minimum_arg_count=max_arg_num, arg_list=arg_list)
        self.last_result = True

    # macro -> delete
    @classmethod
    def _build_macro_delete_parser(cls) -> Cmd2ArgumentParser:
        macro_delete_description = "Delete specified macros or all macros if --all is used."

        macro_delete_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description=macro_delete_description)
        macro_delete_parser.add_argument('-a', '--all', action='store_true', help="delete all macros")
        macro_delete_parser.add_argument(
            'names',
            nargs=argparse.ZERO_OR_MORE,
            help='macro(s) to delete',
            choices_provider=cls._get_macro_completion_items,
            descriptive_headers=["Value"],
        )

        return macro_delete_parser

    @as_subcommand_to('macro', 'delete', _build_macro_delete_parser, help="delete macros")
    def _macro_delete(self, args: argparse.Namespace) -> None:
        """Delete macros."""
        self.last_result = True

        if args.all:
            self.macros.clear()
            self.poutput("All macros deleted")
        elif not args.names:
            self.perror("Either --all or macro name(s) must be specified")
            self.last_result = False
        else:
            for cur_name in utils.remove_duplicates(args.names):
                if cur_name in self.macros:
                    del self.macros[cur_name]
                    self.poutput(f"Macro '{cur_name}' deleted")
                else:
                    self.perror(f"Macro '{cur_name}' does not exist")

    # macro -> list
    macro_list_help = "list macros"
    macro_list_description = Text.assemble(
        "List specified macros in a reusable form that can be saved to a startup script to preserve macros across sessions.",
        "\n\n",
        "Without arguments, all macros will be listed.",
    )

    macro_list_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description=macro_list_description)
    macro_list_parser.add_argument(
        'names',
        nargs=argparse.ZERO_OR_MORE,
        help='macro(s) to list',
        choices_provider=_get_macro_completion_items,
        descriptive_headers=["Value"],
    )

    @as_subcommand_to('macro', 'list', macro_list_parser, help=macro_list_help)
    def _macro_list(self, args: argparse.Namespace) -> None:
        """List some or all macros as 'macro create' commands."""
        self.last_result = {}  # dict[macro_name, macro_value]

        tokens_to_quote = constants.REDIRECTION_TOKENS
        tokens_to_quote.extend(self.statement_parser.terminators)

        to_list = utils.remove_duplicates(args.names) if args.names else sorted(self.macros, key=self.default_sort_key)

        not_found: list[str] = []
        for name in to_list:
            if name not in self.macros:
                not_found.append(name)
                continue

            # Quote redirection and terminator tokens for the 'macro create' command
            tokens = shlex_split(self.macros[name].value)
            command = tokens[0]
            command_args = tokens[1:]
            utils.quote_specific_tokens(command_args, tokens_to_quote)

            val = command
            if command_args:
                val += ' ' + ' '.join(command_args)

            self.poutput(f"macro create {name} {val}")
            self.last_result[name] = val

        for name in not_found:
            self.perror(f"Macro '{name}' not found")

    def complete_help_command(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        """Completes the command argument of help."""
        # Complete token against topics and visible commands
        topics = set(self.get_help_topics())
        visible_commands = set(self.get_visible_commands())
        strs_to_match = list(topics | visible_commands)
        return self.basic_complete(text, line, begidx, endidx, strs_to_match)

    def complete_help_subcommands(
        self, text: str, line: str, begidx: int, endidx: int, arg_tokens: dict[str, list[str]]
    ) -> list[str]:
        """Completes the subcommands argument of help."""
        # Make sure we have a command whose subcommands we will complete
        command = arg_tokens['command'][0]
        if not command:
            return []

        # Check if this command uses argparse
        if (func := self.cmd_func(command)) is None or (argparser := self._command_parsers.get(func)) is None:
            return []

        completer = argparse_completer.DEFAULT_AP_COMPLETER(argparser, self)
        return completer.complete_subcommand_help(text, line, begidx, endidx, arg_tokens['subcommands'])

    def _build_command_info(self) -> tuple[dict[str, list[str]], list[str], list[str], list[str]]:
        """Categorizes and sorts visible commands and help topics for display.

        :return: tuple containing:
                  - dictionary mapping category names to lists of command names
                  - list of documented command names
                  - list of undocumented command names
                  - list of help topic names that are not also commands
        """
        # Get a sorted list of help topics
        help_topics = sorted(self.get_help_topics(), key=self.default_sort_key)

        # Get a sorted list of visible command names
        visible_commands = sorted(self.get_visible_commands(), key=self.default_sort_key)
        cmds_doc: list[str] = []
        cmds_undoc: list[str] = []
        cmds_cats: dict[str, list[str]] = {}
        for command in visible_commands:
            func = cast(CommandFunc, self.cmd_func(command))
            has_help_func = False
            has_parser = func in self._command_parsers

            if command in help_topics:
                # Prevent the command from showing as both a command and help topic in the output
                help_topics.remove(command)

                # Non-argparse commands can have help_functions for their documentation
                has_help_func = not has_parser

            if hasattr(func, constants.CMD_ATTR_HELP_CATEGORY):
                category: str = getattr(func, constants.CMD_ATTR_HELP_CATEGORY)
                cmds_cats.setdefault(category, [])
                cmds_cats[category].append(command)
            elif func.__doc__ or has_help_func or has_parser:
                cmds_doc.append(command)
            else:
                cmds_undoc.append(command)
        return cmds_cats, cmds_doc, cmds_undoc, help_topics

    @classmethod
    def _build_help_parser(cls) -> Cmd2ArgumentParser:
        help_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(
            description="List available commands or provide detailed help for a specific command."
        )
        help_parser.add_argument(
            '-v',
            '--verbose',
            action='store_true',
            help="print a list of all commands with descriptions of each",
        )
        help_parser.add_argument(
            'command',
            nargs=argparse.OPTIONAL,
            help="command to retrieve help for",
            completer=cls.complete_help_command,
        )
        help_parser.add_argument(
            'subcommands',
            nargs=argparse.REMAINDER,
            help="subcommand(s) to retrieve help for",
            completer=cls.complete_help_subcommands,
        )
        return help_parser

    @with_argparser(_build_help_parser)
    def do_help(self, args: argparse.Namespace) -> None:
        """List available commands or provide detailed help for a specific command."""
        self.last_result = True

        if not args.command or args.verbose:
            cmds_cats, cmds_doc, cmds_undoc, help_topics = self._build_command_info()

            if self.doc_leader:
                self.poutput()
                self.poutput(Text(self.doc_leader, style=Cmd2Style.HELP_LEADER))
            self.poutput()

            # Print any categories first and then the remaining documented commands.
            sorted_categories = sorted(cmds_cats.keys(), key=self.default_sort_key)
            all_cmds = {category: cmds_cats[category] for category in sorted_categories}
            if all_cmds:
                all_cmds[self.default_category] = cmds_doc
            else:
                all_cmds[self.doc_header] = cmds_doc

            # Used to provide verbose table separation for better readability.
            previous_table_printed = False

            for category, commands in all_cmds.items():
                if previous_table_printed:
                    self.poutput()

                self._print_documented_command_topics(category, commands, args.verbose)
                previous_table_printed = bool(commands) and args.verbose

            if previous_table_printed and (help_topics or cmds_undoc):
                self.poutput()

            self.print_topics(self.misc_header, help_topics, 15, 80)
            self.print_topics(self.undoc_header, cmds_undoc, 15, 80)

        else:
            # Getting help for a specific command
            func = self.cmd_func(args.command)
            help_func = getattr(self, constants.HELP_FUNC_PREFIX + args.command, None)
            argparser = None if func is None else self._command_parsers.get(func)

            # If the command function uses argparse, then use argparse's help
            if func is not None and argparser is not None:
                completer = argparse_completer.DEFAULT_AP_COMPLETER(argparser, self)
                completer.print_help(args.subcommands, self.stdout)

            # If the command has a custom help function, then call it
            elif help_func is not None:
                help_func()

            # If the command function has a docstring, then print it
            elif func is not None and func.__doc__ is not None:
                self.poutput(pydoc.getdoc(func))

            # If there is no help information then print an error
            else:
                err_msg = self.help_error.format(args.command)
                self.perror(err_msg, style=None)
                self.last_result = False

    def print_topics(self, header: str, cmds: list[str] | None, cmdlen: int, maxcol: int) -> None:  # noqa: ARG002
        """Print groups of commands and topics in columns and an optional header.

        Override of cmd's print_topics() to use Rich.

        :param header: string to print above commands being printed
        :param cmds: list of topics to print
        :param cmdlen: unused, even by cmd's version
        :param maxcol: max number of display columns to fit into
        """
        if not cmds:
            return

        # Print a row that looks like a table header.
        if header:
            header_grid = Table.grid()
            header_grid.add_row(Text(header, style=Cmd2Style.HELP_HEADER))
            header_grid.add_row(Rule(characters=self.ruler, style=Cmd2Style.TABLE_BORDER))
            self.poutput(header_grid, soft_wrap=False)

        # Subtract 1 from maxcol to account for a one-space right margin.
        maxcol = min(maxcol, ru.console_width()) - 1
        self.columnize(cmds, maxcol)
        self.poutput()

    def _print_documented_command_topics(self, header: str, cmds: list[str], verbose: bool) -> None:
        """Print topics which are documented commands, switching between verbose or traditional output."""
        import io

        if not cmds:
            return

        if not verbose:
            self.print_topics(header, cmds, 15, 80)
            return

        # Create a grid to hold the header and the topics table
        category_grid = Table.grid()
        category_grid.add_row(Text(header, style=Cmd2Style.HELP_HEADER))
        category_grid.add_row(Rule(characters=self.ruler, style=Cmd2Style.TABLE_BORDER))

        topics_table = Table(
            Column("Name", no_wrap=True),
            Column("Description", overflow="fold"),
            box=rich.box.SIMPLE_HEAD,
            show_edge=False,
            border_style=Cmd2Style.TABLE_BORDER,
        )

        # Try to get the documentation string for each command
        topics = self.get_help_topics()
        for command in cmds:
            if (cmd_func := self.cmd_func(command)) is None:
                continue

            doc: str | None

            # Non-argparse commands can have help_functions for their documentation
            if command in topics:
                help_func = getattr(self, constants.HELP_FUNC_PREFIX + command)
                result = io.StringIO()

                # try to redirect system stdout
                with contextlib.redirect_stdout(result):
                    # save our internal stdout
                    stdout_orig = self.stdout
                    try:
                        # redirect our internal stdout
                        self.stdout = cast(TextIO, result)
                        help_func()
                    finally:
                        with self.sigint_protection:
                            # restore internal stdout
                            self.stdout = stdout_orig
                doc = result.getvalue()

            else:
                doc = cmd_func.__doc__

            # Attempt to locate the first documentation block
            cmd_desc = strip_doc_annotations(doc) if doc else ''

            # Add this command to the table
            topics_table.add_row(command, cmd_desc)

        category_grid.add_row(topics_table)
        self.poutput(category_grid, soft_wrap=False)
        self.poutput()

    def render_columns(self, str_list: list[str] | None, display_width: int = 80) -> str:
        """Render a list of single-line strings as a compact set of columns.

        This method correctly handles strings containing ANSI style sequences and
        full-width characters (like those used in CJK languages). Each column is
        only as wide as necessary and columns are separated by two spaces.

        :param str_list: list of single-line strings to display
        :param display_width: max number of display columns to fit into
        :return: a string containing the columnized output
        """
        if not str_list:
            return ""

        size = len(str_list)
        if size == 1:
            return str_list[0]

        rows: list[str] = []

        # Try every row count from 1 upwards
        for nrows in range(1, len(str_list)):
            ncols = (size + nrows - 1) // nrows
            colwidths = []
            totwidth = -2
            for col in range(ncols):
                colwidth = 0
                for row in range(nrows):
                    i = row + nrows * col
                    if i >= size:
                        break
                    x = str_list[i]
                    colwidth = max(colwidth, su.str_width(x))
                colwidths.append(colwidth)
                totwidth += colwidth + 2
                if totwidth > display_width:
                    break
            if totwidth <= display_width:
                break
        else:
            # The output is wider than display_width. Print 1 column with each string on its own row.
            nrows = len(str_list)
            ncols = 1
            max_width = max(su.str_width(s) for s in str_list)
            colwidths = [max_width]
        for row in range(nrows):
            texts = []
            for col in range(ncols):
                i = row + nrows * col
                x = "" if i >= size else str_list[i]
                texts.append(x)
            while texts and not texts[-1]:
                del texts[-1]
            for col in range(len(texts)):
                texts[col] = su.align_left(texts[col], width=colwidths[col])
            rows.append("  ".join(texts))

        return "\n".join(rows)

    def columnize(self, str_list: list[str] | None, display_width: int = 80) -> None:
        """Display a list of single-line strings as a compact set of columns.

        Override of cmd's columnize() that uses the render_columns() method.
        The method correctly handles strings with ANSI style sequences and
        full-width characters (like those used in CJK languages).

        :param str_list: list of single-line strings to display
        :param display_width: max number of display columns to fit into
        """
        columnized_strs = self.render_columns(str_list, display_width)
        self.poutput(columnized_strs)

    @staticmethod
    def _build_shortcuts_parser() -> Cmd2ArgumentParser:
        return argparse_custom.DEFAULT_ARGUMENT_PARSER(description="List available shortcuts.")

    @with_argparser(_build_shortcuts_parser)
    def do_shortcuts(self, _: argparse.Namespace) -> None:
        """List available shortcuts."""
        # Sort the shortcut tuples by name
        sorted_shortcuts = sorted(self.statement_parser.shortcuts, key=lambda x: self.default_sort_key(x[0]))
        result = "\n".join(f'{sc[0]}: {sc[1]}' for sc in sorted_shortcuts)
        self.poutput(f"Shortcuts for other commands:\n{result}")
        self.last_result = True

    @staticmethod
    def _build_eof_parser() -> Cmd2ArgumentParser:
        eof_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description="Called when Ctrl-D is pressed.")
        eof_parser.epilog = eof_parser.create_text_group(
            "Note",
            "This command is for internal use and is not intended to be called from the command line.",
        )

        return eof_parser

    @with_argparser(_build_eof_parser)
    def do_eof(self, _: argparse.Namespace) -> bool | None:
        """Quit with no arguments, called when Ctrl-D is pressed.

        This can be overridden if quit should be called differently.
        """
        self.poutput()

        # self.last_result will be set by do_quit()
        return self.do_quit('')

    @staticmethod
    def _build_quit_parser() -> Cmd2ArgumentParser:
        return argparse_custom.DEFAULT_ARGUMENT_PARSER(description="Exit this application.")

    @with_argparser(_build_quit_parser)
    def do_quit(self, _: argparse.Namespace) -> bool | None:
        """Exit this application."""
        # Return True to stop the command loop
        self.last_result = True
        return True

    def select(self, opts: str | list[str] | list[tuple[Any, str | None]], prompt: str = 'Your choice? ') -> Any:
        """Present a numbered menu to the user.

        Modeled after the bash shell's SELECT.  Returns the item chosen.

        Argument ``opts`` can be:

          | a single string -> will be split into one-word options
          | a list of strings -> will be offered as options
          | a list of tuples -> interpreted as (value, text), so
                                that the return value can differ from
                                the text advertised to the user
        """
        local_opts: list[str] | list[tuple[Any, str | None]]
        if isinstance(opts, str):
            local_opts = cast(list[tuple[Any, str | None]], list(zip(opts.split(), opts.split(), strict=False)))
        else:
            local_opts = opts
        fulloptions: list[tuple[Any, str | None]] = []
        for opt in local_opts:
            if isinstance(opt, str):
                fulloptions.append((opt, opt))
            else:
                try:
                    fulloptions.append((opt[0], opt[1]))
                except IndexError:
                    fulloptions.append((opt[0], opt[0]))
        for idx, (_, text) in enumerate(fulloptions):
            self.poutput('  %2d. %s' % (idx + 1, text))  # noqa: UP031

        while True:
            try:
                response = self.read_input(prompt)
            except EOFError:
                response = ''
                self.poutput()
            except KeyboardInterrupt:
                self.poutput('^C')
                raise

            if not response:
                continue

            try:
                choice = int(response)
                if choice < 1:
                    raise IndexError  # noqa: TRY301
                return fulloptions[choice - 1][0]
            except (ValueError, IndexError):
                self.poutput(f"'{response}' isn't a valid choice. Pick a number between 1 and {len(fulloptions)}:")

    @classmethod
    def _build_base_set_parser(cls) -> Cmd2ArgumentParser:
        # When tab completing value, we recreate the set command parser with a value argument specific to
        # the settable being edited. To make this easier, define a base parser with all the common elements.
        set_description = Text.assemble(
            "Set a settable parameter or show current settings of parameters.",
            "\n\n",
            (
                "Call without arguments for a list of all settable parameters with their values. "
                "Call with just param to view that parameter's value."
            ),
        )
        base_set_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description=set_description)
        base_set_parser.add_argument(
            'param',
            nargs=argparse.OPTIONAL,
            help='parameter to set or view',
            choices_provider=cls._get_settable_completion_items,
            descriptive_headers=["Value", "Description"],
        )

        return base_set_parser

    def complete_set_value(
        self, text: str, line: str, begidx: int, endidx: int, arg_tokens: dict[str, list[str]]
    ) -> list[str]:
        """Completes the value argument of set."""
        param = arg_tokens['param'][0]
        try:
            settable = self.settables[param]
        except KeyError as exc:
            raise CompletionError(param + " is not a settable parameter") from exc

        # Create a parser with a value field based on this settable
        settable_parser = self._build_base_set_parser()

        # Settables with choices list the values of those choices instead of the arg name
        # in help text and this shows in tab completion hints. Set metavar to avoid this.
        arg_name = 'value'
        settable_parser.add_argument(
            arg_name,
            metavar=arg_name,
            help=settable.description,
            choices=settable.choices,
            choices_provider=settable.choices_provider,
            completer=settable.completer,
        )

        completer = argparse_completer.DEFAULT_AP_COMPLETER(settable_parser, self)

        # Use raw_tokens since quotes have been preserved
        _, raw_tokens = self.tokens_for_completion(line, begidx, endidx)
        return completer.complete(text, line, begidx, endidx, raw_tokens[1:])

    @classmethod
    def _build_set_parser(cls) -> Cmd2ArgumentParser:
        # Create the parser for the set command
        set_parser = cls._build_base_set_parser()
        set_parser.add_argument(
            'value',
            nargs=argparse.OPTIONAL,
            help='new value for settable',
            completer=cls.complete_set_value,
            suppress_tab_hint=True,
        )

        return set_parser

    # Preserve quotes so users can pass in quoted empty strings and flags (e.g. -h) as the value
    @with_argparser(_build_set_parser, preserve_quotes=True)
    def do_set(self, args: argparse.Namespace) -> None:
        """Set a settable parameter or show current settings of parameters."""
        self.last_result = False

        if not self.settables:
            self.pwarning("There are no settable parameters")
            return

        if args.param:
            try:
                settable = self.settables[args.param]
            except KeyError:
                self.perror(f"Parameter '{args.param}' not supported (type 'set' for list of parameters).")
                return

            if args.value:
                # Try to update the settable's value
                try:
                    orig_value = settable.value
                    settable.value = su.strip_quotes(args.value)
                except ValueError as ex:
                    self.perror(f"Error setting {args.param}: {ex}")
                else:
                    self.poutput(f"{args.param} - was: {orig_value!r}\nnow: {settable.value!r}")
                    self.last_result = True
                return

            # Show one settable
            to_show: list[str] = [args.param]
        else:
            # Show all settables
            to_show = list(self.settables.keys())

        # Define the table structure
        settable_table = Table(
            Column("Name", no_wrap=True),
            Column("Value", overflow="fold"),
            Column("Description", overflow="fold"),
            box=rich.box.SIMPLE_HEAD,
            show_edge=False,
            border_style=Cmd2Style.TABLE_BORDER,
        )

        # Build the table and populate self.last_result
        self.last_result = {}  # dict[settable_name, settable_value]

        for param in sorted(to_show, key=self.default_sort_key):
            settable = self.settables[param]
            settable_table.add_row(
                param,
                str(settable.value),
                settable.description,
            )
            self.last_result[param] = settable.value

        self.poutput()
        self.poutput(settable_table, soft_wrap=False)
        self.poutput()

    @classmethod
    def _build_shell_parser(cls) -> Cmd2ArgumentParser:
        shell_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description="Execute a command as if at the OS prompt.")
        shell_parser.add_argument('command', help='the command to run', completer=cls.shell_cmd_complete)
        shell_parser.add_argument(
            'command_args', nargs=argparse.REMAINDER, help='arguments to pass to command', completer=cls.path_complete
        )

        return shell_parser

    # Preserve quotes since we are passing these strings to the shell
    @with_argparser(_build_shell_parser, preserve_quotes=True)
    def do_shell(self, args: argparse.Namespace) -> None:
        """Execute a command as if at the OS prompt."""
        import signal
        import subprocess

        kwargs: dict[str, Any] = {}

        # Set OS-specific parameters
        if sys.platform.startswith('win'):
            # Windows returns STATUS_CONTROL_C_EXIT when application stopped by Ctrl-C
            ctrl_c_ret_code = 0xC000013A
        else:
            # On POSIX, Popen() returns -SIGINT when application stopped by Ctrl-C
            ctrl_c_ret_code = signal.SIGINT.value * -1

            # On POSIX with shell=True, Popen() defaults to /bin/sh as the shell.
            # sh reports an incorrect return code for some applications when Ctrl-C is pressed within that
            # application (e.g. less). Since sh received the SIGINT, it sets the return code to reflect being
            # closed by SIGINT even though less did not exit upon a Ctrl-C press. In the same situation, other
            # shells like bash and zsh report the actual return code of less. Therefore, we will try to run the
            # user's preferred shell which most likely will be something other than sh. This also allows the user
            # to run builtin commands of their preferred shell.
            shell = os.environ.get("SHELL")
            if shell:
                kwargs['executable'] = shell

        # Create a list of arguments to shell
        tokens = [args.command, *args.command_args]

        # Expand ~ where needed
        utils.expand_user_in_tokens(tokens)
        expanded_command = ' '.join(tokens)

        # Prevent KeyboardInterrupts while in the shell process. The shell process will
        # still receive the SIGINT since it is in the same process group as us.
        with self.sigint_protection:
            # For any stream that is a StdSim, we will use a pipe so we can capture its output
            proc = subprocess.Popen(  # noqa: S602
                expanded_command,
                stdout=subprocess.PIPE if isinstance(self.stdout, utils.StdSim) else self.stdout,  # type: ignore[unreachable]
                stderr=subprocess.PIPE if isinstance(sys.stderr, utils.StdSim) else sys.stderr,
                shell=True,
                **kwargs,
            )

            proc_reader = utils.ProcReader(proc, self.stdout, sys.stderr)
            proc_reader.wait()

            # Save the return code of the application for use in a pyscript
            self.last_result = proc.returncode

            # If the process was stopped by Ctrl-C, then inform the caller by raising a KeyboardInterrupt.
            # This is to support things like stop_on_keyboard_interrupt in runcmds_plus_hooks().
            if proc.returncode == ctrl_c_ret_code:
                self._raise_keyboard_interrupt()

    @staticmethod
    def _reset_py_display() -> None:
        """Reset the dynamic objects in the sys module that the py and ipy consoles fight over.

        When a Python console starts it adopts certain display settings if they've already been set.
        If an ipy console has previously been run, then py uses its settings and ends up looking
        like an ipy console in terms of prompt and exception text. This method forces the Python
        console to create its own display settings since they won't exist.

        IPython does not have this problem since it always overwrites the display settings when it
        is run. Therefore, this method only needs to be called before creating a Python console.
        """
        # Delete any prompts that have been set
        attributes = ['ps1', 'ps2', 'ps3']
        for cur_attr in attributes:
            with contextlib.suppress(KeyError):
                del sys.__dict__[cur_attr]

        # Reset functions
        sys.displayhook = sys.__displayhook__
        sys.excepthook = sys.__excepthook__

    def _set_up_py_shell_env(self, interp: InteractiveConsole) -> _SavedCmd2Env:
        """Set up interactive Python shell environment.

        :return: Class containing saved up cmd2 environment.
        """
        cmd2_env = _SavedCmd2Env()

        # Set up sys module for the Python console
        self._reset_py_display()

        # Enable tab completion if readline is available
        if not sys.platform.startswith('win'):
            import readline
            import rlcompleter

            # Save the current completer
            cmd2_env.completer = readline.get_completer()

            # Set the completer to use the interpreter's locals
            readline.set_completer(rlcompleter.Completer(interp.locals).complete)

            # Use the correct binding based on whether LibEdit or Readline is being used
            if 'libedit' in (readline.__doc__ or ''):
                readline.parse_and_bind("bind ^I rl_complete")
            else:
                readline.parse_and_bind("tab: complete")

        return cmd2_env

    def _restore_cmd2_env(self, cmd2_env: _SavedCmd2Env) -> None:
        """Restore cmd2 environment after exiting an interactive Python shell.

        :param cmd2_env: the environment settings to restore
        """
        # Restore the readline completer
        if not sys.platform.startswith('win'):
            import readline

            readline.set_completer(cmd2_env.completer)

    def _run_python(self, *, pyscript: str | None = None) -> bool | None:
        """Run an interactive Python shell or execute a pyscript file.

        Called by do_py() and do_run_pyscript().

        If pyscript is None, then this function runs an interactive Python shell.
        Otherwise, it runs the pyscript file.

        :param pyscript: optional path to a pyscript file to run. This is intended only to be used by do_run_pyscript()
                         after it sets up sys.argv for the script. (Defaults to None)
        :return: True if running of commands should stop
        """
        self.last_result = False

        def py_quit() -> None:
            """Exit an interactive Python environment, callable from the interactive Python console."""
            raise EmbeddedConsoleExit

        from .py_bridge import (
            PyBridge,
        )

        add_to_history = self.scripts_add_to_history if pyscript else True
        py_bridge = PyBridge(self, add_to_history=add_to_history)
        saved_sys_path = None

        if self.in_pyscript():
            self.perror("Recursively entering interactive Python shells is not allowed")
            return None

        try:
            self._in_py = True
            py_code_to_run = ''

            # Make a copy of self.py_locals for the locals dictionary in the Python environment we are creating.
            # This is to prevent pyscripts from editing it. (e.g. locals().clear()). It also ensures a pyscript's
            # environment won't be filled with data from a previously run pyscript. Only make a shallow copy since
            # it's OK for py_locals to contain objects which are editable in a pyscript.
            local_vars = self.py_locals.copy()
            local_vars[self.py_bridge_name] = py_bridge
            local_vars['quit'] = py_quit
            local_vars['exit'] = py_quit

            if self.self_in_py:
                local_vars['self'] = self

            # Handle case where we were called by do_run_pyscript()
            if pyscript is not None:
                # Read the script file
                expanded_filename = os.path.expanduser(pyscript)

                try:
                    with open(expanded_filename) as f:
                        py_code_to_run = f.read()
                except OSError as ex:
                    self.perror(f"Error reading script file '{expanded_filename}': {ex}")
                    return None

                local_vars['__name__'] = '__main__'
                local_vars['__file__'] = expanded_filename

                # Place the script's directory at sys.path[0] just as Python does when executing a script
                saved_sys_path = list(sys.path)
                sys.path.insert(0, os.path.dirname(os.path.abspath(expanded_filename)))

            else:
                # This is the default name chosen by InteractiveConsole when no locals are passed in
                local_vars['__name__'] = '__console__'

            # Create the Python interpreter
            self.last_result = True
            interp = InteractiveConsole(locals=local_vars)

            # Check if we are running Python code
            if py_code_to_run:
                try:  # noqa: SIM105
                    interp.runcode(py_code_to_run)  # type: ignore[arg-type]
                except BaseException:  # noqa: BLE001, S110
                    # We don't care about any exception that happened in the Python code
                    pass

            # Otherwise we will open an interactive Python shell
            else:
                cprt = 'Type "help", "copyright", "credits" or "license" for more information.'
                instructions = (
                    'Use `Ctrl-D` (Unix) / `Ctrl-Z` (Windows), `quit()`, `exit()` to exit.\n'
                    f'Run CLI commands with: {self.py_bridge_name}("command ...")'
                )
                banner = f"Python {sys.version} on {sys.platform}\n{cprt}\n\n{instructions}\n"

                saved_cmd2_env = None

                try:
                    # Get sigint protection while we set up the Python shell environment
                    with self.sigint_protection:
                        saved_cmd2_env = self._set_up_py_shell_env(interp)

                    # Since quit() or exit() raise an EmbeddedConsoleExit, interact() exits before printing
                    # the exitmsg. Therefore, we will not provide it one and print it manually later.
                    interp.interact(banner=banner, exitmsg='')
                except BaseException:  # noqa: BLE001, S110
                    # We don't care about any exception that happened in the interactive console
                    pass
                finally:
                    # Get sigint protection while we restore cmd2 environment settings
                    with self.sigint_protection:
                        if saved_cmd2_env is not None:
                            self._restore_cmd2_env(saved_cmd2_env)
                    self.poutput("Now exiting Python shell...")

        finally:
            with self.sigint_protection:
                if saved_sys_path is not None:
                    sys.path = saved_sys_path
                self._in_py = False

        return py_bridge.stop

    @staticmethod
    def _build_py_parser() -> Cmd2ArgumentParser:
        return argparse_custom.DEFAULT_ARGUMENT_PARSER(description="Run an interactive Python shell.")

    @with_argparser(_build_py_parser)
    def do_py(self, _: argparse.Namespace) -> bool | None:
        """Run an interactive Python shell.

        :return: True if running of commands should stop.
        """
        # self.last_result will be set by _run_python()
        return self._run_python()

    @classmethod
    def _build_run_pyscript_parser(cls) -> Cmd2ArgumentParser:
        run_pyscript_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(
            description="Run Python script within this application's environment."
        )
        run_pyscript_parser.add_argument('script_path', help='path to the script file', completer=cls.path_complete)
        run_pyscript_parser.add_argument(
            'script_arguments', nargs=argparse.REMAINDER, help='arguments to pass to script', completer=cls.path_complete
        )

        return run_pyscript_parser

    @with_argparser(_build_run_pyscript_parser)
    def do_run_pyscript(self, args: argparse.Namespace) -> bool | None:
        """Run Python script within this application's environment.

        :return: True if running of commands should stop
        """
        self.last_result = False

        # Expand ~ before placing this path in sys.argv just as a shell would
        args.script_path = os.path.expanduser(args.script_path)

        # Add some protection against accidentally running a non-Python file. The happens when users
        # mix up run_script and run_pyscript.
        if not args.script_path.endswith('.py'):
            self.pwarning(f"'{args.script_path}' does not have a .py extension")
            selection = self.select('Yes No', 'Continue to try to run it as a Python script? ')
            if selection != 'Yes':
                return None

        # Save current command line arguments
        orig_args = sys.argv

        try:
            # Overwrite sys.argv to allow the script to take command line arguments
            sys.argv = [args.script_path, *args.script_arguments]

            # self.last_result will be set by _run_python()
            py_return = self._run_python(pyscript=args.script_path)
        finally:
            # Restore command line arguments to original state
            sys.argv = orig_args

        return py_return

    @staticmethod
    def _build_ipython_parser() -> Cmd2ArgumentParser:
        return argparse_custom.DEFAULT_ARGUMENT_PARSER(description="Run an interactive IPython shell.")

    @with_argparser(_build_ipython_parser)
    def do_ipy(self, _: argparse.Namespace) -> bool | None:  # pragma: no cover
        """Run an interactive IPython shell.

        :return: True if running of commands should stop
        """
        self.last_result = False

        # Detect whether IPython is installed
        try:
            import traitlets.config.loader as traitlets_loader

            # Allow users to install ipython from a cmd2 prompt when needed and still have ipy command work
            try:
                _dummy = start_ipython  # noqa: F823
            except NameError:
                from IPython import start_ipython

            from IPython.terminal.interactiveshell import (
                TerminalInteractiveShell,
            )
            from IPython.terminal.ipapp import (
                TerminalIPythonApp,
            )
        except ImportError:
            self.perror("IPython package is not installed")
            return None

        from .py_bridge import (
            PyBridge,
        )

        if self.in_pyscript():
            self.perror("Recursively entering interactive Python shells is not allowed")
            return None

        self.last_result = True

        try:
            self._in_py = True
            py_bridge = PyBridge(self)

            # Make a copy of self.py_locals for the locals dictionary in the IPython environment we are creating.
            # This is to prevent ipy from editing it. (e.g. locals().clear()). Only make a shallow copy since
            # it's OK for py_locals to contain objects which are editable in ipy.
            local_vars = self.py_locals.copy()
            local_vars[self.py_bridge_name] = py_bridge
            if self.self_in_py:
                local_vars['self'] = self

            # Configure IPython
            config = traitlets_loader.Config()
            config.InteractiveShell.banner2 = (
                'Entering an IPython shell. Type exit, quit, or Ctrl-D to exit.\n'
                f'Run CLI commands with: {self.py_bridge_name}("command ...")\n'
            )

            # Start IPython
            start_ipython(config=config, argv=[], user_ns=local_vars)  # type: ignore[no-untyped-call]
            self.poutput("Now exiting IPython shell...")

            # The IPython application is a singleton and won't be recreated next time
            # this function runs. That's a problem since the contents of local_vars
            # may need to be changed. Therefore, we must destroy all instances of the
            # relevant classes.
            TerminalIPythonApp.clear_instance()
            TerminalInteractiveShell.clear_instance()

            return py_bridge.stop
        finally:
            self._in_py = False

    @classmethod
    def _build_history_parser(cls) -> Cmd2ArgumentParser:
        history_description = "View, run, edit, save, or clear previously entered commands."

        history_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(
            description=history_description, formatter_class=argparse_custom.RawTextCmd2HelpFormatter
        )
        history_action_group = history_parser.add_mutually_exclusive_group()
        history_action_group.add_argument('-r', '--run', action='store_true', help='run selected history items')
        history_action_group.add_argument('-e', '--edit', action='store_true', help='edit and then run selected history items')
        history_action_group.add_argument(
            '-o',
            '--output-file',
            metavar='FILE',
            help='output commands to a script file, implies -s',
            completer=cls.path_complete,
        )
        history_action_group.add_argument(
            '-t',
            '--transcript',
            metavar='TRANSCRIPT_FILE',
            help='create a transcript file by re-running the commands, implies both -r and -s',
            completer=cls.path_complete,
        )
        history_action_group.add_argument('-c', '--clear', action='store_true', help='clear all history')

        history_format_group = history_parser.add_argument_group(title='formatting')
        history_format_group.add_argument(
            '-s',
            '--script',
            action='store_true',
            help='output commands in script format, i.e. without command numbers',
        )
        history_format_group.add_argument(
            '-x',
            '--expanded',
            action='store_true',
            help='output fully parsed commands with shortcuts, aliases, and macros expanded',
        )
        history_format_group.add_argument(
            '-v',
            '--verbose',
            action='store_true',
            help='display history and include expanded commands if they differ from the typed command',
        )
        history_format_group.add_argument(
            '-a',
            '--all',
            action='store_true',
            help='display all commands, including ones persisted from previous sessions',
        )

        history_arg_help = (
            "empty               all history items\n"
            "a                   one history item by number\n"
            "a..b, a:b, a:, ..b  items by indices (inclusive)\n"
            "string              items containing string\n"
            "/regex/             items matching regular expression"
        )
        history_parser.add_argument('arg', nargs=argparse.OPTIONAL, help=history_arg_help)

        return history_parser

    @with_argparser(_build_history_parser)
    def do_history(self, args: argparse.Namespace) -> bool | None:
        """View, run, edit, save, or clear previously entered commands.

        :return: True if running of commands should stop
        """
        self.last_result = False

        # -v must be used alone with no other options
        if args.verbose:  # noqa: SIM102
            if args.clear or args.edit or args.output_file or args.run or args.transcript or args.expanded or args.script:
                self.poutput("-v cannot be used with any other options")
                return None

        # -s and -x can only be used if none of these options are present: [-c -r -e -o -t]
        if (args.script or args.expanded) and (args.clear or args.edit or args.output_file or args.run or args.transcript):
            self.poutput("-s and -x cannot be used with -c, -r, -e, -o, or -t")
            return None

        if args.clear:
            self.last_result = True

            # Clear command and prompt-toolkit history
            self.history.clear()

            if self.persistent_history_file:
                try:
                    os.remove(self.persistent_history_file)
                except FileNotFoundError:
                    pass
                except OSError as ex:
                    self.perror(f"Error removing history file '{self.persistent_history_file}': {ex}")
                    self.last_result = False
                    return None

            return None

        # If an argument was supplied, then retrieve partial contents of the history, otherwise retrieve it all
        history = self._get_history(args)

        if args.run:
            if not args.arg:
                self.perror("Cowardly refusing to run all previously entered commands.")
                self.perror("If this is what you want to do, specify '1:' as the range of history.")
            else:
                stop = self.runcmds_plus_hooks(list(history.values()))
                self.last_result = True
                return stop
        elif args.edit:
            fd, fname = tempfile.mkstemp(suffix='.txt', text=True)
            fobj: TextIO
            with os.fdopen(fd, 'w') as fobj:
                for command in history.values():
                    if command.statement.multiline_command:
                        fobj.write(f'{command.expanded}\n')
                    else:
                        fobj.write(f'{command.raw}\n')
            try:
                self.run_editor(fname)

                # self.last_result will be set by do_run_script()
                return self.do_run_script(su.quote(fname))
            finally:
                os.remove(fname)
        elif args.output_file:
            full_path = os.path.abspath(os.path.expanduser(args.output_file))
            try:
                with open(full_path, 'w') as fobj:
                    for item in history.values():
                        if item.statement.multiline_command:
                            fobj.write(f"{item.expanded}\n")
                        else:
                            fobj.write(f"{item.raw}\n")
                plural = '' if len(history) == 1 else 's'
            except OSError as ex:
                self.perror(f"Error saving history file '{full_path}': {ex}")
            else:
                self.pfeedback(f"{len(history)} command{plural} saved to {full_path}")
                self.last_result = True
        elif args.transcript:
            # self.last_result will be set by _generate_transcript()
            self._generate_transcript(list(history.values()), args.transcript)
        else:
            # Display the history items retrieved
            for idx, hi in history.items():
                self.poutput(hi.pr(idx, script=args.script, expanded=args.expanded, verbose=args.verbose))
            self.last_result = history
        return None

    def _get_history(self, args: argparse.Namespace) -> 'OrderedDict[int, HistoryItem]':
        """If an argument was supplied, then retrieve partial contents of the history; otherwise retrieve entire history.

        This function returns a dictionary with history items keyed by their 1-based index in ascending order.
        """
        if args.arg:
            try:
                int_arg = int(args.arg)
                return OrderedDict({int_arg: self.history.get(int_arg)})
            except ValueError:
                pass

            if '..' in args.arg or ':' in args.arg:
                # Get a slice of history
                history = self.history.span(args.arg, args.all)
            elif args.arg.startswith(r'/') and args.arg.endswith(r'/'):
                history = self.history.regex_search(args.arg, args.all)
            else:
                history = self.history.str_search(args.arg, args.all)
        else:
            # Get a copy of the history so it doesn't get mutated while we are using it
            history = self.history.span(':', args.all)
        return history

    def _initialize_history(self, hist_file: str) -> None:
        """Initialize history using history related attributes.

        :param hist_file: optional path to persistent history file. If specified, then history from
                          previous sessions will be included. Additionally, all history will be written
                          to this file when the application exits.
        """
        self.history = History()

        # With no persistent history, nothing else in this method is relevant
        if not hist_file:
            self.persistent_history_file = hist_file
            return

        hist_file = os.path.abspath(os.path.expanduser(hist_file))

        # On Windows, trying to open a directory throws a permission
        # error, not a `IsADirectoryError`. So we'll check it ourselves.
        if os.path.isdir(hist_file):
            self.perror(f"Persistent history file '{hist_file}' is a directory")
            return

        # Create the directory for the history file if it doesn't already exist
        hist_file_dir = os.path.dirname(hist_file)
        try:
            os.makedirs(hist_file_dir, exist_ok=True)
        except OSError as ex:
            self.perror(f"Error creating persistent history file directory '{hist_file_dir}': {ex}")
            return

        # Read history file
        try:
            with open(hist_file, 'rb') as fobj:
                compressed_bytes = fobj.read()
        except FileNotFoundError:
            compressed_bytes = b""
        except OSError as ex:
            self.perror(f"Cannot read persistent history file '{hist_file}': {ex}")
            return

        # Register a function to write history at save
        import atexit

        self.persistent_history_file = hist_file
        atexit.register(self._persist_history)

        # Empty or nonexistent history file. Nothing more to do.
        if not compressed_bytes:
            return

        # Decompress history data
        try:
            import lzma as decompress_lib

            decompress_exceptions: tuple[type[Exception]] = (decompress_lib.LZMAError,)
        except ModuleNotFoundError:  # pragma: no cover
            import bz2 as decompress_lib  # type: ignore[no-redef]

            decompress_exceptions: tuple[type[Exception]] = (OSError, ValueError)  # type: ignore[no-redef]

        try:
            history_json = decompress_lib.decompress(compressed_bytes).decode(encoding='utf-8')
        except decompress_exceptions as ex:
            self.perror(
                f"Error decompressing persistent history data '{hist_file}': {ex}\n"
                f"The history file will be recreated when this application exits."
            )
            return

        # Decode history json
        import json

        try:
            self.history = History.from_json(history_json)
        except (json.JSONDecodeError, KeyError, ValueError) as ex:
            self.perror(
                f"Error processing persistent history data '{hist_file}': {ex}\n"
                f"The history file will be recreated when this application exits."
            )
            return

        self.history.start_session()

    def _persist_history(self) -> None:
        """Write history out to the persistent history file as compressed JSON."""
        if not self.persistent_history_file:
            return

        try:
            import lzma as compress_lib
        except ModuleNotFoundError:  # pragma: no cover
            import bz2 as compress_lib  # type: ignore[no-redef]

        self.history.truncate(self._persistent_history_length)
        history_json = self.history.to_json()
        compressed_bytes = compress_lib.compress(history_json.encode(encoding='utf-8'))

        try:
            with open(self.persistent_history_file, 'wb') as fobj:
                fobj.write(compressed_bytes)
        except OSError as ex:
            self.perror(f"Cannot write persistent history file '{self.persistent_history_file}': {ex}")

    def _generate_transcript(
        self,
        history: list[HistoryItem] | list[str],
        transcript_file: str,
        *,
        add_to_history: bool = True,
    ) -> None:
        """Generate a transcript file from a given history of commands."""
        self.last_result = False

        # Validate the transcript file path to make sure directory exists and write access is available
        transcript_path = os.path.abspath(os.path.expanduser(transcript_file))
        transcript_dir = os.path.dirname(transcript_path)
        if not os.path.isdir(transcript_dir) or not os.access(transcript_dir, os.W_OK):
            self.perror(f"'{transcript_dir}' is not a directory or you don't have write access")
            return

        commands_run = 0
        try:
            with self.sigint_protection:
                # Disable echo while we manually redirect stdout to a StringIO buffer
                saved_echo = self.echo
                saved_stdout = self.stdout
                self.echo = False

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
                if isinstance(history_item, HistoryItem):
                    history_item = history_item.raw  # noqa: PLW2901
                for line in history_item.splitlines():
                    if first:
                        command += f"{self.prompt}{line}\n"
                        first = False
                    else:
                        command += f"{self.continuation_prompt}{line}\n"
                transcript += command

                # Use a StdSim object to capture output
                stdsim = utils.StdSim(self.stdout)
                self.stdout = cast(TextIO, stdsim)

                # then run the command and let the output go into our buffer
                try:
                    stop = self.onecmd_plus_hooks(
                        history_item,
                        add_to_history=add_to_history,
                        raise_keyboard_interrupt=True,
                    )
                except KeyboardInterrupt as ex:
                    self.perror(ex)
                    stop = True

                commands_run += 1

                # add the regex-escaped output to the transcript
                transcript += stdsim.getvalue().replace('/', r'\/')

                # check if we are supposed to stop
                if stop:
                    break
        finally:
            with self.sigint_protection:
                # Restore altered attributes to their original state
                self.echo = saved_echo
                self.stdout = saved_stdout

        # Check if all commands ran
        if commands_run < len(history):
            self.pwarning(f"Command {commands_run} triggered a stop and ended transcript generation early")

        # finally, we can write the transcript out to the file
        try:
            with open(transcript_path, 'w') as fout:
                fout.write(transcript)
        except OSError as ex:
            self.perror(f"Error saving transcript file '{transcript_path}': {ex}")
        else:
            # and let the user know what we did
            plural = 'command and its output' if commands_run == 1 else 'commands and their outputs'
            self.pfeedback(f"{commands_run} {plural} saved to transcript file '{transcript_path}'")
            self.last_result = True

    @classmethod
    def _build_edit_parser(cls) -> Cmd2ArgumentParser:
        edit_description = "Run a text editor and optionally open a file with it."
        edit_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description=edit_description)
        edit_parser.epilog = edit_parser.create_text_group(
            "Note",
            Text.assemble(
                "To set a new editor, run: ",
                ("set editor <program>", Cmd2Style.COMMAND_LINE),
            ),
        )

        edit_parser.add_argument(
            'file_path',
            nargs=argparse.OPTIONAL,
            help="optional path to a file to open in editor",
            completer=cls.path_complete,
        )
        return edit_parser

    @with_argparser(_build_edit_parser)
    def do_edit(self, args: argparse.Namespace) -> None:
        """Run a text editor and optionally open a file with it."""
        # self.last_result will be set by do_shell() which is called by run_editor()
        self.run_editor(args.file_path)

    def run_editor(self, file_path: str | None = None) -> None:
        """Run a text editor and optionally open a file with it.

        :param file_path: optional path of the file to edit. Defaults to None.
        :raises ValueError: if self.editor is not set
        """
        if not self.editor:
            raise ValueError("Please use 'set editor' to specify your text editing program of choice.")

        command = su.quote(os.path.expanduser(self.editor))
        if file_path:
            command += " " + su.quote(os.path.expanduser(file_path))

        self.do_shell(command)

    @property
    def _current_script_dir(self) -> str | None:
        """Accessor to get the current script directory from the _script_dir LIFO queue."""
        if self._script_dir:
            return self._script_dir[-1]
        return None

    @classmethod
    def _build_base_run_script_parser(cls) -> Cmd2ArgumentParser:
        run_script_description = Text.assemble(
            "Run text script.",
            "\n\n",
            "Scripts should contain one command per line, entered as you would in the console.",
        )

        run_script_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description=run_script_description)
        run_script_parser.add_argument(
            'script_path',
            help="path to the script file",
            completer=cls.path_complete,
        )

        return run_script_parser

    @classmethod
    def _build_run_script_parser(cls) -> Cmd2ArgumentParser:
        run_script_parser = cls._build_base_run_script_parser()
        run_script_parser.add_argument(
            '-t',
            '--transcript',
            metavar='TRANSCRIPT_FILE',
            help='record the output of the script as a transcript file',
            completer=cls.path_complete,
        )

        return run_script_parser

    @with_argparser(_build_run_script_parser)
    def do_run_script(self, args: argparse.Namespace) -> bool | None:
        """Run text script.

        :return: True if running of commands should stop
        """
        self.last_result = False
        expanded_path = os.path.abspath(os.path.expanduser(args.script_path))

        # Add some protection against accidentally running a Python file. The happens when users
        # mix up run_script and run_pyscript.
        if expanded_path.endswith('.py'):
            self.pwarning(f"'{expanded_path}' appears to be a Python file")
            selection = self.select('Yes No', 'Continue to try to run it as a text script? ')
            if selection != 'Yes':
                return None

        try:
            # An empty file is not an error, so just return
            if os.path.getsize(expanded_path) == 0:
                self.last_result = True
                return None

            # Make sure the file is ASCII or UTF-8 encoded text
            if not utils.is_text_file(expanded_path):
                self.perror(f"'{expanded_path}' is not an ASCII or UTF-8 encoded text file")
                return None

            # Read all lines of the script
            with open(expanded_path, encoding='utf-8') as target:
                script_commands = target.read().splitlines()
        except OSError as ex:
            self.perror(f"Problem accessing script from '{expanded_path}': {ex}")
            return None

        orig_script_dir_count = len(self._script_dir)

        try:
            self._script_dir.append(os.path.dirname(expanded_path))

            if args.transcript:
                # self.last_result will be set by _generate_transcript()
                self._generate_transcript(
                    script_commands,
                    os.path.expanduser(args.transcript),
                    add_to_history=self.scripts_add_to_history,
                )
            else:
                stop = self.runcmds_plus_hooks(
                    script_commands,
                    add_to_history=self.scripts_add_to_history,
                    stop_on_keyboard_interrupt=True,
                )
                self.last_result = True
                return stop

        finally:
            with self.sigint_protection:
                # Check if a script dir was added before an exception occurred
                if orig_script_dir_count != len(self._script_dir):
                    self._script_dir.pop()
        return None

    @classmethod
    def _build_relative_run_script_parser(cls) -> Cmd2ArgumentParser:
        relative_run_script_parser = cls._build_base_run_script_parser()

        # Append to existing description
        relative_run_script_parser.description = Group(
            cast(Group, relative_run_script_parser.description),
            "\n",
            (
                "If this is called from within an already-running script, the filename will be "
                "interpreted relative to the already-running script's directory."
            ),
        )

        relative_run_script_parser.epilog = relative_run_script_parser.create_text_group(
            "Note",
            "This command is intended to be used from within a text script.",
        )

        return relative_run_script_parser

    @with_argparser(_build_relative_run_script_parser)
    def do__relative_run_script(self, args: argparse.Namespace) -> bool | None:
        """Run text script.

        This command is intended to be used from within a text script.

        :return: True if running of commands should stop
        """
        script_path = args.script_path
        # NOTE: Relative path is an absolute path, it is just relative to the current script directory
        relative_path = os.path.join(self._current_script_dir or '', script_path)

        # self.last_result will be set by do_run_script()
        return self.do_run_script(su.quote(relative_path))

    def _run_transcript_tests(self, transcript_paths: list[str]) -> None:
        """Run transcript tests for provided file(s).

        This is called when either -t is provided on the command line or the transcript_files argument is provided
        during construction of the cmd2.Cmd instance.

        :param transcript_paths: list of transcript test file paths
        """
        import time
        import unittest

        import cmd2

        from .transcript import (
            Cmd2TestCase,
        )

        class TestMyAppCase(Cmd2TestCase):
            cmdapp = self

        # Validate that there is at least one transcript file
        transcripts_expanded = utils.files_from_glob_patterns(transcript_paths, access=os.R_OK)
        if not transcripts_expanded:
            self.perror('No test files found - nothing to test')
            self.exit_code = 1
            return

        verinfo = ".".join(map(str, sys.version_info[:3]))
        num_transcripts = len(transcripts_expanded)
        plural = '' if len(transcripts_expanded) == 1 else 's'
        self.poutput(
            Rule("cmd2 transcript test", characters=self.ruler, style=Style.null()),
            style=Style(bold=True),
        )
        self.poutput(f'platform {sys.platform} -- Python {verinfo}, cmd2-{cmd2.__version__}')
        self.poutput(f'cwd: {os.getcwd()}')
        self.poutput(f'cmd2 app: {sys.argv[0]}')
        self.poutput(f'collected {num_transcripts} transcript{plural}', style=Style(bold=True))

        self.__class__.testfiles = transcripts_expanded
        sys.argv = [sys.argv[0]]  # the --test argument upsets unittest.main()
        testcase = TestMyAppCase()
        stream = cast(TextIO, utils.StdSim(sys.stderr))
        runner = unittest.TextTestRunner(stream=stream)
        start_time = time.time()
        test_results = runner.run(testcase)
        execution_time = time.time() - start_time
        if test_results.wasSuccessful():
            self.perror(stream.read(), end="", style=None)
            finish_msg = f'{num_transcripts} transcript{plural} passed in {execution_time:.3f} seconds'
            self.psuccess(Rule(finish_msg, characters=self.ruler, style=Style.null()))
        else:
            # Strip off the initial traceback which isn't particularly useful for end users
            error_str = stream.read()
            end_of_trace = error_str.find('AssertionError:')
            file_offset = error_str[end_of_trace:].find('File ')
            start = end_of_trace + file_offset

            # But print the transcript file name and line number followed by what was expected and what was observed
            self.perror(error_str[start:])

            # Return a failure error code to support automated transcript-based testing
            self.exit_code = 1

    def async_alert(self, alert_msg: str, new_prompt: str | None = None) -> None:
        """Display an important message to the user while they are at a command line prompt.

        To the user it appears as if an alert message is printed above the prompt and their
        current input text and cursor location is left alone.

        This function checks self._in_prompt to ensure a prompt is on screen.
        If the main thread is not at the prompt, a RuntimeError is raised.

        This function is only needed when you need to print an alert or update the prompt while the
        main thread is blocking at the prompt. Therefore, this should never be called from the main
        thread. Doing so will raise a RuntimeError.

        :param alert_msg: the message to display to the user
        :param new_prompt: If you also want to change the prompt that is displayed, then include it here.
                           See async_update_prompt() docstring for guidance on updating a prompt.
        :raises RuntimeError: if called from the main thread.
        :raises RuntimeError: if main thread is not currently at the prompt.
        """
        # Check if prompt is currently displayed and waiting for user input
        with self._in_prompt_lock:
            if not self._in_prompt or not self.session.app.is_running:
                raise RuntimeError("Main thread is not at the prompt")

        def _alert() -> None:
            if new_prompt is not None:
                self.prompt = new_prompt

            if alert_msg:
                # Since we are running in the loop, patch_stdout context manager from read_input
                # should be active (if tty), or at least we are in the main thread.
                print(alert_msg)

            if hasattr(self, 'session'):
                # Invalidate to force prompt update
                self.session.app.invalidate()

        # Schedule the alert to run on the main thread's event loop
        try:
            self.session.app.loop.call_soon_threadsafe(_alert)  # type: ignore[union-attr]
        except AttributeError:
            # Fallback if loop is not accessible (e.g. prompt not running or session not initialized)
            # This shouldn't happen if _in_prompt is True, unless prompt exited concurrently.
            raise RuntimeError("Event loop not available") from None

    def async_update_prompt(self, new_prompt: str) -> None:  # pragma: no cover
        """Update the command line prompt while the user is still typing at it.

        This is good for alerting the user to system changes dynamically in between commands.
        For instance you could alter the color of the prompt to indicate a system status or increase a
        counter to report an event. If you do alter the actual text of the prompt, it is best to keep
        the prompt the same width as what's on screen. Otherwise the user's input text will be shifted
        and the update will not be seamless.

        If user is at a continuation prompt while entering a multiline command, the onscreen prompt will
        not change. However, self.prompt will still be updated and display immediately after the multiline
        line command completes.

        :param new_prompt: what to change the prompt to
        :raises RuntimeError: if called from the main thread.
        :raises RuntimeError: if main thread is not currently at the prompt.
        """
        self.async_alert('', new_prompt)

    @staticmethod
    def set_window_title(title: str) -> None:  # pragma: no cover
        """Set the terminal window title.

        :param title: the new window title
        """
        set_title(title)

    def enable_command(self, command: str) -> None:
        """Enable a command by restoring its functions.

        :param command: the command being enabled
        """
        # If the commands is already enabled, then return
        if command not in self.disabled_commands:
            return

        cmd_func_name = constants.COMMAND_FUNC_PREFIX + command
        help_func_name = constants.HELP_FUNC_PREFIX + command
        completer_func_name = constants.COMPLETER_FUNC_PREFIX + command

        # Restore the command function to its original value
        dc = self.disabled_commands[command]
        setattr(self, cmd_func_name, dc.command_function)

        # Restore the help function to its original value
        if dc.help_function is None:
            delattr(self, help_func_name)
        else:
            setattr(self, help_func_name, dc.help_function)

        # Restore the completer function to its original value
        if dc.completer_function is None:
            delattr(self, completer_func_name)
        else:
            setattr(self, completer_func_name, dc.completer_function)

        # Remove the disabled command entry
        del self.disabled_commands[command]

    def enable_category(self, category: str) -> None:
        """Enable an entire category of commands.

        :param category: the category to enable
        """
        for cmd_name in list(self.disabled_commands):
            func = self.disabled_commands[cmd_name].command_function
            if getattr(func, constants.CMD_ATTR_HELP_CATEGORY, None) == category:
                self.enable_command(cmd_name)

    def disable_command(self, command: str, message_to_print: str) -> None:
        """Disable a command and overwrite its functions.

        :param command: the command being disabled
        :param message_to_print: what to print when this command is run or help is called on it while disabled

                                 The variable cmd2.COMMAND_NAME can be used as a placeholder for the name of the
                                 command being disabled.
                                 ex: message_to_print = f"{cmd2.COMMAND_NAME} is currently disabled"
        """
        # If the commands is already disabled, then return
        if command in self.disabled_commands:
            return

        # Make sure this is an actual command
        command_function = self.cmd_func(command)
        if command_function is None:
            raise AttributeError(f"'{command}' does not refer to a command")

        cmd_func_name = constants.COMMAND_FUNC_PREFIX + command
        help_func_name = constants.HELP_FUNC_PREFIX + command
        completer_func_name = constants.COMPLETER_FUNC_PREFIX + command

        # Add the disabled command record
        self.disabled_commands[command] = DisabledCommand(
            command_function=command_function,
            help_function=getattr(self, help_func_name, None),
            completer_function=getattr(self, completer_func_name, None),
        )

        # Overwrite the command and help functions to print the message
        new_func = functools.partial(
            self._report_disabled_command_usage, message_to_print=message_to_print.replace(constants.COMMAND_NAME, command)
        )
        setattr(self, cmd_func_name, new_func)
        setattr(self, help_func_name, new_func)

        # Set the completer to a function that returns a blank list
        setattr(self, completer_func_name, lambda *_args, **_kwargs: [])

    def disable_category(self, category: str, message_to_print: str) -> None:
        """Disable an entire category of commands.

        :param category: the category to disable
        :param message_to_print: what to print when anything in this category is run or help is called on it
                                 while disabled. The variable cmd2.COMMAND_NAME can be used as a placeholder for the name
                                 of the command being disabled.
                                 ex: message_to_print = f"{cmd2.COMMAND_NAME} is currently disabled"
        """
        all_commands = self.get_all_commands()

        for cmd_name in all_commands:
            func = self.cmd_func(cmd_name)
            if getattr(func, constants.CMD_ATTR_HELP_CATEGORY, None) == category:
                self.disable_command(cmd_name, message_to_print)

    def _report_disabled_command_usage(self, *_args: Any, message_to_print: str, **_kwargs: Any) -> None:
        """Report when a disabled command has been run or had help called on it.

        :param _args: not used
        :param message_to_print: the message reporting that the command is disabled
        :param _kwargs: not used
        """
        self.perror(message_to_print, style=None)

    def cmdloop(self, intro: RenderableType = '') -> int:
        """Deal with extra features provided by cmd2, this is an outer wrapper around _cmdloop().

        _cmdloop() provides the main loop.  This provides the following extra features provided by cmd2:
        - transcript testing
        - intro banner
        - exit code

        :param intro: if provided this overrides self.intro and serves as the intro banner printed once at start
        :return: exit code
        """
        # cmdloop() expects to be run in the main thread to support extensive use of KeyboardInterrupts throughout the
        # other built-in functions. You are free to override cmdloop, but much of cmd2's features will be limited.
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("cmdloop must be run in the main thread")

        # Register signal handlers
        import signal

        original_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self.sigint_handler)

        if not sys.platform.startswith('win'):
            original_sighup_handler = signal.getsignal(signal.SIGHUP)
            signal.signal(signal.SIGHUP, self.termination_signal_handler)

            original_sigterm_handler = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, self.termination_signal_handler)

        # Always run the preloop first
        for func in self._preloop_hooks:
            func()
        self.preloop()

        # If transcript-based regression testing was requested, then do that instead of the main loop
        if self._transcript_files is not None:
            self._run_transcript_tests([os.path.expanduser(tf) for tf in self._transcript_files])
        else:
            # If an intro was supplied in the method call, allow it to override the default
            if intro:
                self.intro = intro

            # Print the intro, if there is one, right after the preloop
            if self.intro:
                self.poutput(self.intro)

            # And then call _cmdloop() to enter the main loop
            self._cmdloop()

        # Run the postloop() no matter what
        for func in self._postloop_hooks:
            func()
        self.postloop()

        # Restore original signal handlers
        signal.signal(signal.SIGINT, original_sigint_handler)

        if not sys.platform.startswith('win'):
            signal.signal(signal.SIGHUP, original_sighup_handler)
            signal.signal(signal.SIGTERM, original_sigterm_handler)

        return self.exit_code

    ###
    #
    # plugin related functions
    #
    ###
    def _initialize_plugin_system(self) -> None:
        """Initialize the plugin system."""
        self._preloop_hooks: list[Callable[[], None]] = []
        self._postloop_hooks: list[Callable[[], None]] = []
        self._postparsing_hooks: list[Callable[[plugin.PostparsingData], plugin.PostparsingData]] = []
        self._precmd_hooks: list[Callable[[plugin.PrecommandData], plugin.PrecommandData]] = []
        self._postcmd_hooks: list[Callable[[plugin.PostcommandData], plugin.PostcommandData]] = []
        self._cmdfinalization_hooks: list[Callable[[plugin.CommandFinalizationData], plugin.CommandFinalizationData]] = []

    @classmethod
    def _validate_callable_param_count(cls, func: Callable[..., Any], count: int) -> None:
        """Ensure a function has the given number of parameters."""
        signature = inspect.signature(func)
        # validate that the callable has the right number of parameters
        nparam = len(signature.parameters)
        if nparam != count:
            plural = '' if nparam == 1 else 's'
            raise TypeError(f'{func.__name__} has {nparam} positional argument{plural}, expected {count}')

    @classmethod
    def _validate_prepostloop_callable(cls, func: Callable[[], None]) -> None:
        """Check parameter and return types for preloop and postloop hooks."""
        cls._validate_callable_param_count(func, 0)
        # make sure there is no return annotation or the return is specified as None
        _, ret_ann = get_types(func)
        if ret_ann is not None:
            raise TypeError(f"{func.__name__} must have a return type of 'None', got: {ret_ann}")

    def register_preloop_hook(self, func: Callable[[], None]) -> None:
        """Register a function to be called at the beginning of the command loop."""
        self._validate_prepostloop_callable(func)
        self._preloop_hooks.append(func)

    def register_postloop_hook(self, func: Callable[[], None]) -> None:
        """Register a function to be called at the end of the command loop."""
        self._validate_prepostloop_callable(func)
        self._postloop_hooks.append(func)

    @classmethod
    def _validate_postparsing_callable(cls, func: Callable[[plugin.PostparsingData], plugin.PostparsingData]) -> None:
        """Check parameter and return types for postparsing hooks."""
        cls._validate_callable_param_count(cast(Callable[..., Any], func), 1)
        type_hints, ret_ann = get_types(func)
        if not type_hints:
            raise TypeError(f"{func.__name__} parameter is missing a type hint, expected: 'cmd2.plugin.PostparsingData'")
        par_ann = next(iter(type_hints.values()))
        if par_ann != plugin.PostparsingData:
            raise TypeError(f"{func.__name__} must have one parameter declared with type 'cmd2.plugin.PostparsingData'")
        if ret_ann != plugin.PostparsingData:
            raise TypeError(f"{func.__name__} must declare return a return type of 'cmd2.plugin.PostparsingData'")

    def register_postparsing_hook(self, func: Callable[[plugin.PostparsingData], plugin.PostparsingData]) -> None:
        """Register a function to be called after parsing user input but before running the command."""
        self._validate_postparsing_callable(func)
        self._postparsing_hooks.append(func)

    CommandDataType = TypeVar('CommandDataType')

    @classmethod
    def _validate_prepostcmd_hook(
        cls, func: Callable[[CommandDataType], CommandDataType], data_type: type[CommandDataType]
    ) -> None:
        """Check parameter and return types for pre and post command hooks."""
        # validate that the callable has the right number of parameters
        cls._validate_callable_param_count(cast(Callable[..., Any], func), 1)

        type_hints, ret_ann = get_types(func)
        if not type_hints:
            raise TypeError(f"{func.__name__} parameter is missing a type hint, expected: {data_type}")
        _param_name, par_ann = next(iter(type_hints.items()))
        # validate the parameter has the right annotation
        if par_ann != data_type:
            raise TypeError(f'argument 1 of {func.__name__} has incompatible type {par_ann}, expected {data_type}')
        # validate the return value has the right annotation
        if ret_ann is None:
            raise TypeError(f'{func.__name__} does not have a declared return type, expected {data_type}')
        if ret_ann != data_type:
            raise TypeError(f'{func.__name__} has incompatible return type {ret_ann}, expected {data_type}')

    def register_precmd_hook(self, func: Callable[[plugin.PrecommandData], plugin.PrecommandData]) -> None:
        """Register a hook to be called before the command function."""
        self._validate_prepostcmd_hook(func, plugin.PrecommandData)
        self._precmd_hooks.append(func)

    def register_postcmd_hook(self, func: Callable[[plugin.PostcommandData], plugin.PostcommandData]) -> None:
        """Register a hook to be called after the command function."""
        self._validate_prepostcmd_hook(func, plugin.PostcommandData)
        self._postcmd_hooks.append(func)

    @classmethod
    def _validate_cmdfinalization_callable(
        cls, func: Callable[[plugin.CommandFinalizationData], plugin.CommandFinalizationData]
    ) -> None:
        """Check parameter and return types for command finalization hooks."""
        cls._validate_callable_param_count(func, 1)
        type_hints, ret_ann = get_types(func)
        if not type_hints:
            raise TypeError(f"{func.__name__} parameter is missing a type hint, expected: {plugin.CommandFinalizationData}")
        _, par_ann = next(iter(type_hints.items()))
        if par_ann != plugin.CommandFinalizationData:
            raise TypeError(
                f"{func.__name__} must have one parameter declared with type {plugin.CommandFinalizationData}, got: {par_ann}"
            )
        if ret_ann != plugin.CommandFinalizationData:
            raise TypeError(f"{func.__name__} must declare return a return type of {plugin.CommandFinalizationData}")

    def register_cmdfinalization_hook(
        self, func: Callable[[plugin.CommandFinalizationData], plugin.CommandFinalizationData]
    ) -> None:
        """Register a hook to be called after a command is completed, whether it completes successfully or not."""
        self._validate_cmdfinalization_callable(func)
        self._cmdfinalization_hooks.append(func)

    def _resolve_func_self(
        self,
        cmd_support_func: Callable[..., Any],
        cmd_self: Union[CommandSet, 'Cmd', None],
    ) -> object | None:
        """Attempt to resolve a candidate instance to pass as 'self'.

        Used for an unbound class method that was used when defining command's argparse object.

        Since we restrict registration to only a single CommandSet
        instance of each type, using type is a reasonably safe way to resolve the correct object instance.

        :param cmd_support_func: command support function. This could be a completer or namespace provider
        :param cmd_self: The `self` associated with the command or subcommand
        """
        # figure out what class the command support function was defined in
        func_class: type[Any] | None = get_defining_class(cmd_support_func)

        # Was there a defining class identified? If so, is it a sub-class of CommandSet?
        if func_class is not None and issubclass(func_class, CommandSet):
            # Since the support function is provided as an unbound function, we need to locate the instance
            # of the CommandSet to pass in as `self` to emulate a bound method call.
            # We're searching for candidates that match the support function's defining class type in this order:
            #   1. Is the command's CommandSet a sub-class of the support function's class?
            #   2. Do any of the registered CommandSets in the Cmd2 application exactly match the type?
            #   3. Is there a registered CommandSet that is is the only matching subclass?

            func_self: CommandSet | Cmd | None

            # check if the command's CommandSet is a sub-class of the support function's defining class
            if isinstance(cmd_self, func_class):
                # Case 1: Command's CommandSet is a sub-class of the support function's CommandSet
                func_self = cmd_self
            else:
                # Search all registered CommandSets
                func_self = None
                candidate_sets: list[CommandSet] = []
                for installed_cmd_set in self._installed_command_sets:
                    if type(installed_cmd_set) == func_class:  # noqa: E721
                        # Case 2: CommandSet is an exact type match for the function's CommandSet
                        func_self = installed_cmd_set
                        break

                    # Add candidate for Case 3:
                    if isinstance(installed_cmd_set, func_class):
                        candidate_sets.append(installed_cmd_set)
                if func_self is None and len(candidate_sets) == 1:
                    # Case 3: There exists exactly 1 CommandSet that is a sub-class match of the function's CommandSet
                    func_self = candidate_sets[0]
            return func_self
        return self
