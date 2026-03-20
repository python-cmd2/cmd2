"""Module provides Typer/Click-based command parsing support for cmd2.

This is the Typer equivalent of argparse_custom.py. It contains all
Typer-specific logic for building Click commands, completing arguments,
and resolving subcommands for help output.

Typer support is optional and requires the ``typer`` package to be installed.
Install it via ``pip install cmd2[typer]``.
"""

import copy
import inspect
from collections.abc import Callable, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    TypeAlias,
    get_type_hints,
)

import click

from . import constants
from .completion import (
    CompletionItem,
    Completions,
)
from .constants import COMMAND_FUNC_PREFIX
from .types import CmdOrSet

if TYPE_CHECKING:  # pragma: no cover
    import typer

    from .cmd2 import Cmd
    from .command_definition import CommandFunc

#: Type alias for the Click Command objects produced by the Typer integration.
#: All Typer commands are converted to Click Commands via :func:`build_typer_command`.
TyperParser: TypeAlias = click.Command


def build_typer_callback(
    target_func: Callable[..., Any],
    parent: CmdOrSet,
    command_method: 'CommandFunc',
) -> Callable[..., Any]:
    """Build a Click-compatible callback from a Typer-decorated command function.

    Resolves type hints (including ``Annotated``) and strips the ``self``
    parameter so Click/Typer can introspect the signature correctly.

    :param target_func: the original command function to wrap
    :param parent: object which owns the command (Cmd or CommandSet instance)
    :param command_method: the decorated command method (used for extra kwargs)
    :return: callback function with resolved type hints and bound self
    """
    sig = inspect.signature(target_func)
    resolved_hints = get_type_hints(target_func, include_extras=True)
    params = list(sig.parameters.values())
    has_self = params and params[0].name == "self"
    if has_self:
        params = params[1:]

    callback_params = [param.replace(annotation=resolved_hints.get(param.name, param.annotation)) for param in params]
    callback_sig = sig.replace(
        parameters=callback_params,
        return_annotation=resolved_hints.get('return', sig.return_annotation),
    )

    def callback(*args: Any, **kwargs: Any) -> Any:
        # Merge in kwargs passed programmatically (e.g. do_method(..., key=val))
        # so they take effect even when Click doesn't see them on the command line.
        extra_kwargs = getattr(command_method, constants.CMD_ATTR_TYPER_KWARGS, {})
        merged_kwargs = dict(kwargs)
        for key, value in extra_kwargs.items():
            if key not in merged_kwargs or merged_kwargs[key] is None:
                merged_kwargs[key] = value
        if has_self:
            return target_func(parent, *args, **merged_kwargs)
        return target_func(*args, **merged_kwargs)

    callback.__name__ = target_func.__name__
    callback.__doc__ = target_func.__doc__
    callback.__annotations__ = dict(resolved_hints)
    callback.__annotations__.pop("self", None)
    callback.__signature__ = callback_sig  # type: ignore[attr-defined]
    return callback


def bind_typer_app(app: 'typer.Typer', parent: CmdOrSet, command_method: 'CommandFunc') -> 'typer.Typer':
    """Deep copy a Typer app and bind all callbacks to the given parent instance.

    Recursively walks through all registered commands and groups in the app,
    wrapping each callback with :func:`build_typer_callback` so that ``self``
    is correctly bound.

    :param app: the Typer app to bind
    :param parent: object which owns the command (Cmd or CommandSet instance)
    :param command_method: the decorated command method
    :return: deep copy of the app with bound callbacks
    """
    bound_app = copy.deepcopy(app)

    def _bind_group(group: 'typer.Typer') -> None:
        if group.registered_callback is not None and callable(group.registered_callback.callback):
            group.registered_callback.callback = build_typer_callback(
                group.registered_callback.callback,
                parent,
                command_method,
            )

        for command_info in group.registered_commands:
            if command_info.callback is not None:
                command_info.callback = build_typer_callback(command_info.callback, parent, command_method)

        for group_info in group.registered_groups:
            if callable(group_info.callback):
                group_info.callback = build_typer_callback(group_info.callback, parent, command_method)
            if group_info.typer_instance is not None:
                _bind_group(group_info.typer_instance)

    _bind_group(bound_app)
    return bound_app


#: Options to strip from Click commands in a REPL context.
#: --help is handled by cmd2's built-in help, and completion options
#: are handled by prompt_toolkit / readline.
_REPL_STRIP_NAMES = frozenset(('help', 'install_completion', 'show_completion'))


def _strip_repl_options(command: click.Command) -> None:
    """Remove ``--help``, ``--install-completion``, and ``--show-completion`` from a Click command tree.

    These options are intended for standalone CLI tools. In a cmd2 REPL,
    help is provided by the built-in ``help`` command and shell completion
    is handled by prompt_toolkit / readline, so these options are unnecessary clutter.

    Mutates the command (and any subcommands) in place.
    """
    command.params = [p for p in command.params if p.name not in _REPL_STRIP_NAMES]
    # Prevent Click from re-adding --help
    if hasattr(command, 'add_help_option'):
        command.add_help_option = False

    # Recurse into subcommands for Groups
    sub_commands: dict[str, click.Command] | None = getattr(command, 'commands', None)
    if sub_commands is not None:
        for sub_cmd in sub_commands.values():
            _strip_repl_options(sub_cmd)


