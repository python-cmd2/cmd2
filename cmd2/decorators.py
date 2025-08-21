"""Decorators for ``cmd2`` commands."""

import argparse
from collections.abc import Callable, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
    Union,
)

from . import (
    constants,
)
from .argparse_custom import (
    Cmd2AttributeWrapper,
)
from .command_definition import (
    CommandFunc,
    CommandSet,
)
from .exceptions import (
    Cmd2ArgparseError,
)
from .parsing import (
    Statement,
)

if TYPE_CHECKING:  # pragma: no cover
    import cmd2


def with_category(category: str) -> Callable[[CommandFunc], CommandFunc]:
    """Decorate a ``do_*`` command method to apply a category.

    :param category: the name of the category in which this command should
                     be grouped when displaying the list of commands.

    Example:
    ```py
    class MyApp(cmd2.Cmd):
        @cmd2.with_category('Text Functions')
        def do_echo(self, args)
            self.poutput(args)
    ```

    For an alternative approach to categorizing commands using a function, see
    [cmd2.utils.categorize][]

    """

    def cat_decorator(func: CommandFunc) -> CommandFunc:
        from .utils import (
            categorize,
        )

        categorize(func, category)
        return func

    return cat_decorator


CommandParent = TypeVar('CommandParent', bound=Union['cmd2.Cmd', CommandSet])
CommandParentType = TypeVar('CommandParentType', bound=type['cmd2.Cmd'] | type[CommandSet])


RawCommandFuncOptionalBoolReturn = Callable[[CommandParent, Statement | str], bool | None]


##########################
# The _parse_positionals and _arg_swap functions allow for additional positional args to be preserved
# in cmd2 command functions/callables. As long as the 2-ple of arguments we expect to be there can be
# found we can swap out the statement with each decorator's specific parameters
##########################
def _parse_positionals(args: tuple[Any, ...]) -> tuple['cmd2.Cmd', Statement | str]:
    """Inspect the positional arguments until the cmd2.Cmd argument is found.

    Assumes that we will find cmd2.Cmd followed by the command statement object or string.

    :arg args: The positional arguments to inspect
    :return: The cmd2.Cmd reference and the command line statement.
    """
    for pos, arg in enumerate(args):
        from cmd2 import (
            Cmd,
        )

        if isinstance(arg, (Cmd, CommandSet)) and len(args) > pos + 1:
            if isinstance(arg, CommandSet):
                arg = arg._cmd  # noqa: PLW2901
            next_arg = args[pos + 1]
            if isinstance(next_arg, (Statement, str)):
                return arg, args[pos + 1]

    # This shouldn't happen unless we forget to pass statement in `Cmd.onecmd` or
    # somehow call the unbound class method.
    raise TypeError('Expected arguments: cmd: cmd2.Cmd, statement: Union[Statement, str] Not found')


def _arg_swap(args: Sequence[Any], search_arg: Any, *replace_arg: Any) -> list[Any]:
    """Swap the Statement parameter with one or more decorator-specific parameters.

    :param args: The original positional arguments
    :param search_arg: The argument to search for (usually the Statement)
    :param replace_arg: The arguments to substitute in
    :return: The new set of arguments to pass to the command function
    """
    index = args.index(search_arg)
    args_list = list(args)
    args_list[index : index + 1] = replace_arg
    return args_list


#: Function signature for a command function that accepts a pre-processed argument list from user input
#: and optionally returns a boolean
ArgListCommandFuncOptionalBoolReturn = Callable[[CommandParent, list[str]], bool | None]
#: Function signature for a command function that accepts a pre-processed argument list from user input
#: and returns a boolean
ArgListCommandFuncBoolReturn = Callable[[CommandParent, list[str]], bool]
#: Function signature for a command function that accepts a pre-processed argument list from user input
#: and returns Nothing
ArgListCommandFuncNoneReturn = Callable[[CommandParent, list[str]], None]

