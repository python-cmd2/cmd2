"""Module defines the ArgparseCompleter class which provides argparse-based completion to cmd2 apps.

See the header of argparse_custom.py for instructions on how to use these features.
"""

import argparse
import dataclasses
import inspect
from collections import deque
from collections.abc import Sequence
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    cast,
)

from .constants import INFINITY
from .rich_utils import Cmd2GeneralConsole

if TYPE_CHECKING:  # pragma: no cover
    from .cmd2 import Cmd

from rich.box import SIMPLE_HEAD
from rich.table import (
    Column,
    Table,
)

from .argparse_custom import (
    ChoicesCallable,
    generate_range_error,
)
from .command_definition import CommandSet
from .completion import (
    CompletionItem,
    Completions,
    all_display_numeric,
)
from .exceptions import CompletionError
from .styles import Cmd2Style

# If no table header is supplied, then this will be used instead
DEFAULT_TABLE_HEADER: Sequence[str | Column] = ['Description']

# Name of the choice/completer function argument that, if present, will be passed a dictionary of
# command line tokens up through the token being completed mapped to their argparse destination name.
ARG_TOKENS = 'arg_tokens'


def _build_hint(parser: argparse.ArgumentParser, arg_action: argparse.Action) -> str:
    """Build completion hint for a given argument."""
    # Check if hinting is disabled for this argument
    suppress_hint = arg_action.get_suppress_tab_hint()  # type: ignore[attr-defined]
    if suppress_hint or arg_action.help == argparse.SUPPRESS:
        return ''

    # Use the parser's help formatter to display just this action's help text
    formatter = parser._get_formatter()
    formatter.start_section("Hint")
    formatter.add_argument(arg_action)
    formatter.end_section()
    return formatter.format_help()


def _single_prefix_char(token: str, parser: argparse.ArgumentParser) -> bool:
    """Is a token just a single flag prefix character."""
    return len(token) == 1 and token[0] in parser.prefix_chars


def _looks_like_flag(token: str, parser: argparse.ArgumentParser) -> bool:
    """Determine if a token looks like a flag.

    Unless an argument has nargs set to argparse.REMAINDER, then anything that looks like a flag
    can't be consumed as a value for it.

    Based on argparse._parse_optional().
    """
    # Flags have to be at least characters
    if len(token) < 2:
        return False

    # Flags have to start with a prefix character
    if token[0] not in parser.prefix_chars:
        return False

    # If it looks like a negative number, it is not a flag unless there are negative-number-like flags
    if parser._negative_number_matcher.match(token) and not parser._has_negative_number_optionals:
        return False

    # Flags can't have a space
    return ' ' not in token


class _ArgumentState:
    """Keeps state of an argument being parsed."""

    def __init__(self, arg_action: argparse.Action) -> None:
        self.action = arg_action
        self.min: int
        self.max: float | int
        self.count = 0
        self.is_remainder = self.action.nargs == argparse.REMAINDER

        # Check if nargs is a range
        nargs_range: tuple[int, int | float] | None = self.action.get_nargs_range()  # type: ignore[attr-defined]
        if nargs_range is not None:
            self.min = nargs_range[0]
            self.max = nargs_range[1]

        # Otherwise check against argparse types
        elif self.action.nargs is None:
            self.min = 1
            self.max = 1
        elif self.action.nargs == argparse.OPTIONAL:
            self.min = 0
            self.max = 1
        elif self.action.nargs in (argparse.ZERO_OR_MORE, argparse.REMAINDER):
            self.min = 0
            self.max = INFINITY
        elif self.action.nargs == argparse.ONE_OR_MORE:
            self.min = 1
            self.max = INFINITY
        else:
            self.min = cast(int, self.action.nargs)
            self.max = cast(int, self.action.nargs)


