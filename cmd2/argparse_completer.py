"""Module defines the ArgparseCompleter class which provides argparse-based tab completion to cmd2 apps.

See the header of argparse_custom.py for instructions on how to use these features.
"""

import argparse
import inspect
import numbers
from collections import (
    deque,
)
from collections.abc import Sequence
from typing import (
    IO,
    TYPE_CHECKING,
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
    ChoicesProviderFuncWithTokens,
    CompletionItem,
    generate_range_error,
)
from .command_definition import CommandSet
from .exceptions import CompletionError
from .styles import Cmd2Style

# If no descriptive headers are supplied, then this will be used instead
DEFAULT_DESCRIPTIVE_HEADERS: Sequence[str | Column] = ['Description']

# Name of the choice/completer function argument that, if present, will be passed a dictionary of
# command line tokens up through the token being completed mapped to their argparse destination name.
ARG_TOKENS = 'arg_tokens'


def _build_hint(parser: argparse.ArgumentParser, arg_action: argparse.Action) -> str:
    """Build tab completion hint for a given argument."""
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
        self.min: int | str
        self.max: float | int | str
        self.count = 0
        self.is_remainder = self.action.nargs == argparse.REMAINDER

        # Check if nargs is a range
        nargs_range = self.action.get_nargs_range()  # type: ignore[attr-defined]
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
            self.min = self.action.nargs
            self.max = self.action.nargs


class _UnfinishedFlagError(CompletionError):
    def __init__(self, flag_arg_state: _ArgumentState) -> None:
        """CompletionError which occurs when the user has not finished the current flag.

        :param flag_arg_state: information about the unfinished flag action.
        """
        arg = f'{argparse._get_action_name(flag_arg_state.action)}'
        err = f'{generate_range_error(cast(int, flag_arg_state.min), cast(int | float, flag_arg_state.max))}'
        error = f"Error: argument {arg}: {err} ({flag_arg_state.count} entered)"
        super().__init__(error)


class _NoResultsError(CompletionError):
    def __init__(self, parser: argparse.ArgumentParser, arg_action: argparse.Action) -> None:
        """CompletionError which occurs when there are no results.

        If hinting is allowed, then its message will be a hint about the argument being tab completed.

        :param parser: ArgumentParser instance which owns the action being tab completed
        :param arg_action: action being tab completed.
        """
        # Set apply_style to False because we don't want hints to look like errors
        super().__init__(_build_hint(parser, arg_action), apply_style=False)