#: Aggregate of all accepted function signatures for command functions that accept a pre-processed argument list
ArgListCommandFunc = (
    ArgListCommandFuncOptionalBoolReturn[CommandParent]
    | ArgListCommandFuncBoolReturn[CommandParent]
    | ArgListCommandFuncNoneReturn[CommandParent]
)


def with_argument_list(
    func_arg: ArgListCommandFunc[CommandParent] | None = None,
    *,
    preserve_quotes: bool = False,
) -> (
    RawCommandFuncOptionalBoolReturn[CommandParent]
    | Callable[[ArgListCommandFunc[CommandParent]], RawCommandFuncOptionalBoolReturn[CommandParent]]
):
    """Decorate a ``do_*`` method to alter the arguments passed to it so it is passed a list[str].

    Default passes a string of whatever the user typed. With this decorator, the
    decorated method will receive a list of arguments parsed from user input.

    :param func_arg: Single-element positional argument list containing ``doi_*`` method
                 this decorator is wrapping
    :param preserve_quotes: if ``True``, then argument quotes will not be stripped
    :return: function that gets passed a list of argument strings

    Example:
    ```py
    class MyApp(cmd2.Cmd):
        @cmd2.with_argument_list
        def do_echo(self, arglist):
            self.poutput(' '.join(arglist)
    ```

    """
    import functools

    def arg_decorator(func: ArgListCommandFunc[CommandParent]) -> RawCommandFuncOptionalBoolReturn[CommandParent]:
        """Decorate function that ingests an Argument List function and returns a raw command function.

        The returned function will process the raw input into an argument list to be passed to the wrapped function.

        :param func: The defined argument list command function
        :return: Function that takes raw input and converts to an argument list to pass to the wrapped function.
        """

        @functools.wraps(func)
        def cmd_wrapper(*args: Any, **kwargs: Any) -> bool | None:
            """Command function wrapper which translates command line into an argument list and calls actual command function.

            :param args: All positional arguments to this function.  We're expecting there to be:
                            cmd2_app, statement: Union[Statement, str]
                            contiguously somewhere in the list
            :param kwargs: any keyword arguments being passed to command function
            :return: return value of command function
            """
            cmd2_app, statement = _parse_positionals(args)
            _, parsed_arglist = cmd2_app.statement_parser.get_command_arg_list(command_name, statement, preserve_quotes)
            args_list = _arg_swap(args, statement, parsed_arglist)
            return func(*args_list, **kwargs)

        command_name = func.__name__[len(constants.COMMAND_FUNC_PREFIX) :]
        cmd_wrapper.__doc__ = func.__doc__
        return cmd_wrapper

    if callable(func_arg):
        return arg_decorator(func_arg)
    return arg_decorator


#: Function signatures for command functions that use an argparse.ArgumentParser to process user input
#: and optionally return a boolean
ArgparseCommandFuncOptionalBoolReturn = Callable[[CommandParent, argparse.Namespace], bool | None]
ArgparseCommandFuncWithUnknownArgsOptionalBoolReturn = Callable[[CommandParent, argparse.Namespace, list[str]], bool | None]

#: Function signatures for command functions that use an argparse.ArgumentParser to process user input
#: and return a boolean
ArgparseCommandFuncBoolReturn = Callable[[CommandParent, argparse.Namespace], bool]
ArgparseCommandFuncWithUnknownArgsBoolReturn = Callable[[CommandParent, argparse.Namespace, list[str]], bool]

#: Function signatures for command functions that use an argparse.ArgumentParser to process user input
#: and return nothing
ArgparseCommandFuncNoneReturn = Callable[[CommandParent, argparse.Namespace], None]
ArgparseCommandFuncWithUnknownArgsNoneReturn = Callable[[CommandParent, argparse.Namespace, list[str]], None]