class _UnfinishedFlagError(CompletionError):
    def __init__(self, flag_arg_state: _ArgumentState) -> None:
        """CompletionError which occurs when the user has not finished the current flag.

        :param flag_arg_state: information about the unfinished flag action.
        """
        arg = f'{argparse._get_action_name(flag_arg_state.action)}'
        err = f'{generate_range_error(flag_arg_state.min, flag_arg_state.max)}'
        error = f"Error: argument {arg}: {err} ({flag_arg_state.count} entered)"
        super().__init__(error)


class _NoResultsError(CompletionError):
    def __init__(self, parser: argparse.ArgumentParser, arg_action: argparse.Action) -> None:
        """CompletionError which occurs when there are no results.

        If hinting is allowed on this argument, then its hint text will display.

        :param parser: ArgumentParser instance which owns the action being completed
        :param arg_action: action being completed.
        """
        # Set apply_style to False because we don't want hints to look like errors
        super().__init__(_build_hint(parser, arg_action), apply_style=False)


class ArgparseCompleter:
    """Automatic command line completion based on argparse parameters."""

    def __init__(
        self,
        parser: argparse.ArgumentParser,
        cmd2_app: 'Cmd',
        *,
        parent_tokens: dict[str, list[str]] | None = None,
    ) -> None:
        """Create an ArgparseCompleter.

        :param parser: ArgumentParser instance
        :param cmd2_app: reference to the Cmd2 application that owns this ArgparseCompleter
        :param parent_tokens: optional dictionary mapping parent parsers' arg names to their tokens
                              This is only used by ArgparseCompleter when recursing on subcommand parsers
                              Defaults to None
        """
        self._parser = parser
        self._cmd2_app = cmd2_app

        if parent_tokens is None:
            parent_tokens = {}
        self._parent_tokens = parent_tokens

        # All flags in this command
        self._flags: list[str] = []

        # Maps flags to the argparse action object
        self._flag_to_action: dict[str, argparse.Action] = {}

        # Actions for positional arguments (by position index)
        self._positional_actions: list[argparse.Action] = []

        # This will be set if self._parser has subcommands
        self._subcommand_action: argparse._SubParsersAction[argparse.ArgumentParser] | None = None

        # Start digging through the argparse structures.
        # _actions is the top level container of parameter definitions
        for action in self._parser._actions:
            # if the parameter is flag based, it will have option_strings
            if action.option_strings:
                # record each option flag
                for option in action.option_strings:
                    self._flags.append(option)
                    self._flag_to_action[option] = action

            # Otherwise this is a positional parameter
            else:
                self._positional_actions.append(action)
                # Check if this action defines subcommands
                if isinstance(action, argparse._SubParsersAction):
                    self._subcommand_action = action

    def complete(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
        tokens: list[str],
        *,
        cmd_set: CommandSet | None = None,
    ) -> Completions:
        """Complete text using argparse metadata.

        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param tokens: list of argument tokens being passed to the parser
        :param cmd_set: if completing a command, the CommandSet the command's function belongs to, if applicable.
                        Defaults to None.
        :return: a Completions object
        :raises CompletionError: for various types of completion errors
        """
        if not tokens:
            return Completions()

        # Positionals args that are left to parse
        remaining_positionals = deque(self._positional_actions)

        # This gets set to True when flags will no longer be processed as argparse flags
        # That can happen when -- is used or an argument with nargs=argparse.REMAINDER is used
        skip_remaining_flags = False

        # _ArgumentState of the current positional
        pos_arg_state: _ArgumentState | None = None

        # _ArgumentState of the current flag
        flag_arg_state: _ArgumentState | None = None

        # Non-reusable flags that we've parsed
        used_flags: set[str] = set()

        # Keeps track of arguments we've seen and any tokens they consumed
        consumed_arg_values: dict[str, list[str]] = {}  # dict(arg_name -> list[tokens])

        # Completed mutually exclusive groups
        completed_mutex_groups: dict[argparse._MutuallyExclusiveGroup, argparse.Action] = {}

        def consume_argument(arg_state: _ArgumentState, arg_token: str) -> None:
            """Consume token as an argument."""
            arg_state.count += 1
            consumed_arg_values.setdefault(arg_state.action.dest, [])
            consumed_arg_values[arg_state.action.dest].append(arg_token)

        #############################################################################################
        # Parse all but the last token
        #############################################################################################
        for token_index, token in enumerate(tokens[:-1]):
            # If we're in a positional REMAINDER arg, force all future tokens to go to that
            if pos_arg_state is not None and pos_arg_state.is_remainder:
                consume_argument(pos_arg_state, token)
                continue

            # If we're in a flag REMAINDER arg, force all future tokens to go to that until a double dash is hit
            if flag_arg_state is not None and flag_arg_state.is_remainder:
                if token == '--':  # noqa: S105
                    flag_arg_state = None
                else:
                    consume_argument(flag_arg_state, token)
                continue

            # Handle '--' which tells argparse all remaining arguments are non-flags
            if token == '--' and not skip_remaining_flags:  # noqa: S105
                # Check if there is an unfinished flag
                if (
                    flag_arg_state is not None
                    and isinstance(flag_arg_state.min, int)
                    and flag_arg_state.count < flag_arg_state.min
                ):
                    raise _UnfinishedFlagError(flag_arg_state)

                # Otherwise end the current flag
                flag_arg_state = None
                skip_remaining_flags = True
                continue

            # Check if token is a flag
            if _looks_like_flag(token, self._parser) and not skip_remaining_flags:
                # Check if there is an unfinished flag
                if (
                    flag_arg_state is not None
                    and isinstance(flag_arg_state.min, int)
                    and flag_arg_state.count < flag_arg_state.min
                ):
                    raise _UnfinishedFlagError(flag_arg_state)

                # Reset flag arg state but not positional tracking because flags can be
                # interspersed anywhere between positionals
                flag_arg_state = None
                action = None

                # Does the token match a known flag?
                if token in self._flag_to_action:
                    action = self._flag_to_action[token]
                elif self._parser.allow_abbrev:
                    candidates_flags = [flag for flag in self._flag_to_action if flag.startswith(token)]
                    if len(candidates_flags) == 1:
                        action = self._flag_to_action[candidates_flags[0]]

                if action is not None:
                    self._update_mutex_groups(action, completed_mutex_groups, used_flags, remaining_positionals)
                    if isinstance(
                        action,
                        (
                            argparse._AppendAction,
                            argparse._AppendConstAction,
                            argparse._CountAction,
                            argparse._ExtendAction,
                        ),
                    ):
                        # Flags with actions set to append, append_const, count, and extend can be reused.
                        # Therefore don't erase any tokens already consumed for this flag.
                        consumed_arg_values.setdefault(action.dest, [])
                    else:
                        # This flag is not reusable, so mark that we've seen it
                        used_flags.update(action.option_strings)

                        # It's possible we already have consumed values for this flag if it was used
                        # earlier in the command line. Reset them now for this use of it.
                        consumed_arg_values[action.dest] = []

                    new_arg_state = _ArgumentState(action)

                    # Keep track of this flag if it can receive arguments
                    if new_arg_state.max > 0:
                        flag_arg_state = new_arg_state
                        skip_remaining_flags = flag_arg_state.is_remainder

            # Check if token is a flag's argument
            elif flag_arg_state is not None:
                consume_argument(flag_arg_state, token)

                # Check if we have finished with this flag
                if flag_arg_state.count >= flag_arg_state.max:
                    flag_arg_state = None

            # Otherwise treat token as a positional argument
            else:
                # If we aren't current tracking a positional, then get the next positional arg to handle this token
                if pos_arg_state is None and remaining_positionals:
                    action = remaining_positionals.popleft()

                    # Are we at a subcommand? If so, forward to the matching completer
                    if action == self._subcommand_action:
                        if token in self._subcommand_action.choices:
                            # Merge self._parent_tokens and consumed_arg_values
                            parent_tokens = {**self._parent_tokens, **consumed_arg_values}

                            # Include the subcommand name if its destination was set
                            if action.dest != argparse.SUPPRESS:
                                parent_tokens[action.dest] = [token]

                            parser = self._subcommand_action.choices[token]
                            completer_type = self._cmd2_app._determine_ap_completer_type(parser)
                            completer = completer_type(parser, self._cmd2_app, parent_tokens=parent_tokens)
                            return completer.complete(text, line, begidx, endidx, tokens[token_index + 1 :], cmd_set=cmd_set)

                        # Invalid subcommand entered, so no way to complete remaining tokens
                        return Completions()

                    # Otherwise keep track of the argument
                    pos_arg_state = _ArgumentState(action)

                # Check if we have a positional to consume this token
                if pos_arg_state is not None:
                    self._update_mutex_groups(pos_arg_state.action, completed_mutex_groups, used_flags, remaining_positionals)
                    consume_argument(pos_arg_state, token)

                    # No more flags are allowed if this is a REMAINDER argument
                    if pos_arg_state.is_remainder:
                        skip_remaining_flags = True

                    # Check if we have finished with this positional
                    elif pos_arg_state.count >= pos_arg_state.max:
                        pos_arg_state = None

                        # Check if the next positional has nargs set to argparse.REMAINDER.
                        # At this point argparse allows no more flags to be processed.
                        if remaining_positionals and remaining_positionals[0].nargs == argparse.REMAINDER:
                            skip_remaining_flags = True

        #############################################################################################
        # We have parsed all but the last token and have enough information to complete it
        #############################################################################################
        return self._handle_last_token(
            text,
            line,
            begidx,
            endidx,
            flag_arg_state,
            pos_arg_state,
            remaining_positionals,
            consumed_arg_values,
            used_flags,
            skip_remaining_flags,
            cmd_set,
        )

    def _update_mutex_groups(
        self,
        arg_action: argparse.Action,
        completed_mutex_groups: dict[argparse._MutuallyExclusiveGroup, argparse.Action],
        used_flags: set[str],
        remaining_positionals: deque[argparse.Action],
    ) -> None:
        """Manage mutually exclusive group constraints and argument pruning for a given action.

        If an action belongs to a mutually exclusive group, this method ensures no other member
        has been used and updates the parser state to "consume" all remaining conflicting arguments.

        :raises CompletionError: if another member of the same mutually exclusive group
                                 has already been used.
        """
        # Check if this action is in a mutually exclusive group
        for group in self._parser._mutually_exclusive_groups:
            if arg_action in group._group_actions:
                # Check if the group this action belongs to has already been completed
                if group in completed_mutex_groups:
                    # If this is the action that completed the group, then there is no error
                    # since it's allowed to appear on the command line more than once.
                    completer_action = completed_mutex_groups[group]
                    if arg_action == completer_action:
                        return

                    arg_str = f'{argparse._get_action_name(arg_action)}'
                    completer_str = f'{argparse._get_action_name(completer_action)}'
                    error = f"Error: argument {arg_str}: not allowed with argument {completer_str}"
                    raise CompletionError(error)

                # Mark that this action completed the group
                completed_mutex_groups[group] = arg_action

                # Don't complete any of the other args in the group
                for group_action in group._group_actions:
                    if group_action == arg_action:
                        continue
                    if group_action in self._flag_to_action.values():
                        used_flags.update(group_action.option_strings)
                    elif group_action in remaining_positionals:
                        remaining_positionals.remove(group_action)

                # Arg can only be in one group, so we are done
                break

    def _handle_last_token(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
        flag_arg_state: _ArgumentState | None,
        pos_arg_state: _ArgumentState | None,
        remaining_positionals: deque[argparse.Action],
        consumed_arg_values: dict[str, list[str]],
        used_flags: set[str],
        skip_remaining_flags: bool,
        cmd_set: CommandSet | None,
    ) -> Completions:
        """Perform final completion step handling positionals and flags."""
        # Check if we are completing a flag name. This check ignores strings with a length of one, like '-'.
        # This is because that could be the start of a negative number which may be a valid completion for
        # the current argument. We will handle the completion of flags that start with only one prefix
        # character (-f) at the end.
        if _looks_like_flag(text, self._parser) and not skip_remaining_flags:
            if (
                flag_arg_state is not None
                and isinstance(flag_arg_state.min, int)
                and flag_arg_state.count < flag_arg_state.min
            ):
                raise _UnfinishedFlagError(flag_arg_state)
            return self._complete_flags(text, line, begidx, endidx, used_flags)

        # Check if we are completing a flag's argument
        if flag_arg_state is not None:
            completions = self._complete_arg(text, line, begidx, endidx, flag_arg_state, consumed_arg_values, cmd_set=cmd_set)

            # If we have results, then return them
            if completions:
                if not completions.completion_hint:
                    # Add a hint even though there are results in case Cmd.always_show_hint is True.
                    completions = dataclasses.replace(
                        completions,
                        completion_hint=_build_hint(self._parser, flag_arg_state.action),
                    )

                return completions

            # Otherwise, print a hint if the flag isn't finished or text isn't possibly the start of a flag
            if (
                (isinstance(flag_arg_state.min, int) and flag_arg_state.count < flag_arg_state.min)
                or not _single_prefix_char(text, self._parser)
                or skip_remaining_flags
            ):
                raise _NoResultsError(self._parser, flag_arg_state.action)

        # Otherwise check if we have a positional to complete
        elif pos_arg_state is not None or remaining_positionals:
            # If we aren't current tracking a positional, then get the next positional arg to handle this token
            if pos_arg_state is None:
                action = remaining_positionals.popleft()
                pos_arg_state = _ArgumentState(action)

            completions = self._complete_arg(text, line, begidx, endidx, pos_arg_state, consumed_arg_values, cmd_set=cmd_set)

            # If we have results, then return them
            if completions:
                if not completions.completion_hint:
                    # Add a hint even though there are results in case Cmd.always_show_hint is True.
                    completions = dataclasses.replace(
                        completions,
                        completion_hint=_build_hint(self._parser, pos_arg_state.action),
                    )
                return completions

            # Otherwise, print a hint if text isn't possibly the start of a flag
            if not _single_prefix_char(text, self._parser) or skip_remaining_flags:
                raise _NoResultsError(self._parser, pos_arg_state.action)

        # If we aren't skipping remaining flags, then complete flag names if either is True:
        #   1. text is a single flag prefix character that didn't complete against any argument values
        #   2. there are no more positionals to complete
        if not skip_remaining_flags and (_single_prefix_char(text, self._parser) or not remaining_positionals):
            return self._complete_flags(text, line, begidx, endidx, used_flags)

        return Completions()

    def _complete_flags(self, text: str, line: str, begidx: int, endidx: int, used_flags: set[str]) -> Completions:
        """Completion routine for a parsers unused flags."""
        # Build a list of flags that can be completed
        match_against: list[str] = []

        for flag in self._flags:
            # Make sure this flag hasn't already been used
            if flag not in used_flags:
                # Make sure this flag isn't considered hidden
                action = self._flag_to_action[flag]
                if action.help != argparse.SUPPRESS:
                    match_against.append(flag)

        # Build a dictionary linking actions with their matched flag names
        matched_flags = self._cmd2_app.basic_complete(text, line, begidx, endidx, match_against)
        matched_actions: dict[argparse.Action, list[str]] = {}

        for item in matched_flags.items:
            action = self._flag_to_action[item.text]
            matched_actions.setdefault(action, []).append(flag)

        # For completion suggestions, group matched flags by action
        items: list[CompletionItem] = []
        for action, option_strings in matched_actions.items():
            flag_text = ', '.join(option_strings)

            # Mark optional flags with brackets
            if not action.required:
                flag_text = '[' + flag_text + ']'

            # Use the first option string as the completion result for this action
            items.append(
                CompletionItem(
                    option_strings[0],
                    display=flag_text,
                    display_meta=action.help or '',
                )
            )

        return Completions(items)

    def _format_completions(self, arg_state: _ArgumentState, completions: Completions) -> Completions:
        """Format CompletionItems into hint table."""
        # Skip table generation for single results or if the list exceeds the
        # user-defined threshold for table display.
        if len(completions) < 2 or len(completions) > self._cmd2_app.max_completion_table_items:
            return completions

        # Ensure every item provides table metadata to avoid an incomplete table.
        if not all(item.table_row for item in completions):
            return completions

        # If a metavar was defined, use that instead of the dest field
        destination = arg_state.action.metavar or arg_state.action.dest

        # Handle case where metavar was a tuple
        if isinstance(destination, tuple):
            # Figure out what string in the tuple to use based on how many of the arguments have been completed.
            # Use min() to avoid going passed the end of the tuple to support nargs being ZERO_OR_MORE and
            # ONE_OR_MORE. In those cases, argparse limits metavar tuple to 2 elements but we may be completing
            # the 3rd or more argument here.
            destination = destination[min(len(destination) - 1, arg_state.count)]

        # Determine if all display values are numeric so we can right-align them
        all_nums = all_display_numeric(completions.items)

        # Build header row for the hint table
        rich_columns: list[Column] = []
        rich_columns.append(Column(destination.upper(), justify="right" if all_nums else "left", no_wrap=True))
        table_header = cast(Sequence[str | Column] | None, arg_state.action.get_table_header())  # type: ignore[attr-defined]
        if table_header is None:
            table_header = DEFAULT_TABLE_HEADER
        rich_columns.extend(
            column if isinstance(column, Column) else Column(column, overflow="fold") for column in table_header
        )

        # Build the hint table
        hint_table = Table(*rich_columns, box=SIMPLE_HEAD, show_edge=False, border_style=Cmd2Style.TABLE_BORDER)
        for item in completions:
            hint_table.add_row(item.display, *item.table_row)

        # Generate the hint table string
        console = Cmd2GeneralConsole()
        with console.capture() as capture:
            console.print(hint_table, end="", soft_wrap=False)

        return dataclasses.replace(
            completions,
            completion_table=capture.get(),
        )

    def complete_subcommand_help(self, text: str, line: str, begidx: int, endidx: int, tokens: list[str]) -> Completions:
        """Supports cmd2's help command in the completion of subcommand names.

        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param tokens: arguments passed to command/subcommand
        :return: a Completions object
        """
        # If our parser has subcommands, we must examine the tokens and check if they are subcommands
        # If so, we will let the subcommand's parser handle the rest of the tokens via another ArgparseCompleter.
        if self._subcommand_action is not None:
            for token_index, token in enumerate(tokens):
                if token in self._subcommand_action.choices:
                    parser = self._subcommand_action.choices[token]
                    completer_type = self._cmd2_app._determine_ap_completer_type(parser)
                    completer = completer_type(parser, self._cmd2_app)
                    return completer.complete_subcommand_help(text, line, begidx, endidx, tokens[token_index + 1 :])

                if token_index == len(tokens) - 1:
                    # Since this is the last token, we will attempt to complete it
                    return self._cmd2_app.basic_complete(text, line, begidx, endidx, self._subcommand_action.choices)
                break
        return Completions()

    def print_help(self, tokens: list[str], file: IO[str] | None = None) -> None:
        """Supports cmd2's help command in the printing of help text.

        :param tokens: arguments passed to help command
        :param file: optional file object where the argparse should write help text
                     If not supplied, argparse will write to sys.stdout.
        """
        # If our parser has subcommands, we must examine the tokens and check if they are subcommands.
        # If so, we will let the subcommand's parser handle the rest of the tokens via another ArgparseCompleter.
        if tokens and self._subcommand_action is not None:
            parser = self._subcommand_action.choices.get(tokens[0])
            if parser is not None:
                completer_type = self._cmd2_app._determine_ap_completer_type(parser)
                completer = completer_type(parser, self._cmd2_app)
                completer.print_help(tokens[1:])
                return
        self._parser.print_help(file=file)

    def _get_raw_choices(self, arg_state: _ArgumentState) -> list[CompletionItem] | ChoicesCallable | None:
        """Extract choices from action or return the choices_callable."""
        if arg_state.action.choices is not None:
            # If choices are subcommands, then get their help text to populate display_meta.
            if isinstance(arg_state.action, argparse._SubParsersAction):
                parser_help = {}
                for action in arg_state.action._choices_actions:
                    if action.dest in arg_state.action.choices:
                        subparser = arg_state.action.choices[action.dest]
                        parser_help[subparser] = action.help or ''

                return [
                    CompletionItem(name, display_meta=parser_help.get(subparser, ''))
                    for name, subparser in arg_state.action.choices.items()
                ]

            # Standard choices
            return [
                choice if isinstance(choice, CompletionItem) else CompletionItem(choice) for choice in arg_state.action.choices
            ]

        choices_callable: ChoicesCallable | None = arg_state.action.get_choices_callable()  # type: ignore[attr-defined]
        return choices_callable

    def _prepare_callable_params(
        self,
        choices_callable: ChoicesCallable,
        arg_state: _ArgumentState,
        text: str,
        consumed_arg_values: dict[str, list[str]],
        cmd_set: CommandSet | None,
    ) -> tuple[list[Any], dict[str, Any]]:
        """Resolve the instance and arguments required to call a choices/completer function."""
        args: list[Any] = []
        kwargs: dict[str, Any] = {}

        # Resolve the 'self' instance for the method
        self_arg = self._cmd2_app._resolve_func_self(choices_callable.to_call, cmd_set)
        if self_arg is None:
            raise CompletionError("Could not find CommandSet instance matching defining type for completer")

        args.append(self_arg)

        # Check if the function expects 'arg_tokens'
        to_call_params = inspect.signature(choices_callable.to_call).parameters
        if ARG_TOKENS in to_call_params:
            arg_tokens = {**self._parent_tokens, **consumed_arg_values}
            arg_tokens.setdefault(arg_state.action.dest, []).append(text)
            kwargs[ARG_TOKENS] = arg_tokens

        return args, kwargs

    def _complete_arg(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
        arg_state: _ArgumentState,
        consumed_arg_values: dict[str, list[str]],
        *,
        cmd_set: CommandSet | None = None,
    ) -> Completions:
        """Completion routine for an argparse argument.

        :return: a Completions object
        :raises CompletionError: if the completer or choices function this calls raises one
        """
        raw_choices = self._get_raw_choices(arg_state)
        if not raw_choices:
            return Completions()

        # Check if the argument uses a completer function
        if isinstance(raw_choices, ChoicesCallable) and raw_choices.is_completer:
            args, kwargs = self._prepare_callable_params(raw_choices, arg_state, text, consumed_arg_values, cmd_set)
            args.extend([text, line, begidx, endidx])
            completions = raw_choices.completer(*args, **kwargs)

        # Otherwise it uses a choices list or choices provider function
        else:
            all_choices: list[CompletionItem] = []

            if isinstance(raw_choices, ChoicesCallable):
                args, kwargs = self._prepare_callable_params(raw_choices, arg_state, text, consumed_arg_values, cmd_set)
                choices_func = raw_choices.choices_provider
                all_choices = list(choices_func(*args, **kwargs))
            else:
                all_choices = raw_choices

            # Filter used values and run basic completion
            used_values = consumed_arg_values.get(arg_state.action.dest, [])
            filtered = [choice for choice in all_choices if choice.text not in used_values]
            completions = self._cmd2_app.basic_complete(text, line, begidx, endidx, filtered)

        return self._format_completions(arg_state, completions)


# The default ArgparseCompleter class for a cmd2 app
DEFAULT_AP_COMPLETER: type[ArgparseCompleter] = ArgparseCompleter


def set_default_ap_completer_type(completer_type: type[ArgparseCompleter]) -> None:
    """Set the default ArgparseCompleter class for a cmd2 app.

    :param completer_type: Type that is a subclass of ArgparseCompleter.
    """
    global DEFAULT_AP_COMPLETER  # noqa: PLW0603
    DEFAULT_AP_COMPLETER = completer_type