class ArgparseCompleter:
    """Automatic command line tab completion based on argparse parameters."""

    def __init__(
        self, parser: argparse.ArgumentParser, cmd2_app: 'Cmd', *, parent_tokens: dict[str, list[str]] | None = None
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

        self._flags = []  # all flags in this command
        self._flag_to_action = {}  # maps flags to the argparse action object
        self._positional_actions = []  # actions for positional arguments (by position index)
        self._subcommand_action = None  # this will be set if self._parser has subcommands

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
        self, text: str, line: str, begidx: int, endidx: int, tokens: list[str], *, cmd_set: CommandSet | None = None
    ) -> list[str]:
        """Complete text using argparse metadata."""
        if not tokens:
            return []

        # Positionals args that are left to parse
        remaining_positionals = deque(self._positional_actions)

        # This gets set to True when flags will no longer be processed as argparse flags
        skip_remaining_flags = False

        # _ArgumentState of the current positional
        pos_arg_state: _ArgumentState | None = None

        # _ArgumentState of the current flag
        flag_arg_state: _ArgumentState | None = None

        # Non-reusable flags that we've parsed
        matched_flags: list[str] = []

        # Keeps track of arguments we've seen and any tokens they consumed
        consumed_arg_values: dict[str, list[str]] = {}  # dict(arg_name -> list[tokens])

        # Completed mutually exclusive groups
        completed_mutex_groups: dict[argparse._MutuallyExclusiveGroup, argparse.Action] = {}

        def consume_argument(arg_state: _ArgumentState, token: str) -> None:
            """Consuming token as an argument."""
            arg_state.count += 1
            consumed_arg_values.setdefault(arg_state.action.dest, [])
            consumed_arg_values[arg_state.action.dest].append(token)

        def update_mutex_groups(arg_action: argparse.Action) -> None:
            """Check if an argument belongs to a mutually exclusive group potenitally mark that group complete."""
            # Check if this action is in a mutually exclusive group
            for group in self._parser._mutually_exclusive_groups:
                if arg_action in group._group_actions:
                    # Check if the group this action belongs to has already been completed
                    if group in completed_mutex_groups:
                        completer_action = completed_mutex_groups[group]
                        if arg_action != completer_action:
                            arg_str = f'{argparse._get_action_name(arg_action)}'
                            completer_str = f'{argparse._get_action_name(completer_action)}'
                            raise CompletionError(f"Error: argument {arg_str}: not allowed with argument {completer_str}")
                        return

                    # Mark that this action completed the group
                    completed_mutex_groups[group] = arg_action

                    # Don't tab complete any of the other args in the group
                    for group_action in group._group_actions:
                        if group_action == arg_action:
                            continue
                        if group_action in self._flag_to_action.values():
                            matched_flags.extend(group_action.option_strings)
                        elif group_action in remaining_positionals:
                            remaining_positionals.remove(group_action)
                    break

        #############################################################################################
        # Parse all but the last token
        #############################################################################################
        for token_index, token in enumerate(tokens[:-1]):
            # Remainder handling
            if pos_arg_state is not None and pos_arg_state.is_remainder:
                consume_argument(pos_arg_state, token)
                continue
            if flag_arg_state is not None and flag_arg_state.is_remainder:
                if token == '--':  # noqa: S105
                    flag_arg_state = None
                else:
                    consume_argument(flag_arg_state, token)
                continue

            # Handle '--'
            if token == '--' and not skip_remaining_flags:  # noqa: S105
                if flag_arg_state and isinstance(flag_arg_state.min, int) and flag_arg_state.count < flag_arg_state.min:
                    raise _UnfinishedFlagError(flag_arg_state)
                flag_arg_state = None
                skip_remaining_flags = True
                continue

            # Flag handling
            if _looks_like_flag(token, self._parser) and not skip_remaining_flags:
                if flag_arg_state and isinstance(flag_arg_state.min, int) and flag_arg_state.count < flag_arg_state.min:
                    raise _UnfinishedFlagError(flag_arg_state)
                flag_arg_state = None
                action = self._flag_to_action.get(token)
                if action is None and self._parser.allow_abbrev:
                    candidates = [f for f in self._flag_to_action if f.startswith(token)]
                    if len(candidates) == 1:
                        action = self._flag_to_action[candidates[0]]
                if action:
                    update_mutex_groups(action)
                    if isinstance(action, (argparse._AppendAction, argparse._AppendConstAction, argparse._CountAction)):
                        consumed_arg_values.setdefault(action.dest, [])
                    else:
                        matched_flags.extend(action.option_strings)
                        consumed_arg_values[action.dest] = []
                    new_arg_state = _ArgumentState(action)
                    if new_arg_state.max > 0:  # type: ignore[operator]
                        flag_arg_state = new_arg_state
                        skip_remaining_flags = flag_arg_state.is_remainder
            elif flag_arg_state is not None:
                consume_argument(flag_arg_state, token)
                if isinstance(flag_arg_state.max, (float, int)) and flag_arg_state.count >= flag_arg_state.max:
                    flag_arg_state = None
            # Positional handling
            else:
                if pos_arg_state is None and remaining_positionals:
                    action = remaining_positionals.popleft()
                    if action == self._subcommand_action:
                        if token in self._subcommand_action.choices:
                            parent_tokens = {**self._parent_tokens, **consumed_arg_values}
                            if action.dest != argparse.SUPPRESS:
                                parent_tokens[action.dest] = [token]
                            parser = self._subcommand_action.choices[token]
                            completer_type = self._cmd2_app._determine_ap_completer_type(parser)
                            completer = completer_type(parser, self._cmd2_app, parent_tokens=parent_tokens)
                            return completer.complete(text, line, begidx, endidx, tokens[token_index + 1 :], cmd_set=cmd_set)
                        return []
                    pos_arg_state = _ArgumentState(action)
                if pos_arg_state is not None:
                    update_mutex_groups(pos_arg_state.action)
                    consume_argument(pos_arg_state, token)
                    if pos_arg_state.is_remainder:
                        skip_remaining_flags = True
                    elif isinstance(pos_arg_state.max, (float, int)) and pos_arg_state.count >= pos_arg_state.max:
                        pos_arg_state = None
                        if remaining_positionals and remaining_positionals[0].nargs == argparse.REMAINDER:
                            skip_remaining_flags = True

        #############################################################################################
        # Complete the last token
        #############################################################################################
        if _looks_like_flag(text, self._parser) and not skip_remaining_flags:
            if flag_arg_state and isinstance(flag_arg_state.min, int) and flag_arg_state.count < flag_arg_state.min:
                raise _UnfinishedFlagError(flag_arg_state)
            return cast(list[str], self._complete_flags(text, line, begidx, endidx, matched_flags))

        completion_results: list[str] = []
        if flag_arg_state is not None:
            completion_results = self._complete_arg(
                text, line, begidx, endidx, flag_arg_state, consumed_arg_values, cmd_set=cmd_set
            )
            if completion_results:
                if not self._cmd2_app.completion_hint:
                    self._cmd2_app.completion_hint = _build_hint(self._parser, flag_arg_state.action)
                return completion_results
            if (
                (isinstance(flag_arg_state.min, int) and flag_arg_state.count < flag_arg_state.min)
                or not _single_prefix_char(text, self._parser)
                or skip_remaining_flags
            ):
                raise _NoResultsError(self._parser, flag_arg_state.action)
        elif pos_arg_state is not None or remaining_positionals:
            if pos_arg_state is None:
                pos_arg_state = _ArgumentState(remaining_positionals.popleft())
            completion_results = self._complete_arg(
                text, line, begidx, endidx, pos_arg_state, consumed_arg_values, cmd_set=cmd_set
            )
            if completion_results:
                if not self._cmd2_app.completion_hint and not isinstance(pos_arg_state.action, argparse._SubParsersAction):
                    self._cmd2_app.completion_hint = _build_hint(self._parser, pos_arg_state.action)
                return completion_results
            # Fallback to flags if allowed
            if not skip_remaining_flags and (
                _looks_like_flag(text, self._parser)
                or _single_prefix_char(text, self._parser)
                or (isinstance(pos_arg_state.min, int) and pos_arg_state.count >= pos_arg_state.min)
            ):
                flag_results = self._complete_flags(text, line, begidx, endidx, matched_flags)
                if flag_results:
                    return cast(list[str], flag_results)
            if not _single_prefix_char(text, self._parser) or skip_remaining_flags:
                raise _NoResultsError(self._parser, pos_arg_state.action)

        if not skip_remaining_flags and (not text or _single_prefix_char(text, self._parser) or not remaining_positionals):
            self._cmd2_app._reset_completion_defaults()
            return cast(list[str], self._complete_flags(text, line, begidx, endidx, matched_flags))
        return []

    def _complete_flags(
        self, text: str, line: str, begidx: int, endidx: int, matched_flags: list[str]
    ) -> list[CompletionItem]:
        """Tab completion routine for a parsers unused flags."""
        match_against = []
        for flag in self._flags:
            if flag not in matched_flags:
                action = self._flag_to_action[flag]
                if action.help != argparse.SUPPRESS:
                    match_against.append(flag)

        matches = self._cmd2_app.basic_complete(text, line, begidx, endidx, match_against)
        matched_actions: dict[argparse.Action, list[str]] = {}
        for flag in matches:
            action = self._flag_to_action[flag]
            matched_actions.setdefault(action, []).append(flag)

        results: list[CompletionItem] = []
        for action, option_strings in matched_actions.items():
            flag_text = ', '.join(option_strings)
            if not action.required:
                flag_text = '[' + flag_text + ']'
            self._cmd2_app.display_matches.append(flag_text)
            results.extend(CompletionItem(opt, [action.help if action.help else '']) for opt in option_strings)
        return results

    def _format_completions(self, arg_state: _ArgumentState, completions: list[str] | list[CompletionItem]) -> list[str]:
        """Format CompletionItems into hint table."""
        if len(completions) < 2 or not all(isinstance(c, CompletionItem) for c in completions):
            return cast(list[str], completions)

        items = cast(list[CompletionItem], completions)
        all_nums = all(isinstance(c.orig_value, numbers.Number) for c in items)

        if not self._cmd2_app.matches_sorted:
            if all_nums:
                items.sort(key=lambda c: c.orig_value)
            else:
                items.sort(key=self._cmd2_app.default_sort_key)
            self._cmd2_app.matches_sorted = True

        if len(completions) <= self._cmd2_app.max_completion_items:
            if isinstance(arg_state.action, argparse._SubParsersAction) or (
                arg_state.action.metavar == "COMMAND" and arg_state.action.dest == "command"
            ):
                return cast(list[str], completions)

            destination = arg_state.action.metavar if arg_state.action.metavar else arg_state.action.dest
            if isinstance(destination, tuple):
                destination = destination[min(len(destination) - 1, arg_state.count)]

            headers: list[Column] = []
            headers.append(Column(destination.upper(), justify="right" if all_nums else "left", no_wrap=True))
            desc_headers = cast(Sequence[str | Column] | None, arg_state.action.get_descriptive_headers())  # type: ignore[attr-defined]
            if desc_headers is None:
                desc_headers = DEFAULT_DESCRIPTIVE_HEADERS
            headers.extend(dh if isinstance(dh, Column) else Column(dh, overflow="fold") for dh in desc_headers)

            hint_table = Table(*headers, box=SIMPLE_HEAD, show_edge=False, border_style=Cmd2Style.TABLE_BORDER)
            for item in items:
                hint_table.add_row(item, *item.descriptive_data)

            console = Cmd2GeneralConsole()
            with console.capture() as capture:
                console.print(hint_table, end="")
            self._cmd2_app.formatted_completions = capture.get()
        return cast(list[str], completions)

    def complete_subcommand_help(self, text: str, line: str, begidx: int, endidx: int, tokens: list[str]) -> list[str]:
        """Supports cmd2's help command in the completion of subcommand names."""
        if self._subcommand_action is not None:
            for token_index, token in enumerate(tokens):
                if token in self._subcommand_action.choices:
                    parser = self._subcommand_action.choices[token]
                    completer = self._cmd2_app._determine_ap_completer_type(parser)(parser, self._cmd2_app)
                    return completer.complete_subcommand_help(text, line, begidx, endidx, tokens[token_index + 1 :])
                if token_index == len(tokens) - 1:
                    return self._cmd2_app.basic_complete(text, line, begidx, endidx, self._subcommand_action.choices)
                break
        return []

    def print_help(self, tokens: list[str], file: IO[str] | None = None) -> None:
        """Supports cmd2's help command in the printing of help text."""
        if tokens and self._subcommand_action is not None:
            parser = cast(argparse.ArgumentParser | None, self._subcommand_action.choices.get(tokens[0]))
            if parser:
                completer = self._cmd2_app._determine_ap_completer_type(parser)(parser, self._cmd2_app)
                completer.print_help(tokens[1:])
                return
        self._parser.print_help(file=file)

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
    ) -> list[str]:
        """Tab completion routine for an argparse argument."""
        arg_choices: list[str] | list[CompletionItem] | ChoicesCallable
        if arg_state.action.choices is not None:
            if isinstance(arg_state.action, argparse._SubParsersAction):
                items: list[CompletionItem] = []
                parser_help = {}
                for action in arg_state.action._choices_actions:
                    if action.dest in arg_state.action.choices:
                        subparser = arg_state.action.choices[action.dest]
                        parser_help[subparser] = action.help if action.help else ''
                for name, subparser in arg_state.action.choices.items():
                    items.append(CompletionItem(name, [parser_help.get(subparser, '')]))
                arg_choices = items
            else:
                arg_choices = list(arg_state.action.choices)
            if not arg_choices:
                return []
            if all(isinstance(x, numbers.Number) for x in arg_choices):
                arg_choices.sort()
                self._cmd2_app.matches_sorted = True
            for index, choice in enumerate(arg_choices):
                if not isinstance(choice, str):
                    arg_choices[index] = str(choice)  # type: ignore[unreachable]
        else:
            choices_attr = arg_state.action.get_choices_callable()  # type: ignore[attr-defined]
            if choices_attr is None:
                return []
            arg_choices = choices_attr

        args = []
        kwargs = {}
        if isinstance(arg_choices, ChoicesCallable):
            self_arg = self._cmd2_app._resolve_func_self(arg_choices.to_call, cmd_set)
            if self_arg is None:
                raise CompletionError('Could not find CommandSet instance matching defining type for completer')
            args.append(self_arg)
            to_call_params = inspect.signature(arg_choices.to_call).parameters
            if ARG_TOKENS in to_call_params:
                arg_tokens = {**self._parent_tokens, **consumed_arg_values}
                arg_tokens.setdefault(arg_state.action.dest, []).append(text)
                kwargs[ARG_TOKENS] = arg_tokens

        if isinstance(arg_choices, ChoicesCallable) and arg_choices.is_completer:
            args.extend([text, line, begidx, endidx])
            results = arg_choices.completer(*args, **kwargs)  # type: ignore[arg-type]
        else:
            completion_items: list[str] | list[CompletionItem] = []
            if isinstance(arg_choices, ChoicesCallable):
                if not arg_choices.is_completer:
                    choices_func = arg_choices.choices_provider
                    if isinstance(choices_func, ChoicesProviderFuncWithTokens):
                        completion_items = choices_func(*args, **kwargs)
                    else:
                        completion_items = choices_func(*args)
            else:
                completion_items = arg_choices
            used_values = consumed_arg_values.get(arg_state.action.dest, [])
            completion_items = [choice for choice in completion_items if choice not in used_values]
            results = self._cmd2_app.basic_complete(text, line, begidx, endidx, completion_items)

        if not results:
            self._cmd2_app.matches_sorted = False
            return []
        return self._format_completions(arg_state, results)


DEFAULT_AP_COMPLETER: type[ArgparseCompleter] = ArgparseCompleter


def set_default_ap_completer_type(completer_type: type[ArgparseCompleter]) -> None:
    """Set the default ArgparseCompleter class for a cmd2 app."""
    global DEFAULT_AP_COMPLETER  # noqa: PLW0603
    DEFAULT_AP_COMPLETER = completer_type
