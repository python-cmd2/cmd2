# coding=utf-8
"""Decorators for ``cmd2`` commands"""
import argparse
import types
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

from . import constants
from .exceptions import Cmd2ArgparseError
from .parsing import Statement

if TYPE_CHECKING:  # pragma: no cover
    import cmd2


def with_category(category: str) -> Callable:
    """A decorator to apply a category to a ``do_*`` command method.

    :param category: the name of the category in which this command should
                     be grouped when displaying the list of commands.

    :Example:

    >>> class MyApp(cmd2.Cmd):
    >>>   @cmd2.with_category('Text Functions')
    >>>   def do_echo(self, args)
    >>>     self.poutput(args)

    For an alternative approach to categorizing commands using a function, see
    :func:`~cmd2.utils.categorize`
    """
    def cat_decorator(func):
        from .utils import categorize
        categorize(func, category)
        return func
    return cat_decorator

##########################
# The _parse_positionals and _swap_args decorators allow for additional positional args to be preserved
# in cmd2 command functions/callables. As long as the 2-ple of arguments we expect to be there can be
# found we can swap out the statement with each decorator's specific parameters
##########################


def _parse_positionals(args: Tuple) -> Tuple['cmd2.Cmd', Union[Statement, str]]:
    """
    Helper function for cmd2 decorators to inspect the positional arguments until the cmd2.Cmd argument is found
    Assumes that we will find cmd2.Cmd followed by the command statement object or string.
    :arg args: The positional arguments to inspect
    :return: The cmd2.Cmd reference and the command line statement
    """
    for pos, arg in enumerate(args):
        from cmd2 import Cmd
        if isinstance(arg, Cmd) and len(args) > pos:
            next_arg = args[pos + 1]
            if isinstance(next_arg, (Statement, str)):
                return arg, args[pos + 1]

    # This shouldn't happen unless we forget to pass statement in `Cmd.onecmd` or
    # somehow call the unbound class method.
    raise TypeError('Expected arguments: cmd: cmd2.Cmd, statement: Union[Statement, str] Not found')  # pragma: no cover


def _arg_swap(args: Union[Tuple[Any], List[Any]], search_arg: Any, *replace_arg: Any) -> List[Any]:
    """
    Helper function for cmd2 decorators to swap the Statement parameter with one or more decorator-specific parameters
    :param args: The original positional arguments
    :param search_arg: The argument to search for (usually the Statement)
    :param replace_arg: The arguments to substitute in
    :return: The new set of arguments to pass to the command function
    """
    index = args.index(search_arg)
    args_list = list(args)
    args_list[index:index + 1] = replace_arg
    return args_list


def with_argument_list(*args: List[Callable], preserve_quotes: bool = False) -> Callable[[List], Optional[bool]]:
    """
    A decorator to alter the arguments passed to a ``do_*`` method. Default
    passes a string of whatever the user typed. With this decorator, the
    decorated method will receive a list of arguments parsed from user input.

    :param args: Single-element positional argument list containing ``do_*`` method
                 this decorator is wrapping
    :param preserve_quotes: if ``True``, then argument quotes will not be stripped
    :return: function that gets passed a list of argument strings

    :Example:

    >>> class MyApp(cmd2.Cmd):
    >>>     @cmd2.with_argument_list
    >>>     def do_echo(self, arglist):
    >>>         self.poutput(' '.join(arglist)
    """
    import functools

    def arg_decorator(func: Callable):
        @functools.wraps(func)
        def cmd_wrapper(*args, **kwargs: Dict[str, Any]) -> Optional[bool]:
            """
            Command function wrapper which translates command line into an argument list and calls actual command function

            :param args: All positional arguments to this function.  We're expecting there to be:
                            cmd2_app, statement: Union[Statement, str]
                            contiguously somewhere in the list
            :param kwargs: any keyword arguments being passed to command function
            :return: return value of command function
            """
            cmd2_app, statement = _parse_positionals(args)
            _, parsed_arglist = cmd2_app.statement_parser.get_command_arg_list(command_name,
                                                                               statement,
                                                                               preserve_quotes)
            args_list = _arg_swap(args, statement, parsed_arglist)
            return func(*args_list, **kwargs)

        command_name = func.__name__[len(constants.COMMAND_FUNC_PREFIX):]
        cmd_wrapper.__doc__ = func.__doc__
        return cmd_wrapper

    if len(args) == 1 and callable(args[0]):
        # noinspection PyTypeChecker
        return arg_decorator(args[0])
    else:
        # noinspection PyTypeChecker
        return arg_decorator


