"""Statement parsing classes for cmd2."""

import re
import shlex
import sys
from collections.abc import (
    Iterable,
    Mapping,
    Sequence,
)
from dataclasses import (
    asdict,
    dataclass,
    field,
)
from typing import (
    Any,
    ClassVar,
)

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from . import (
    constants,
    utils,
)
from . import string_utils as su
from .exceptions import Cmd2ShlexError


def shlex_split(str_to_split: str) -> list[str]:
    """Split the string *str_to_split* using shell-like syntax.

    A wrapper around shlex.split() that uses cmd2's preferred arguments.

    This allows other classes to easily call split() the same way StatementParser does.

    :param str_to_split: the string being split
    :return: A list of tokens
    """
    return shlex.split(str_to_split, comments=False, posix=False)


@dataclass(frozen=True, slots=True)
class MacroArg:
    """Information used to resolve or unescape macro arguments."""

    # The starting index of this argument in the macro value
    start_index: int

    # The number string that appears between the braces
    # This is a string instead of an int because we support unicode digits and must be able
    # to reproduce this string later
    number_str: str

    # Tells if this argument is escaped and therefore needs to be unescaped
    is_escaped: bool

    # Matches normal args like {5}
    # Uses lookarounds to ensure exactly one brace.
    # (?<!{){ -> Match '{' not preceded by '{'
    # \d+     -> Match digits
    # }(?!})  -> Match '}' not followed by '}'
    macro_normal_arg_pattern: ClassVar[re.Pattern[str]] = re.compile(r'(?<!{){\d+}|{\d+}(?!})')

    # Matches escaped args like {{5}}
    # Specifically looking for exactly two braces on each side.
    macro_escaped_arg_pattern: ClassVar[re.Pattern[str]] = re.compile(r'{{2}\d+}{2}')

    # Finds a string of digits
    digit_pattern: ClassVar[re.Pattern[str]] = re.compile(r'\d+')