#: Aggregate of all accepted function signatures for an argparse command function
ArgparseCommandFunc = (
    ArgparseCommandFuncOptionalBoolReturn[CommandParent]
    | ArgparseCommandFuncWithUnknownArgsOptionalBoolReturn[CommandParent]
    | ArgparseCommandFuncBoolReturn[CommandParent]
    | ArgparseCommandFuncWithUnknownArgsBoolReturn[CommandParent]
    | ArgparseCommandFuncNoneReturn[CommandParent]
    | ArgparseCommandFuncWithUnknownArgsNoneReturn[CommandParent]
)


def with_argparser(
    parser: argparse.ArgumentParser  # existing parser
    | Callable[[], argparse.ArgumentParser]  # function or staticmethod
    | Callable[[CommandParentType], argparse.ArgumentParser],  # Cmd or CommandSet classmethod
    *,
    ns_provider: Callable[..., argparse.Namespace] | None = None,
    preserve_quotes: bool = False,
    with_unknown_args: bool = False,
) -> Callable[[ArgparseCommandFunc[CommandParent]], RawCommandFuncOptionalBoolReturn[CommandParent]]:
    """Decorate a ``do_*`` method to populate its ``args`` argument with the given instance of argparse.ArgumentParser.

    :param parser: instance of ArgumentParser or a callable that returns an ArgumentParser for this command
    :param ns_provider: An optional function that accepts a cmd2.Cmd or cmd2.CommandSet object as an argument and returns an
                        argparse.Namespace. This is useful if the Namespace needs to be prepopulated with state data that
                        affects parsing.
    :param preserve_quotes: if ``True``, then arguments passed to argparse maintain their quotes
    :param with_unknown_args: if true, then capture unknown args
    :return: function that gets passed argparse-parsed args in a ``Namespace``
             A [cmd2.argparse_custom.Cmd2AttributeWrapper][] called ``cmd2_statement`` is included
             in the ``Namespace`` to provide access to the [cmd2.Statement][] object that was created when
             parsing the command line. This can be useful if the command function needs to know the command line.

    Example:
    ```py
    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    parser.add_argument('words', nargs='+', help='words to print')

    class MyApp(cmd2.Cmd):
        @cmd2.with_argparser(parser, preserve_quotes=True)
        def do_argprint(self, args):
            "Print the options and argument list this options command was called with."
            self.poutput(f'args: {args!r}')
    ```

    Example with unknown args:

    ```py
    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    parser.add_argument('-r', '--repeat', type=int, help='output [n] times')

    class MyApp(cmd2.Cmd):
        @cmd2.with_argparser(parser, with_unknown_args=True)
        def do_argprint(self, args, unknown):
            "Print the options and argument list this options command was called with."
            self.poutput(f'args: {args!r}')
            self.poutput(f'unknowns: {unknown}')
    ```

    """
    import functools

    def arg_decorator(func: ArgparseCommandFunc[CommandParent]) -> RawCommandFuncOptionalBoolReturn[CommandParent]:
        """Decorate function that ingests an Argparse Command Function and returns a raw command function.

        The returned function will process the raw input into an argparse Namespace to be passed to the wrapped function.

        :param func: The defined argparse command function
        :return: Function that takes raw input and converts to an argparse Namespace to passed to the wrapped function.
        """

        @functools.wraps(func)
        def cmd_wrapper(*args: Any, **kwargs: dict[str, Any]) -> bool | None:
            """Command function wrapper which translates command line into argparse Namespace and call actual command function.

            :param args: All positional arguments to this function.  We're expecting there to be:
                            cmd2_app, statement: Union[Statement, str]
                            contiguously somewhere in the list
            :param kwargs: any keyword arguments being passed to command function
            :return: return value of command function
            :raises Cmd2ArgparseError: if argparse has error parsing command line
            """
            cmd2_app, statement_arg = _parse_positionals(args)
            statement, parsed_arglist = cmd2_app.statement_parser.get_command_arg_list(
                command_name, statement_arg, preserve_quotes
            )

            # Pass cmd_wrapper instead of func, since it contains the parser info.
            arg_parser = cmd2_app._command_parsers.get(cmd_wrapper)
            if arg_parser is None:
                # This shouldn't be possible to reach
                raise ValueError(f'No argument parser found for {command_name}')  # pragma: no cover

            if ns_provider is None:
                namespace = None
            else:
                # The namespace provider may or may not be defined in the same class as the command. Since provider
                # functions are registered with the command argparser before anything is instantiated, we
                # need to find an instance at runtime that matches the types during declaration
                provider_self = cmd2_app._resolve_func_self(ns_provider, args[0])
                namespace = ns_provider(provider_self if provider_self is not None else cmd2_app)

            try:
                new_args: tuple[argparse.Namespace] | tuple[argparse.Namespace, list[str]]
                if with_unknown_args:
                    new_args = arg_parser.parse_known_args(parsed_arglist, namespace)
                else:
                    new_args = (arg_parser.parse_args(parsed_arglist, namespace),)
                ns = new_args[0]
            except SystemExit as exc:
                raise Cmd2ArgparseError from exc
            else:
                # Add wrapped statement to Namespace as cmd2_statement
                ns.cmd2_statement = Cmd2AttributeWrapper(statement)

                # Add wrapped subcmd handler (which can be None) to Namespace as cmd2_handler
                handler = getattr(ns, constants.NS_ATTR_SUBCMD_HANDLER, None)
                ns.cmd2_handler = Cmd2AttributeWrapper(handler)

                # Remove the subcmd handler attribute from the Namespace
                # since cmd2_handler is how a developer accesses it.
                if hasattr(ns, constants.NS_ATTR_SUBCMD_HANDLER):
                    delattr(ns, constants.NS_ATTR_SUBCMD_HANDLER)

                args_list = _arg_swap(args, statement_arg, *new_args)
                return func(*args_list, **kwargs)

        command_name = func.__name__[len(constants.COMMAND_FUNC_PREFIX) :]

        # Set some custom attributes for this command
        setattr(cmd_wrapper, constants.CMD_ATTR_ARGPARSER, parser)
        setattr(cmd_wrapper, constants.CMD_ATTR_PRESERVE_QUOTES, preserve_quotes)

        return cmd_wrapper

    return arg_decorator