# noinspection PyProtectedMember
def _set_parser_prog(parser: argparse.ArgumentParser, prog: str):
    """
    Recursively set prog attribute of a parser and all of its subparsers so that the root command
    is a command name and not sys.argv[0].

    :param parser: the parser being edited
    :param prog: new value for the parser's prog attribute
    """
    # Set the prog value for this parser
    parser.prog = prog

    # Set the prog value for the parser's subcommands
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            # Set the _SubParsersAction's _prog_prefix value. That way if its add_parser() method is called later,
            # the correct prog value will be set on the parser being added.
            action._prog_prefix = parser.prog

            # The keys of action.choices are subcommand names as well as subcommand aliases. The aliases point to the
            # same parser as the actual subcommand. We want to avoid placing an alias into a parser's prog value.
            # Unfortunately there is nothing about an action.choices entry which tells us it's an alias. In most cases
            # we can filter out the aliases by checking the contents of action._choices_actions. This list only contains
            # help information and names for the subcommands and not aliases. However, subcommands without help text
            # won't show up in that list. Since dictionaries are ordered in Python 3.6 and above and argparse inserts the
            # subcommand name into choices dictionary before aliases, we should be OK assuming the first time we see a
            # parser, the dictionary key is a subcommand and not alias.
            processed_parsers = []

            # Set the prog value for each subcommand's parser
            for subcmd_name, subcmd_parser in action.choices.items():
                # Check if we've already edited this parser
                if subcmd_parser in processed_parsers:
                    continue

                subcmd_prog = parser.prog + ' ' + subcmd_name
                _set_parser_prog(subcmd_parser, subcmd_prog)
                processed_parsers.append(subcmd_parser)

            # We can break since argparse only allows 1 group of subcommands per level
            break


def with_argparser_and_unknown_args(parser: argparse.ArgumentParser, *,
                                    ns_provider: Optional[Callable[..., argparse.Namespace]] = None,
                                    preserve_quotes: bool = False) -> \
        Callable[[argparse.Namespace, List], Optional[bool]]:
    """
    Deprecated decorator. Use `with_argparser(parser, with_unknown_args=True)` instead.

    A decorator to alter a cmd2 method to populate its ``args`` argument by parsing
    arguments with the given instance of argparse.ArgumentParser, but also returning
    unknown args as a list.

    :param parser: unique instance of ArgumentParser
    :param ns_provider: An optional function that accepts a cmd2.Cmd object as an argument
                        and returns an argparse.Namespace. This is useful if the Namespace
                        needs to be prepopulated with state data that affects parsing.
    :param preserve_quotes: if ``True``, then arguments passed to argparse maintain their quotes
    :return: function that gets passed argparse-parsed args in a ``Namespace`` and a list
             of unknown argument strings. A member called ``__statement__`` is added to the
             ``Namespace`` to provide command functions access to the :class:`cmd2.Statement`
             object. This can be useful if the command function needs to know the command line.

    :Example:

    >>> parser = argparse.ArgumentParser()
    >>> parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    >>> parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    >>> parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    >>>
    >>> class MyApp(cmd2.Cmd):
    >>>     @cmd2.with_argparser(parser, with_unknown_args=True)
    >>>     def do_argprint(self, args, unknown):
    >>>         "Print the options and argument list this options command was called with."
    >>>         self.poutput('args: {!r}'.format(args))
    >>>         self.poutput('unknowns: {}'.format(unknown))
    """
    import warnings
    warnings.warn('This decorator will be deprecated. Use `with_argparser(parser, with_unknown_args=True)`.',
                  PendingDeprecationWarning, stacklevel=2)

    return with_argparser(parser, ns_provider=ns_provider, preserve_quotes=preserve_quotes, with_unknown_args=True)