def build_typer_command(
    parent: CmdOrSet,
    command_method: 'CommandFunc',
) -> TyperParser:
    """Build a Typer/Click command for a command method.

    This is the Typer equivalent of :meth:`Cmd._build_parser`. It creates a
    Click ``Command`` object from the attributes set by the ``@with_typer``
    decorator on the command method.

    :param parent: object which owns the command (Cmd or CommandSet instance)
    :param command_method: the decorated command method
    :return: Click Command object
    :raises ImportError: if typer is not installed
    """
    try:
        import typer
    except ModuleNotFoundError as exc:
        raise ImportError("Typer support requires 'cmd2[typer]' to be installed") from exc

    # CMD_ATTR_TYPER stores the explicit Typer app, or None for auto-build
    explicit_app = getattr(command_method, constants.CMD_ATTR_TYPER, None)

    if explicit_app is not None:
        bound_app = bind_typer_app(explicit_app, parent, command_method)
        bound_app._add_completion = False
        click_command = typer.main.get_command(bound_app)
    else:
        target_func = getattr(command_method, constants.CMD_ATTR_TYPER_FUNC, command_method)
        callback = build_typer_callback(target_func, parent, command_method)
        context_settings = getattr(command_method, constants.CMD_ATTR_TYPER_CONTEXT_SETTINGS, None)
        app = typer.Typer(add_completion=False, context_settings=context_settings)
        command_name = command_method.__name__[len(COMMAND_FUNC_PREFIX) :]
        app.command(name=command_name)(callback)
        click_command = typer.main.get_command(app)

    # Strip --help, --install-completion, --show-completion from the command tree.
    # In a REPL, help is provided by cmd2's built-in ``help`` command and shell
    # completion is handled by prompt_toolkit / readline.
    _strip_repl_options(click_command)
    return click_command


def typer_complete(
    cmd: 'Cmd',
    text: str,
    _line: str,
    _begidx: int,
    _endidx: int,
    *,
    command_func: 'CommandFunc',
    args: Sequence[str],
) -> Completions:
    """Complete values for Typer/Click-based commands.

    This is the Typer equivalent of :class:`ArgparseCompleter.complete`.
    It delegates to Click's shell completion machinery to generate
    completion candidates.

    The signature matches the ``CompleterBound`` protocol so it can be used
    with ``functools.partial`` the same way the argparse completer is.

    :param cmd: the Cmd instance (used for error formatting and parser cache)
    :param text: the string prefix we are attempting to match
    :param _line: the current input line (unused, for signature compatibility)
    :param _begidx: beginning index of text (unused, for signature compatibility)
    :param _endidx: ending index of text (unused, for signature compatibility)
    :param command_func: the command function being completed
    :param args: parsed argument tokens so far
    :return: a Completions object
    """
    from click.shell_completion import CompletionItem as ClickCompletionItem
    from click.shell_completion import ShellComplete

    try:
        parser = cmd._command_parsers.get(command_func)
        if not isinstance(parser, click.Command):
            return Completions()
        args_list = list(args)
        remaining_args = args_list[:-1] if args_list else []
        completer = ShellComplete(parser, {}, parser.name or "", "")
        results = completer.get_completions(remaining_args, text)
        items = [
            CompletionItem(
                value=item.value,
                display=item.value,
                display_meta=item.help or "",
            )
            if isinstance(item, ClickCompletionItem)
            else CompletionItem(value=item)
            for item in results
        ]
        return Completions(items=items)
    except Exception as exc:  # noqa: BLE001
        return Completions(error=cmd.format_exception(exc))


def resolve_typer_subcommand(command: TyperParser, subcommands: Sequence[str]) -> tuple[TyperParser, list[str]]:
    """Resolve nested Click subcommands for Typer-backed help paths.

    :param command: the top-level Click Command or Group
    :param subcommands: sequence of subcommand names to resolve
    :return: tuple of (resolved command, list of resolved names)
    :raises KeyError: if a subcommand is not found
    """
    current = command
    resolved_names: list[str] = []
    for subcommand in subcommands:
        commands = getattr(current, 'commands', None)
        if commands is None or subcommand not in commands:
            raise KeyError(subcommand)
        current = commands[subcommand]
        resolved_names.append(current.name or subcommand)
    return current, resolved_names


def typer_complete_subcommand_help(
    cmd: 'Cmd',
    text: str,
    _line: str,
    _begidx: int,
    _endidx: int,
    *,
    command_func: 'CommandFunc',
    subcommands: Sequence[str],
) -> Completions:
    """Complete subcommand names for Typer/Click-based help paths.

    This is the Typer equivalent of
    :meth:`ArgparseCompleter.complete_subcommand_help`. It walks the Click
    command tree using already-resolved subcommand tokens and returns
    available child subcommand names for the current level.

    :param cmd: the Cmd instance (used for parser cache and error formatting)
    :param text: the string prefix we are attempting to match
    :param _line: the current input line (unused, for signature compatibility)
    :param _begidx: beginning index of text (unused, for signature compatibility)
    :param _endidx: ending index of text (unused, for signature compatibility)
    :param command_func: the command function being completed
    :param subcommands: subcommand tokens already entered
    :return: a Completions object with matching subcommand names
    """
    parser = cmd._command_parsers.get(command_func)
    if not isinstance(parser, click.Command):
        return Completions()

    # Resolve already-entered subcommands to find the current group
    try:
        current, _ = resolve_typer_subcommand(parser, subcommands)
    except KeyError:
        return Completions()

    # List available subcommands at this level
    commands = getattr(current, 'commands', None)
    if commands is None:
        return Completions()

    items = [
        CompletionItem(
            value=name,
            display=name,
            display_meta=sub_cmd.get_short_help_str() if hasattr(sub_cmd, 'get_short_help_str') else "",
        )
        for name, sub_cmd in commands.items()
        if name.startswith(text)
    ]
    return Completions(items=items)