@dataclass(frozen=True, slots=True)
class Macro:
    """Defines a cmd2 macro."""

    # Name of the macro
    name: str

    # The string the macro resolves to
    value: str

    # The minimum number of args the user has to pass to this macro
    minimum_arg_count: int

    # Metadata for argument placeholders and escaped sequences found in 'value'.
    # This is stored internally as a tuple.
    args: Sequence[MacroArg] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Finalize the object after initialization."""
        # Convert args to an immutable tuple.
        if not isinstance(self.args, tuple):
            object.__setattr__(self, 'args', tuple(self.args))


@dataclass(frozen=True)
class Statement(str):  # noqa: SLOT000
    """String subclass with additional attributes to store the results of parsing.

    Instances of this class should not be created by anything other than the
    [StatementParser.parse][cmd2.parsing.StatementParser.parse] method, nor should any of the
    attributes be modified once the object is created.

    The string portion of the class contains the arguments, but not the
    command, nor the output redirection clauses.

    Tips:

    1. `argparse <https://docs.python.org/3/library/argparse.html>`_ is your
       friend for anything complex. ``cmd2`` has the decorator
       ([cmd2.decorators.with_argparser][]) which you can
       use to make your command method receive a namespace of parsed arguments,
       whether positional or denoted with switches.

    2. For commands with simple positional arguments, use
       [args][cmd2.parsing.Statement.args] or [arg_list][cmd2.parsing.Statement.arg_list]

    3. If you don't want to have to worry about quoted arguments, see
       [argv][cmd2.parsing.Statement.argv] for a trick which strips quotes off for you.
    """

    # A space-delimited string containing the arguments to the command (quotes preserved).
    # This does not include any output redirection clauses.
    # Note: If a terminator is present, characters that would otherwise be
    # redirectors (like '>') are treated as literal arguments if they appear
    # before the terminator.
    args: str = ''

    # The original, unmodified input string
    raw: str = ''

    # The resolved command name (after shortcut/alias expansion)
    command: str = ''

    # Whether the command is recognized as a multiline-capable command
    multiline_command: bool = False

    # The character which terminates the command/arguments portion of the input.
    # While primarily used to signal the end of multiline commands, its presence
    # defines the boundary between arguments and any subsequent redirection.
    terminator: str = ''

    # Characters appearing after the terminator but before output redirection
    suffix: str = ''

    # The operator used to redirect output (e.g. '>', '>>', or '|').
    redirector: str = ''

    # The destination for the redirected output (a file path or a shell command).
    # Quotes are preserved.
    redirect_to: str = ''

    def __new__(cls, value: object, *_pos_args: Any, **_kw_args: Any) -> Self:
        """Create a new instance of Statement.

        We must override __new__ because we are subclassing `str` which is
        immutable and takes a different number of arguments as Statement.

        NOTE:  @dataclass takes care of initializing other members in the __init__ it
        generates.
        """
        return super().__new__(cls, value)

    @property
    def command_and_args(self) -> str:
        """Combine command and args with a space separating them.

        Quoted arguments remain quoted. Output redirection and piping are
        excluded, as are any command terminators.
        """
        if self.command and self.args:
            return f"{self.command} {self.args}"
        return self.command

    @property
    def post_command(self) -> str:
        """A string containing any ending terminator, suffix, and redirection chars."""
        parts = []
        if self.terminator:
            parts.append(self.terminator)

        if self.suffix:
            parts.append(self.suffix)

        if self.redirector:
            parts.append(self.redirector)
            if self.redirect_to:
                parts.append(self.redirect_to)

        return ' '.join(parts)

    @property
    def expanded_command_line(self) -> str:
        """Concatenate [cmd2.parsing.Statement.command_and_args]() and [cmd2.parsing.Statement.post_command]()."""
        # Use a space if there is a post_command that doesn't start with a terminator
        sep = ' ' if self.post_command and not self.terminator else ''
        return f"{self.command_and_args}{sep}{self.post_command}"

    @property
    def argv(self) -> list[str]:
        """A list of arguments a-la ``sys.argv``.

        The first element of the list is the command after shortcut and macro
        expansion. Subsequent elements of the list contain any additional
        arguments, with quotes removed, just like bash would. This is very
        useful if you are going to use ``argparse.parse_args()``.

        If you want to strip quotes from the input, you can use ``argv[1:]``.
        """
        if self.command:
            return [su.strip_quotes(self.command)] + [su.strip_quotes(arg) for arg in self.arg_list]

        return []

    @property
    def arg_list(self) -> list[str]:
        """Return the arguments in a list (quotes preserved)."""
        return shlex_split(self.args)

    def to_dict(self) -> dict[str, Any]:
        """Convert this Statement into a dictionary for use in persistent JSON history files."""
        return asdict(self)

    @classmethod
    def from_dict(cls, source_dict: dict[str, Any]) -> Self:
        """Restore a Statement from a dictionary.

        :param source_dict: source data dictionary (generated using to_dict())
        :return: Statement object
        """
        # value needs to be passed as a positional argument. It corresponds to the args field.
        try:
            value = source_dict["args"]
        except KeyError:
            raise KeyError("Statement dictionary is missing 'args' field") from None

        # Filter out 'args' so it isn't passed twice
        kwargs = {k: v for k, v in source_dict.items() if k != 'args'}
        return cls(value, **kwargs)


@dataclass(frozen=True, slots=True)
class PartialStatement:
    """A partially parsed command line.

    This separates the command from its arguments without validating
    terminators, redirection, or quoted string completion.

    Note:
        Unlike [cmd2.parsing.Statement][], this is a simple data object
        and does not inherit from [str][].

    """

    # The resolved command name (after shortcut/alias expansion)
    command: str

    # The remaining string after the command. May contain unclosed quotes
    # or unprocessed redirection/terminator characters.
    args: str

    # The original, unmodified input string
    raw: str

    # Whether the command is recognized as a multiline-capable command
    multiline_command: bool

    @property
    def command_and_args(self) -> str:
        """Combine command and args with a space between them."""
        if self.command and self.args:
            return f"{self.command} {self.args}"
        return self.command


class StatementParser:
    """Parse user input as a string into discrete command components."""

    def __init__(
        self,
        terminators: Iterable[str] | None = None,
        multiline_commands: Iterable[str] | None = None,
        aliases: Mapping[str, str] | None = None,
        shortcuts: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize an instance of StatementParser.

        The following will get converted to an immutable tuple before storing internally:
        terminators, multiline commands, and shortcuts.

        :param terminators: iterable containing strings which should terminate commands
        :param multiline_commands: iterable containing the names of commands that accept multiline input
        :param aliases: dictionary containing aliases
        :param shortcuts: dictionary containing shortcuts
        """
        self.terminators: tuple[str, ...]
        if terminators is None:
            self.terminators = (constants.MULTILINE_TERMINATOR,)
        else:
            self.terminators = tuple(terminators)
        self.multiline_commands: tuple[str, ...] = tuple(multiline_commands) if multiline_commands is not None else ()
        self.aliases: dict[str, str] = dict(aliases) if aliases is not None else {}

        if shortcuts is None:
            shortcuts = constants.DEFAULT_SHORTCUTS

        # Sort the shortcuts in descending order by name length because the longest match
        # should take precedence. (e.g., @@file should match '@@' and not '@'.
        self.shortcuts = tuple(sorted(shortcuts.items(), key=lambda x: len(x[0]), reverse=True))

        # commands have to be a word, so make a regular expression
        # that matches the first word in the line. This regex has three
        # parts:
        #     - the '\A\s*' matches the beginning of the string (even
        #       if contains multiple lines) and gobbles up any leading
        #       whitespace
        #     - the first parenthesis enclosed group matches one
        #       or more non-whitespace characters with a non-greedy match
        #       (that's what the '+?' part does). The non-greedy match
        #       ensures that this first group doesn't include anything
        #       matched by the second group
        #     - the second parenthesis group must be dynamically created
        #       because it needs to match either whitespace, something in
        #       REDIRECTION_CHARS, one of the terminators, or the end of
        #       the string (\Z matches the end of the string even if it
        #       contains multiple lines)
        #
        invalid_command_chars = []
        invalid_command_chars.extend(constants.QUOTES)
        invalid_command_chars.extend(constants.REDIRECTION_CHARS)
        invalid_command_chars.extend(self.terminators)
        # escape each item so it will for sure get treated as a literal
        second_group_items = [re.escape(x) for x in invalid_command_chars]
        # add the whitespace and end of string, not escaped because they
        # are not literals
        second_group_items.extend([r'\s', r'\Z'])
        # join them up with a pipe
        second_group = '|'.join(second_group_items)
        # build the regular expression
        expr = rf'\A\s*(\S*?)({second_group})'
        self._command_pattern = re.compile(expr)

    def is_valid_command(self, word: str, *, is_subcommand: bool = False) -> tuple[bool, str]:
        """Determine whether a word is a valid name for a command.

        Commands cannot include redirection characters, whitespace,
        or termination characters. They also cannot start with a
        shortcut.

        :param word: the word to check as a command
        :param is_subcommand: Flag whether this command name is a subcommand name
        :return: a tuple of a boolean and an error string

        If word is not a valid command, return ``False`` and an error string
        suitable for inclusion in an error message of your choice::

            checkit = '>'
            valid, errmsg = statement_parser.is_valid_command(checkit)
            if not valid:
                errmsg = f"alias: {errmsg}"
        """
        valid = False

        if not isinstance(word, str):
            return False, f'must be a string. Received {type(word)!s} instead'  # type: ignore[unreachable]

        if not word:
            return False, 'cannot be an empty string'

        if word.startswith(constants.COMMENT_CHAR):
            return False, 'cannot start with the comment character'

        if not is_subcommand:
            for shortcut, _ in self.shortcuts:
                if word.startswith(shortcut):
                    # Build an error string with all shortcuts listed
                    errmsg = 'cannot start with a shortcut: '
                    errmsg += ', '.join(shortcut for (shortcut, _) in self.shortcuts)
                    return False, errmsg

        errmsg = 'cannot contain: whitespace, quotes, '
        errchars = []
        errchars.extend(constants.REDIRECTION_CHARS)
        errchars.extend(self.terminators)
        errmsg += ', '.join([shlex.quote(x) for x in errchars])

        match = self._command_pattern.search(word)
        if match and word == match.group(1):
            valid = True
            errmsg = ''
        return valid, errmsg

    def tokenize(self, line: str) -> list[str]:
        """Lex a string into a list of tokens. Shortcuts and aliases are expanded and comments are removed.

        :param line: the command line being lexed
        :return: A list of tokens
        :raises Cmd2ShlexError: if a shlex error occurs (e.g. No closing quotation)
        """
        # expand shortcuts and aliases
        line = self._expand(line)

        # check if this line is a comment
        if line.lstrip().startswith(constants.COMMENT_CHAR):
            return []

        # split on whitespace
        try:
            tokens = shlex_split(line)
        except ValueError as ex:
            raise Cmd2ShlexError(ex) from None

        # custom lexing
        return self.split_on_punctuation(tokens)

    def parse(self, line: str) -> Statement:
        """Tokenize the input and parse it into a [cmd2.parsing.Statement][] object.

        Stripping comments, expanding aliases and shortcuts, and extracting output redirection directives.

        :param line: the command line being parsed
        :return: a new [cmd2.parsing.Statement][] object
        :raises Cmd2ShlexError: if a shlex error occurs (e.g. No closing quotation)
        """
        # handle the special case/hardcoded terminator of a blank line
        # we have to do this before we tokenize because tokenizing
        # destroys all unquoted whitespace in the input
        terminator = ''
        if line[-1:] == constants.LINE_FEED:
            terminator = constants.LINE_FEED

        command = ''
        args = ''

        # lex the input into a list of tokens
        tokens = self.tokenize(line)

        # of the valid terminators, find the first one to occur in the input
        terminator_pos = len(tokens) + 1
        for pos, cur_token in enumerate(tokens):
            for test_terminator in self.terminators:
                if cur_token.startswith(test_terminator):
                    terminator_pos = pos
                    terminator = test_terminator
                    # break the inner loop, and we want to break the
                    # outer loop too
                    break
            else:
                # this else clause is only run if the inner loop
                # didn't execute a break. If it didn't, then
                # continue to the next iteration of the outer loop
                continue
            # inner loop was broken, break the outer
            break

        if terminator:
            if terminator == constants.LINE_FEED:
                terminator_pos = len(tokens) + 1

            # everything before the first terminator is the command and the args
            (command, args) = self._command_and_args(tokens[:terminator_pos])

            # we will set the suffix later
            # remove all the tokens before and including the terminator
            tokens = tokens[terminator_pos + 1 :]
        else:
            (testcommand, testargs) = self._command_and_args(tokens)
            if testcommand in self.multiline_commands:
                # no terminator on this line but we have a multiline command
                # everything else on the line is part of the args
                # because redirectors can only be after a terminator
                command = testcommand
                args = testargs
                tokens = []

        redirector = ''
        redirect_to = ''

        # Find which redirector character appears first in the command
        try:
            pipe_index = tokens.index(constants.REDIRECTION_PIPE)
        except ValueError:
            pipe_index = len(tokens)

        try:
            overwrite_index = tokens.index(constants.REDIRECTION_OVERWRITE)
        except ValueError:
            overwrite_index = len(tokens)

        try:
            append_index = tokens.index(constants.REDIRECTION_APPEND)
        except ValueError:
            append_index = len(tokens)

        # Check if output should be piped to a shell command
        if pipe_index < overwrite_index and pipe_index < append_index:
            redirector = constants.REDIRECTION_PIPE

            # Get the tokens for the pipe command and expand ~ where needed
            pipe_to_tokens = tokens[pipe_index + 1 :]
            utils.expand_user_in_tokens(pipe_to_tokens)

            # Build the pipe command line string
            redirect_to = ' '.join(pipe_to_tokens)

            # remove all the tokens after the pipe
            tokens = tokens[:pipe_index]

        # Check for output redirect/append
        elif overwrite_index != append_index:
            if overwrite_index < append_index:
                redirector = constants.REDIRECTION_OVERWRITE
                redirector_index = overwrite_index
            else:
                redirector = constants.REDIRECTION_APPEND
                redirector_index = append_index

            redirect_to_index = redirector_index + 1

            # Check if we are redirecting to a file
            if len(tokens) > redirect_to_index:
                unquoted_path = su.strip_quotes(tokens[redirect_to_index])
                if unquoted_path:
                    redirect_to = utils.expand_user(tokens[redirect_to_index])

            # remove all the tokens after the output redirect
            tokens = tokens[:redirector_index]

        if terminator:
            # whatever is left is the suffix
            suffix = ' '.join(tokens)
        else:
            # no terminator, so whatever is left is the command and the args
            suffix = ''
            if not command:
                # command could already have been set, if so, don't set it again
                (command, args) = self._command_and_args(tokens)

        # build the statement
        return Statement(
            args,
            raw=line,
            command=command,
            multiline_command=command in self.multiline_commands,
            terminator=terminator,
            suffix=suffix,
            redirector=redirector,
            redirect_to=redirect_to,
        )

    def parse_command_only(self, rawinput: str) -> PartialStatement:
        """Identify the command and arguments from raw input.

        Partially parse input into a [cmd2.PartialStatement][] object.

        The command is identified, and shortcuts and aliases are expanded.
        Multiline commands are identified, but terminators and output
        redirection are not parsed.

        This method is optimized for completion code and gracefully handles
        unclosed quotes without raising exceptions.

        [cmd2.parsing.PartialStatement.args][] will include all output redirection
        clauses and command terminators.

        Note:
            Unlike [cmd2.parsing.StatementParser.parse][], this method
            preserves internal whitespace within the args. It ensures
            args has no leading whitespace, and it strips trailing
            whitespace only if all quotes are closed.

        :param rawinput: the command line as entered by the user
        :return: a [cmd2.PartialStatement][] object representing the split input

        """
        # Expand shortcuts and aliases
        line = self._expand(rawinput)

        command = ''
        args = ''
        match = self._command_pattern.search(line)

        if match:
            # Extract the resolved command
            command = match.group(1)

            # If the command is empty, the input was either empty or started with
            # something like a redirector ('>') or terminator (';').
            if command:
                # args is everything after the command match
                args = line[match.end(1) :].lstrip()

                try:
                    # Check for closed quotes
                    shlex_split(args)
                except ValueError:
                    # Unclosed quote: preserve trailing whitespace for completion context.
                    pass
                else:
                    # Quotes are closed: strip trailing whitespace
                    args = args.rstrip()

        return PartialStatement(
            command=command,
            args=args,
            raw=rawinput,
            multiline_command=command in self.multiline_commands,
        )

    def get_command_arg_list(
        self, command_name: str, to_parse: Statement | str, preserve_quotes: bool
    ) -> tuple[Statement, list[str]]:
        """Retrieve just the arguments being passed to their ``do_*`` methods as a list.

        Convenience method used by the argument parsing decorators.

        :param command_name: name of the command being run
        :param to_parse: what is being passed to the ``do_*`` method. It can be one of two types:

                             1. An already parsed [cmd2.Statement][]
                             2. An argument string in cases where a ``do_*`` method is
                                explicitly called. Calling ``do_help('alias create')`` would
                                cause ``to_parse`` to be 'alias create'.

                                In this case, the string will be converted to a
                                [cmd2.Statement][] and returned along with
                                the argument list.

        :param preserve_quotes: if ``True``, then quotes will not be stripped from
                                the arguments
        :return: A tuple containing the [cmd2.Statement][] and a list of
                 strings representing the arguments
        """
        # Check if to_parse needs to be converted to a Statement
        if not isinstance(to_parse, Statement):
            to_parse = self.parse(command_name + ' ' + to_parse)

        if preserve_quotes:
            return to_parse, to_parse.arg_list
        return to_parse, to_parse.argv[1:]

    def _expand(self, line: str) -> str:
        """Expand aliases and shortcuts."""
        # Make a copy of aliases so we can keep track of what aliases have been resolved to avoid an infinite loop
        remaining_aliases = list(self.aliases.keys())
        keep_expanding = bool(remaining_aliases)

        while keep_expanding:
            keep_expanding = False

            # apply our regex to line
            match = self._command_pattern.search(line)
            if match:
                # we got a match, extract the command
                command = match.group(1)

                # Check if this command matches an alias that wasn't already processed
                if command in remaining_aliases:
                    # rebuild line with the expanded alias
                    line = self.aliases[command] + match.group(2) + line[match.end(2) :]
                    remaining_aliases.remove(command)
                    keep_expanding = bool(remaining_aliases)

        # expand shortcuts
        for shortcut, expansion in self.shortcuts:
            if line.startswith(shortcut):
                # If the next character after the shortcut isn't a space, then insert one
                shortcut_len = len(shortcut)
                effective_expansion = expansion
                if len(line) == shortcut_len or line[shortcut_len] != ' ':
                    effective_expansion += ' '

                # Expand the shortcut
                line = line.replace(shortcut, effective_expansion, 1)
                break
        return line

    @staticmethod
    def _command_and_args(tokens: list[str]) -> tuple[str, str]:
        """Given a list of tokens, return a tuple of the command and the args as a string."""
        command = ''
        args = ''

        if tokens:
            command = tokens[0]

        if len(tokens) > 1:
            args = ' '.join(tokens[1:])

        return command, args

    def split_on_punctuation(self, tokens: list[str]) -> list[str]:
        """Further splits tokens from a command line using punctuation characters.

        Punctuation characters are treated as word breaks when they are in
        unquoted strings. Each run of punctuation characters is treated as a
        single token.

        :param tokens: the tokens as parsed by shlex
        :return: a new list of tokens, further split using punctuation
        """
        punctuation: list[str] = []
        punctuation.extend(self.terminators)
        punctuation.extend(constants.REDIRECTION_CHARS)

        punctuated_tokens = []

        for cur_initial_token in tokens:
            # Save tokens up to 1 character in length or quoted tokens. No need to parse these.
            if len(cur_initial_token) <= 1 or cur_initial_token[0] in constants.QUOTES:
                punctuated_tokens.append(cur_initial_token)
                continue

            # Iterate over each character in this token
            cur_index = 0
            cur_char = cur_initial_token[cur_index]

            # Keep track of the token we are building
            new_token = ''

            while True:
                if cur_char not in punctuation:
                    # Keep appending to new_token until we hit a punctuation char
                    while cur_char not in punctuation:
                        new_token += cur_char
                        cur_index += 1
                        if cur_index < len(cur_initial_token):
                            cur_char = cur_initial_token[cur_index]
                        else:
                            break

                else:
                    cur_punc = cur_char

                    # Keep appending to new_token until we hit something other than cur_punc
                    while cur_char == cur_punc:
                        new_token += cur_char
                        cur_index += 1
                        if cur_index < len(cur_initial_token):
                            cur_char = cur_initial_token[cur_index]
                        else:
                            break

                # Save the new token
                punctuated_tokens.append(new_token)
                new_token = ''

                # Check if we've viewed all characters
                if cur_index >= len(cur_initial_token):
                    break

        return punctuated_tokens