def as_subcommand_to(
    command: str,
    subcommand: str,
    parser: argparse.ArgumentParser  # existing parser
    | Callable[[], argparse.ArgumentParser]  # function or staticmethod
    | Callable[[CommandParentType], argparse.ArgumentParser],  # Cmd or CommandSet classmethod
    *,
    help: str | None = None,  # noqa: A002
    aliases: list[str] | None = None,
) -> Callable[[ArgparseCommandFunc[CommandParent]], ArgparseCommandFunc[CommandParent]]:
    """Tag this method as a subcommand to an existing argparse decorated command.

    :param command: Command Name. Space-delimited subcommands may optionally be specified
    :param subcommand: Subcommand name
    :param parser: instance of ArgumentParser or a callable that returns an ArgumentParser for this subcommand
    :param help: Help message for this subcommand which displays in the list of subcommands of the command we are adding to.
                 This is passed as the help argument to subparsers.add_parser().
    :param aliases: Alternative names for this subcommand. This is passed as the alias argument to
                    subparsers.add_parser().
    :return: Wrapper function that can receive an argparse.Namespace
    """

    def arg_decorator(func: ArgparseCommandFunc[CommandParent]) -> ArgparseCommandFunc[CommandParent]:
        # Set some custom attributes for this command
        setattr(func, constants.SUBCMD_ATTR_COMMAND, command)
        setattr(func, constants.CMD_ATTR_ARGPARSER, parser)
        setattr(func, constants.SUBCMD_ATTR_NAME, subcommand)

        # Keyword arguments for subparsers.add_parser()
        add_parser_kwargs: dict[str, Any] = {}
        if help is not None:
            add_parser_kwargs['help'] = help
        if aliases:
            add_parser_kwargs['aliases'] = aliases[:]

        setattr(func, constants.SUBCMD_ATTR_ADD_PARSER_KWARGS, add_parser_kwargs)

        return func

    return arg_decorator