def with_argparser(parser: argparse.ArgumentParser, *,
                   ns_provider: Optional[Callable[..., argparse.Namespace]] = None,
                   preserve_quotes: bool = False,
                   with_unknown_args: bool = False) -> Callable[[argparse.Namespace], Optional[bool]]:
    """A decorator to alter a cmd2 method to populate its ``args`` argument by parsing arguments
    with the given instance of argparse.ArgumentParser.

    :param parser: unique instance of ArgumentParser
    :param ns_provider: An optional function that accepts a cmd2.Cmd object as an argument and returns an
                        argparse.Namespace. This is useful if the Namespace needs to be prepopulated with
                        state data that affects parsing.
    :param preserve_quotes: if True, then arguments passed to argparse maintain their quotes
    :param with_unknown_args: if true, then capture unknown args
    :return: function that gets passed the argparse-parsed args in a Namespace
             A member called __statement__ is added to the Namespace to provide command functions access to the
             Statement object. This can be useful if the command function needs to know the command line.

    :Example:

    >>> parser = argparse.ArgumentParser()
    >>> parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    >>> parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    >>> parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    >>> parser.add_argument('words', nargs='+', help='words to print')
    >>>
    >>> class MyApp(cmd2.Cmd):
    >>>     @cmd2.with_argparser(parser, preserve_quotes=True)
    >>>     def do_argprint(self, args):
    >>>         "Print the options and argument list this options command was called with."
    >>>         self.poutput('args: {!r}'.format(args))

    :Example with unknown args:

    >>> parser = argparse.ArgumentParser()
    >>> parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    >>> parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    >>> parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    >>>
    >>> class MyApp(cmd2.Cmd):
    >>>     @cmd2.with_argparser(parser, with_unknown_args=True)
    >>>     def do_argprint(self, args, unknown):
    >>>         "Print the options and argument list this options command was called with."
    >>>         self.poutput('args: {!r}'.format(args))
    >>>         self.poutput('unknowns: {}'.format(unknown))

    """
    import functools

    def arg_decorator(func: Callable):
        @functools.wraps(func)
        def cmd_wrapper(*args: Any, **kwargs: Dict[str, Any]) -> Optional[bool]:
            """
            Command function wrapper which translates command line into argparse Namespace and calls actual
            command function

            :param args: All positional arguments to this function.  We're expecting there to be:
                            cmd2_app, statement: Union[Statement, str]
                            contiguously somewhere in the list
            :param kwargs: any keyword arguments being passed to command function
            :return: return value of command function
            :raises: Cmd2ArgparseError if argparse has error parsing command line
            """
            cmd2_app, statement = _parse_positionals(args)
            statement, parsed_arglist = cmd2_app.statement_parser.get_command_arg_list(command_name,
                                                                                       statement,
                                                                                       preserve_quotes)

            if ns_provider is None:
                namespace = None
            else:
                namespace = ns_provider(cmd2_app)

            try:
                if with_unknown_args:
                    new_args = parser.parse_known_args(parsed_arglist, namespace)
                else:
                    new_args = (parser.parse_args(parsed_arglist, namespace), )
                ns = new_args[0]
            except SystemExit:
                raise Cmd2ArgparseError
            else:
                setattr(ns, '__statement__', statement)

                def get_handler(self: argparse.Namespace) -> Optional[Callable]:
                    return getattr(self, constants.SUBCMD_HANDLER, None)

                setattr(ns, 'get_handler', types.MethodType(get_handler, ns))

                args_list = _arg_swap(args, statement, *new_args)
                return func(*args_list, **kwargs)

        # argparser defaults the program name to sys.argv[0], but we want it to be the name of our command
        command_name = func.__name__[len(constants.COMMAND_FUNC_PREFIX):]
        _set_parser_prog(parser, command_name)

        # If the description has not been set, then use the method docstring if one exists
        if parser.description is None and func.__doc__:
            parser.description = func.__doc__

        # Set the command's help text as argparser.description (which can be None)
        cmd_wrapper.__doc__ = parser.description

        # Set some custom attributes for this command
        setattr(cmd_wrapper, constants.CMD_ATTR_ARGPARSER, parser)
        setattr(cmd_wrapper, constants.CMD_ATTR_PRESERVE_QUOTES, preserve_quotes)

        return cmd_wrapper

    # noinspection PyTypeChecker
    return arg_decorator


def as_subcommand_to(command: str,
                     subcommand: str,
                     parser: argparse.ArgumentParser,
                     *,
                     help_text: Optional[str] = None,
                     aliases: Iterable[str] = None) -> Callable[[argparse.Namespace], Optional[bool]]:
    """
    Tag this method as a subcommand to an existing argparse decorated command.

    :param command: Command Name. Space-delimited subcommands may optionally be specified
    :param subcommand: Subcommand name
    :param parser: argparse Parser for this subcommand
    :param help_text: Help message for this subcommand
    :param aliases: Alternative names for this subcommand
    :return: Wrapper function that can receive an argparse.Namespace
    """
    def arg_decorator(func: Callable):
        _set_parser_prog(parser, subcommand)

        # If the description has not been set, then use the method docstring if one exists
        if parser.description is None and func.__doc__:
            parser.description = func.__doc__

        parser.set_defaults(func=func)

        # Set some custom attributes for this command
        setattr(func, constants.SUBCMD_ATTR_COMMAND, command)
        setattr(func, constants.CMD_ATTR_ARGPARSER, parser)
        setattr(func, constants.SUBCMD_ATTR_NAME, subcommand)
        parser_args = {}
        if help_text is not None:
            parser_args['help'] = help_text
        if aliases is not None:
            parser_args['aliases'] = aliases[:]
        setattr(func, constants.SUBCMD_ATTR_PARSER_ARGS, parser_args)

        return func

    # noinspection PyTypeChecker
    return arg_decorator
