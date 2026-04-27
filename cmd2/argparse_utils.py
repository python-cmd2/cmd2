"""Module adds capabilities to argparse by patching a few of its functions.

It also defines a parser class called Cmd2ArgumentParser which improves error
and help output over normal argparse. All cmd2 code uses this parser and it is
required that developers of cmd2-based apps either use it or write their own
parser that inherits from it. If you wish to override the parser used by cmd2's
built-in commands, see custom_parser.py example.


**Added capabilities**

Extends argparse nargs functionality by allowing tuples which specify a range
(min, max). To specify a max value with no upper bound, use a 1-item tuple
(min,)

Example::

    # -f argument expects at least 3 values
    parser.add_argument('-f', nargs=(3,))

    # -f argument expects 3 to 5 values
    parser.add_argument('-f', nargs=(3, 5))


**Completion**

cmd2 uses its ArgparseCompleter class to enable argparse-based completion
on all commands that use the @with_argparser decorator. Out of the box you get
completion of commands, subcommands, and flag names, as well as instructive
hints about the current argument that print when tab is pressed. In addition,
you can add completion for each argument's values using parameters passed
to add_argument().

Below are the 3 add_argument() parameters for enabling completion of an
argument's value. Only one can be used at a time.

``choices`` - pass a list of values to the choices parameter.

    Example::

        my_list = ['An Option', 'SomeOtherOption']
        parser.add_argument('-o', '--options', choices=my_list)

``choices_provider`` - pass a function that returns a Choices object. This is good in
cases where the choices are dynamically generated when the user hits tab.

    Example::

        def my_choices_provider(self) -> Choices:
            ...
            return my_choices

        parser.add_argument("arg", choices_provider=my_choices_provider)

``completer`` - pass a function that does custom completion and returns a Completions object.

cmd2 provides a few completer methods for convenience (e.g., path_complete,
delimiter_complete)

    Example::

        # This adds file-path completion to an argument
        parser.add_argument('-o', '--options', completer=cmd2.Cmd.path_complete)

    You can use functools.partial() to prepopulate values of the underlying
    choices and completer functions/methods.

    Example::

        # This says to call path_complete with a preset value for its path_filter argument
        dir_completer = functools.partial(path_complete,
                                          path_filter=lambda path: os.path.isdir(path))
        parser.add_argument('-o', '--options', completer=dir_completer)

For ``choices_provider`` and ``completer``, do not set them to a bound method. This
is because ArgparseCompleter passes the `self` argument explicitly to these
functions. When ArgparseCompleter calls one, it will detect whether it is bound
to a `Cmd` subclass or `CommandSet`. If bound to a `cmd2.Cmd subclass`, it will
pass the app instance as the `self` argument. If bound to a `cmd2.CommandSet`
subclass, it will pass the `CommandSet` instance as the `self` argument.
Therefore instead of passing something like `self.path_complete`, pass
`cmd2.Cmd.path_complete`.

``choices_provider`` and ``completer`` functions can also be implemented as
standalone functions (i.e. not a member of a class). In this case,
ArgparseCompleter will pass its ``cmd2.Cmd`` app instance as the first
positional argument.

Of the 3 completion parameters, ``choices`` is the only one where argparse
validates user input against items in the choices list. This is because the
other 2 parameters are meant to complete data sets that are viewed as
dynamic. Therefore it is up to the developer to validate if the user has typed
an acceptable value for these arguments.

There are times when what's being completed is determined by a previous
argument on the command line. In these cases, ArgparseCompleter can pass a
dictionary that maps the command line tokens up through the one being completed
to their argparse argument name. To receive this dictionary, your
choices/completer function should have an argument called arg_tokens.

    Example::

        def my_choices_provider(self, arg_tokens) -> Choices
        def my_completer(self, text, line, begidx, endidx, arg_tokens) -> Completions

All values of the arg_tokens dictionary are lists, even if a particular
argument expects only 1 token. Since ArgparseCompleter is for completion,
it does not convert the tokens to their actual argument types or validate their
values. All tokens are stored in the dictionary as the raw strings provided on
the command line. It is up to the developer to determine if the user entered
the correct argument type (e.g. int) and validate their values.

**CompletionItem Class**

This class represents a single completion result and what the ``Choices``
and ``Completion`` classes contain.

``CompletionItem`` provides the following optional metadata fields which enhance
completion results displayed to the screen.

1. display - string for displaying the completion differently in the completion menu
2. display_meta - meta information about completion which displays in the completion menu
3. table_data - supplemental data for completion tables

They can also be used as argparse choices. When a ``CompletionItem`` is created, it
stores the original value (e.g. ID number) and makes it accessible through a property
called ``value``. cmd2 has patched argparse so that when evaluating choices, input
is compared to ``CompletionItem.value`` instead of the ``CompletionItem`` instance.

**Completion Tables**

These were added to help in cases where uninformative data is being completed.
For instance, completing ID numbers isn't very helpful to a user without context.

Providing ``table_data`` in your ``CompletionItem`` signals ArgparseCompleter
to output the completion results in a table with supplemental data instead of just a table
of tokens::

    Instead of this:
        1     2     3

    The user sees this:
         ITEM_ID   Description
        ────────────────────────────
               1   My item
               2   Another item
               3   Yet another item


The left-most column is the actual value being completed and its header is
that value's name. Any additional column headers are defined using the
``table_columns`` parameter of add_argument(), which is a list of header
names. The supplemental column values come from the
``table_data`` argument to ``CompletionItem``. It's a ``Sequence`` with the
same number of items as ``table_columns``.

Example::

    Add an argument and define its table_columns.

        parser.add_argument(
            "item_id",
            type=int,
            choices_provider=get_choices,
            table_columns=["Item Name", "Checked Out", "Due Date"],
        )

    Implement the choices_provider to return Choices.

        def get_choices(self) -> Choices:
            \"\"\"choices_provider which returns CompletionItems\"\"\"

            # Populate CompletionItem's table_data argument.
            # Its item count should match that of table_columns.
            items = [
                CompletionItem(1, table_data=["My item", True, "02/02/2022"]),
                CompletionItem(2, table_data=["Another item", False, ""]),
                CompletionItem(3, table_data=["Yet another item", False, ""]),
            ]
            return Choices(items)

    This is what the user will see during completion.

        ITEM_ID   Item Name          Checked Out   Due Date
        ───────────────────────────────────────────────────────
              1   My item            True          02/02/2022
              2   Another item       False
              3   Yet another item   False

``table_columns`` can be strings or ``Rich.table.Columns`` for more
control over things like alignment.

- If a header is a string, it will render as a left-aligned column with its
overflow behavior set to "fold". This means a long string will wrap within its
cell, creating as many new lines as required to fit.

- If a header is a ``Column``, it defaults to "ellipsis" overflow behavior.
This means a long string which exceeds the width of its column will be
truncated with an ellipsis at the end. You can override this and other settings
when you create the ``Column``.

``table_data`` items can include Rich objects, including styled Text and Tables.

To avoid printing excessive information to the screen at once when a user
presses tab, there is a maximum threshold for the number of ``CompletionItems``
that will be shown. Its value is defined in ``cmd2.Cmd.max_completion_table_items``.
It defaults to 50, but can be changed. If the number of completion suggestions
exceeds this number, then a completion table won't be displayed.


**Custom Argument Parameters**

``argparse._ActionsContainer.add_argument`` has been patched to support several
custom parameters used for tab completion and nargs range parsing. These
parameters are registered using ``register_argparse_argument_parameter()``.
See ``_ActionsContainer_add_argument`` for more details on these parameters.

Registering a parameter whitelists it for use in ``add_argument()`` and
automatically adds getter and setter accessor methods to the ``argparse.Action``
class. For any registered parameter named ``<name>``, the following methods are
available on the resulting ``Action`` object to access its underlying attribute:

- ``action.get_<name>()``
- ``action.set_<name>(value)``
"""

import argparse
import re
import sys
import threading
from argparse import ArgumentError
from collections.abc import (
    Callable,
    Iterable,
    Sequence,
)
from dataclasses import dataclass
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    ClassVar,
    NoReturn,
    cast,
)

from rich.console import RenderableType
from rich.table import Column

from . import constants
from .completion import CompletionItem
from .rich_utils import Cmd2HelpFormatter
from .styles import Cmd2Style
from .types import (
    CmdOrSetT,
    UnboundChoicesProvider,
    UnboundCompleter,
)

if TYPE_CHECKING:  # pragma: no cover
    from .argparse_completer import ArgparseCompleter


def build_range_error(range_min: int, range_max: float) -> str:
    """Build an error message when the the number of arguments provided is not within the expected range."""
    err_msg = "expected "

    if range_max == constants.INFINITY:
        plural = "" if range_min == 1 else "s"
        err_msg += f"at least {range_min}"
    else:
        plural = "" if range_max == 1 else "s"
        if range_min == range_max:
            err_msg += f"{range_min}"
        else:
            err_msg += f"{range_min} to {range_max}"

    err_msg += f" argument{plural}"

    return err_msg


############################################################################################################
# Allow developers to add custom action attributes
############################################################################################################

# This set should only be edited by calling register_argparse_argument_parameter().
# Do not manually add or remove items.
_CUSTOM_ACTION_ATTRIBS: set[str] = set()


def register_argparse_argument_parameter(
    param_name: str,
    *,
    validator: Callable[[argparse.Action, Any], Any] | None = None,
) -> None:
    """Register a custom parameter for argparse.Action and add accessors to the Action class.

    :param param_name: Name of the parameter. This must be a valid Python identifier.
    :param validator: Optional function to validate and/or transform the parameter value.
                      It accepts the Action instance and the value as arguments.
    :raises ValueError: if the parameter name is invalid
    :raises KeyError: if the new parameter collides with any existing attributes
    """
    if not param_name.isidentifier():
        raise ValueError(f"Invalid parameter name '{param_name}': must be a valid Python identifier")

    if param_name in _CUSTOM_ACTION_ATTRIBS:
        raise KeyError(f"Custom parameter '{param_name}' is already registered")

    # Ensure we don't hijack standard argparse.Action attributes or existing methods
    if hasattr(argparse.Action, param_name):
        raise KeyError(f"'{param_name}' conflicts with an existing attribute on argparse.Action")

    # Check if accessors already exist (e.g., from manual patching or previous registration)
    getter_name = f"get_{param_name}"
    setter_name = f"set_{param_name}"
    if hasattr(argparse.Action, getter_name) or hasattr(argparse.Action, setter_name):
        raise KeyError(f"Accessor methods for '{param_name}' already exist on argparse.Action")

    # Check for the prefixed internal attribute name collision (e.g., _cmd2_<param_name>)
    attr_name = constants.cmd2_private_attr_name(param_name)
    if hasattr(argparse.Action, attr_name):
        raise KeyError(f"The internal attribute '{attr_name}' already exists on argparse.Action")

    def _action_get_custom_parameter(self: argparse.Action) -> Any:
        """Get the custom attribute of an argparse Action."""
        return getattr(self, attr_name, None)

    setattr(argparse.Action, getter_name, _action_get_custom_parameter)

    def _action_set_custom_parameter(self: argparse.Action, value: Any) -> None:
        """Set the custom attribute of an argparse Action."""
        if validator is not None:
            value = validator(self, value)

        setattr(self, attr_name, value)

    setattr(argparse.Action, setter_name, _action_set_custom_parameter)

    _CUSTOM_ACTION_ATTRIBS.add(param_name)


def _validate_completion_callable(self: argparse.Action, value: Any) -> Any:
    """Validate choices_provider and completer values for potential conflicts."""
    if value is None:
        return None

    if self.choices is not None:
        err_msg = "None of the following parameters can be used alongside a choices parameter:\nchoices_provider, completer"
        raise ValueError(err_msg)
    if self.nargs == 0:
        err_msg = (
            "None of the following parameters can be used on an action that takes no arguments:\nchoices_provider, completer"
        )
        raise ValueError(err_msg)
    return value


# Add new attributes to argparse.Action.
# See _ActionsContainer_add_argument() for details on these attributes.
register_argparse_argument_parameter("choices_provider", validator=_validate_completion_callable)
register_argparse_argument_parameter("completer", validator=_validate_completion_callable)
register_argparse_argument_parameter("table_columns")
register_argparse_argument_parameter("nargs_range")
register_argparse_argument_parameter("suppress_tab_hint")


############################################################################################################
# Patch _ActionsContainer.add_argument to support more arguments
############################################################################################################

# Save original _ActionsContainer.add_argument so we can call it in our patch
orig_actions_container_add_argument = argparse._ActionsContainer.add_argument


def _ActionsContainer_add_argument(  # noqa: N802
    self: argparse._ActionsContainer,
    *args: Any,
    nargs: int | str | tuple[int] | tuple[int, int] | tuple[int, float] | None = None,
    choices_provider: UnboundChoicesProvider[CmdOrSetT] | None = None,
    completer: UnboundCompleter[CmdOrSetT] | None = None,
    suppress_tab_hint: bool = False,
    table_columns: Sequence[str | Column] | None = None,
    **kwargs: Any,
) -> argparse.Action:
    """Patch _ActionsContainer.add_argument() to support cmd2-specific settings.

    # Args from original function
    :param self: instance of the _ActionsContainer being added to
    :param args: arguments expected by argparse._ActionsContainer.add_argument

    # Customized arguments from original function
    :param nargs: extends argparse nargs functionality by allowing tuples which specify a range (min, max)
                  to specify a max value with no upper bound, use a 1-item tuple (min,)

    # Added args used by ArgparseCompleter
    :param choices_provider: function that provides choices for this argument
    :param completer: completion function that provides choices for this argument
    :param suppress_tab_hint: when ArgparseCompleter has no results to show during completion, it displays the
                              current argument's help text as a hint. Set this to True to suppress the hint. If this
                              argument's help text is set to argparse.SUPPRESS, then tab hints will not display
                              regardless of the value passed for suppress_tab_hint. Defaults to False.
    :param table_columns: optional headers for when displaying a completion table. Defaults to None.

    # Args from original function
    :param kwargs: keyword-arguments recognized by argparse._ActionsContainer.add_argument

    Note: You can only use 1 of the following in your argument:
          choices, choices_provider, completer

          See the header of this file for more information

    :return: the created argument action
    :raises ValueError: on incorrect parameter usage
    """
    # Verify consistent use of arguments
    if choices_provider is not None and completer is not None:
        raise ValueError("Only one of the following parameters may be used at a time:\nchoices_provider, completer")

    # Pre-process special ranged nargs
    nargs_range = None

    if nargs is not None:
        nargs_adjusted: int | str | tuple[int] | tuple[int, int] | tuple[int, float] | None
        # Check if nargs was given as a range
        if isinstance(nargs, tuple):
            # Handle 1-item tuple by setting max to INFINITY
            if len(nargs) == 1:
                nargs = (nargs[0], constants.INFINITY)

            # Validate nargs tuple
            if (
                len(nargs) != 2
                or not isinstance(nargs[0], int)
                or not (isinstance(nargs[1], int) or nargs[1] == constants.INFINITY)
            ):
                raise ValueError("Ranged values for nargs must be a tuple of 1 or 2 integers")
            if nargs[0] >= nargs[1]:
                raise ValueError("Invalid nargs range. The first value must be less than the second")
            if nargs[0] < 0:
                raise ValueError("Negative numbers are invalid for nargs range")

            # Save the nargs tuple as our range setting
            nargs_range = nargs
            range_min = nargs_range[0]
            range_max = nargs_range[1]

            # Convert nargs into a format argparse recognizes
            if range_min == 0:
                if range_max == 1:
                    nargs_adjusted = argparse.OPTIONAL

                    # No range needed since (0, 1) is just argparse.OPTIONAL
                    nargs_range = None
                else:
                    nargs_adjusted = argparse.ZERO_OR_MORE
                    if range_max == constants.INFINITY:
                        # No range needed since (0, INFINITY) is just argparse.ZERO_OR_MORE
                        nargs_range = None
            elif range_min == 1 and range_max == constants.INFINITY:
                nargs_adjusted = argparse.ONE_OR_MORE

                # No range needed since (1, INFINITY) is just argparse.ONE_OR_MORE
                nargs_range = None
            else:
                nargs_adjusted = argparse.ONE_OR_MORE
        else:
            nargs_adjusted = nargs

        # Add the argparse-recognized version of nargs to kwargs
        kwargs["nargs"] = nargs_adjusted

    # Extract registered custom keyword arguments
    custom_attribs = {keyword: value for keyword, value in kwargs.items() if keyword in _CUSTOM_ACTION_ATTRIBS}
    for keyword in custom_attribs:
        del kwargs[keyword]

    # Create the argument using the original add_argument function
    new_arg = orig_actions_container_add_argument(self, *args, **kwargs)

    # Set the cmd2-specific attributes
    new_arg.set_nargs_range(nargs_range)  # type: ignore[attr-defined]
    new_arg.set_choices_provider(choices_provider)  # type: ignore[attr-defined]
    new_arg.set_completer(completer)  # type: ignore[attr-defined]
    new_arg.set_suppress_tab_hint(suppress_tab_hint)  # type: ignore[attr-defined]
    new_arg.set_table_columns(table_columns)  # type: ignore[attr-defined]

    # Set other registered custom attributes
    for keyword, value in custom_attribs.items():
        attr_setter = getattr(new_arg, f"set_{keyword}", None)
        if attr_setter is not None:
            attr_setter(value)

    return new_arg


# Overwrite _ActionsContainer.add_argument with our patch
argparse._ActionsContainer.add_argument = _ActionsContainer_add_argument  # type: ignore[method-assign]

############################################################################################################
# Patch argparse._SubParsersAction by adding remove_parser() function
############################################################################################################


def _SubParsersAction_remove_parser(  # noqa: N802
    self: argparse._SubParsersAction,  # type: ignore[type-arg]
    name: str,
) -> argparse.ArgumentParser:
    """Remove a subparser from a subparsers group.

    This function is added by cmd2 as a method called ``remove_parser()``
    to ``argparse._SubParsersAction`` class.

    To call: ``action.remove_parser(name)``

    :param self: instance of the _SubParsersAction being edited
    :param name: name of the subcommand for the subparser to remove
    :return: the removed parser
    :raises ValueError: if the subcommand doesn't exist
    """
    if name not in self._name_parser_map:
        raise ValueError(f"Subcommand '{name}' does not exist")

    subparser = self._name_parser_map[name]

    # Find all names (primary and aliases) that map to this subparser
    all_names = [cur_name for cur_name, cur_parser in self._name_parser_map.items() if cur_parser is subparser]

    # Remove the help entry for this subparser. To handle the case where
    # name is an alias, we remove the action whose 'dest' matches any of
    # the names mapped to this subparser.
    for choice_action in self._choices_actions:
        if choice_action.dest in all_names:
            self._choices_actions.remove(choice_action)
            break

    # Remove all references to this subparser, including aliases.
    for cur_name in all_names:
        del self._name_parser_map[cur_name]

    return cast(argparse.ArgumentParser, subparser)


argparse._SubParsersAction.remove_parser = _SubParsersAction_remove_parser  # type: ignore[attr-defined]


@dataclass
class _ParserThreadLocals(threading.local):
    """Thread-local storage used by Cmd2ArgumentParser to manage execution context."""

    # If set, this stream will be used by print_help() and print_usage()
    # instead of defaulting to sys.stdout.
    custom_stdout: IO[str] | None = None


class Cmd2ArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser class that improves error and help output."""

    # Thread-local storage shared by all parser instances (including subparsers)
    _thread_locals: ClassVar[_ParserThreadLocals] = _ParserThreadLocals()

    def __init__(
        self,
        prog: str | None = None,
        usage: str | None = None,
        description: RenderableType | None = None,
        epilog: RenderableType | None = None,
        parents: Sequence[argparse.ArgumentParser] = (),
        formatter_class: type[Cmd2HelpFormatter] = Cmd2HelpFormatter,
        prefix_chars: str = "-",
        fromfile_prefix_chars: str | None = None,
        argument_default: str | None = None,
        conflict_handler: str = "error",
        add_help: bool = True,
        allow_abbrev: bool = True,
        exit_on_error: bool = True,
        suggest_on_error: bool = False,
        color: bool = False,
        *,
        ap_completer_type: type["ArgparseCompleter"] | None = None,
    ) -> None:
        """Initialize the Cmd2ArgumentParser instance.

        :param ap_completer_type: optional parameter which specifies a subclass of ArgparseCompleter for custom completion
                                  behavior on this parser. If this is None or not present, then cmd2 will use
                                  argparse_completer.DEFAULT_AP_COMPLETER when completing this parser's arguments
        """
        kwargs: dict[str, bool] = {}
        if sys.version_info >= (3, 14):
            # Python >= 3.14 so pass new arguments to parent argparse.ArgumentParser class
            kwargs = {
                "suggest_on_error": suggest_on_error,
                "color": color,
            }

        super().__init__(
            prog=prog,
            usage=usage,
            description=description,  # type: ignore[arg-type]
            epilog=epilog,  # type: ignore[arg-type]
            parents=parents or [],
            formatter_class=formatter_class,
            prefix_chars=prefix_chars,
            fromfile_prefix_chars=fromfile_prefix_chars,
            argument_default=argument_default,
            conflict_handler=conflict_handler,
            add_help=add_help,
            allow_abbrev=allow_abbrev,
            exit_on_error=exit_on_error,
            **kwargs,
        )

        self.ap_completer_type = ap_completer_type

        # To assist type checkers, recast these to reflect our usage of rich-argparse.
        self.formatter_class: type[Cmd2HelpFormatter]
        self.description: RenderableType | None  # type: ignore[assignment]
        self.epilog: RenderableType | None  # type: ignore[assignment]

    def parse_args_custom_stdout(
        self,
        stdout: IO[str],
        args: list[str] | None = None,
        namespace: argparse.Namespace | None = None,
    ) -> argparse.Namespace:
        """Parse arguments while directing help and usage output to a custom stdout stream.

        This method is particularly useful when you need to capture help output without
        globally redirecting sys.stdout.

        :param stdout: the stream to use for help and usage output
        :param args: optional list of arguments to parse. If None, uses sys.argv[1:].
        :param namespace: optional namespace to populate. If None, a new Namespace is created.
        :return: the parsed namespace
        """
        previous = self._thread_locals.custom_stdout
        try:
            self._thread_locals.custom_stdout = stdout
            return self.parse_args(args, namespace)
        finally:
            self._thread_locals.custom_stdout = previous

    def parse_known_args_custom_stdout(
        self,
        stdout: IO[str],
        args: list[str] | None = None,
        namespace: argparse.Namespace | None = None,
    ) -> tuple[argparse.Namespace, list[str]]:
        """Parse known arguments while directing help and usage output to a custom stdout stream.

        This method is particularly useful when you need to capture help output without
        globally redirecting sys.stdout.

        :param stdout: the stream to use for help and usage output
        :param args: optional list of arguments to parse. If None, uses sys.argv[1:].
        :param namespace: optional namespace to populate. If None, a new Namespace is created.
        :return: a tuple containing the parsed namespace and a list of unknown arguments
        """
        previous = self._thread_locals.custom_stdout
        try:
            self._thread_locals.custom_stdout = stdout
            return self.parse_known_args(args, namespace)
        finally:
            self._thread_locals.custom_stdout = previous

    def print_usage(self, file: IO[str] | None = None) -> None:  # type:ignore[override]
        """Override to support writing to a custom stream."""
        if file is None:
            file = self._thread_locals.custom_stdout
        super().print_usage(file)

    def print_help(self, file: IO[str] | None = None) -> None:  # type:ignore[override]
        """Override to support writing to a custom stream."""
        if file is None:
            file = self._thread_locals.custom_stdout
        super().print_help(file)

    def get_subparsers_action(self) -> "argparse._SubParsersAction[Cmd2ArgumentParser]":
        """Get the _SubParsersAction for this parser if it exists.

        :return: the _SubParsersAction for this parser
        :raises ValueError: if this parser does not support subcommands
        """
        if self._subparsers is not None:
            for action in self._subparsers._group_actions:
                if isinstance(action, argparse._SubParsersAction):
                    return action
        raise ValueError(f"Command '{self.prog}' does not support subcommands")

    def _build_subparsers_prog_prefix(self, positionals: list[argparse.Action]) -> str:
        """Build the 'prog' prefix for a subparsers action.

        This prefix is stored in the _SubParsersAction's '_prog_prefix' attribute and
        is used to construct the 'prog' attribute for its child parsers. It
        typically consists of the current parser's 'prog' name followed by any
        positional arguments that appear before the _SubParsersAction.

        This method uses a temporary Cmd2ArgumentParser to leverage argparse's
        functionality for generating these strings. Subclasses can override this if
        they need to change how subcommand 'prog' values are constructed (e.g., if
        add_subparsers() was overridden with custom naming logic or if a different
        formatting style is desired).

        Note: This method explicitly instantiates Cmd2ArgumentParser rather than
        type(self) to avoid potential side effects or mandatory constructor
        arguments in user-defined subclasses.

        :param positionals: positional arguments which appear before the _SubParsersAction
        :return: the built 'prog' prefix
        """
        # 1. usage=None: In Python < 3.14, this prevents the default usage
        #    string from affecting subparser prog strings. This was fixed in 3.14:
        #    https://github.com/python/cpython/commit/0cb4d6c6549d2299f7518f083bbe7d10314ecd66
        #
        # 2. add_help=False: No need for a help action since we already know which
        #    actions are needed to build the prefix and have passed them in
        #    via the 'positionals' argument.
        temp_parser = Cmd2ArgumentParser(
            prog=self.prog,
            usage=None,
            formatter_class=self.formatter_class,
            add_help=False,
        )

        # Inject the current positional state so add_subparsers() has the right context
        temp_parser._actions = positionals
        temp_parser._mutually_exclusive_groups = self._mutually_exclusive_groups

        # Call add_subparsers() to build _prog_prefix
        return temp_parser.add_subparsers()._prog_prefix

    def update_prog(self, prog: str) -> None:
        """Recursively update the prog attribute of this parser and all of its subparsers.

        :param prog: new value for this parser's prog attribute
        """
        # Set the prog value for this parser
        self.prog = prog

        try:
            subparsers_action = self.get_subparsers_action()
        except ValueError:
            # This parser has no subcommands
            return

        # Get all positional arguments which appear before the subcommand.
        positionals: list[argparse.Action] = []
        for action in self._actions:
            if action is subparsers_action:
                break

            # Save positional argument
            if not action.option_strings:
                positionals.append(action)

        # Update _prog_prefix. This ensures that any subcommands added later via
        # add_parser() will have the correct prog value.
        subparsers_action._prog_prefix = self._build_subparsers_prog_prefix(positionals)

        # subparsers_action._name_parser_map includes aliases. Since primary names are inserted
        # first, we skip already updated parsers to ensure primary names are used in 'prog'.
        # We can't rely on subparsers_action._choices_actions to filter out aliases because while
        # it contains only primary names, it omits any subcommands that lack help text.
        updated_parsers: set[Cmd2ArgumentParser] = set()

        # Set the prog value for each subcommand's parser
        for subcmd_name, subcmd_parser in subparsers_action._name_parser_map.items():
            if subcmd_parser in updated_parsers:
                continue

            subcmd_prog = f"{subparsers_action._prog_prefix} {subcmd_name}"
            subcmd_parser.update_prog(subcmd_prog)
            updated_parsers.add(subcmd_parser)

    def find_parser(self, subcommand_path: Iterable[str]) -> "Cmd2ArgumentParser":
        """Find a parser in the hierarchy based on a sequence of subcommand names.

        :param subcommand_path: sequence of subcommand names leading to the target parser
        :return: the discovered parser
        :raises ValueError: if any subcommand in the path is not found or a level doesn't support subcommands
        """
        parser = self
        for name in subcommand_path:
            subparsers_action = parser.get_subparsers_action()
            if name not in subparsers_action._name_parser_map:
                raise ValueError(f"Subcommand '{name}' does not exist for '{parser.prog}'")
            parser = subparsers_action._name_parser_map[name]
        return parser

    def attach_subcommand(
        self,
        subcommand_path: Iterable[str],
        subcommand: str,
        subcommand_parser: "Cmd2ArgumentParser",
        **add_parser_kwargs: Any,
    ) -> None:
        """Attach a parser as a subcommand to a command at the specified path.

        :param subcommand_path: sequence of subcommand names leading to the parser that will
                                host the new subcommand. An empty sequence indicates this parser.
        :param subcommand: name of the new subcommand
        :param subcommand_parser: the parser to attach
        :param add_parser_kwargs: additional arguments for the subparser registration (e.g. help, aliases)
        :raises TypeError: if subcommand_parser is not an instance of the following or their subclasses:
                           1. Cmd2ArgumentParser
                           2. The parser_class configured for the target subcommand group
        :raises ValueError: if the command path is invalid, doesn't support subcommands, or the
                            subcommand already exists
        """
        if not isinstance(subcommand_parser, Cmd2ArgumentParser):
            raise TypeError(
                f"The attached parser must be an instance of 'Cmd2ArgumentParser' (or a subclass). "
                f"Received: '{type(subcommand_parser).__name__}'."
            )

        target_parser = self.find_parser(subcommand_path)
        subparsers_action = target_parser.get_subparsers_action()

        # Verify the parser is compatible with the 'parser_class' configured for this
        # subcommand group. We use isinstance() here to allow for subclasses, providing
        # more flexibility than the standard add_parser() factory approach which enforces
        # a specific class.
        if not isinstance(subcommand_parser, subparsers_action._parser_class):
            raise TypeError(
                f"The attached parser must be an instance of '{subparsers_action._parser_class.__name__}' "
                f"(or a subclass) to match the 'parser_class' configured for this subcommand group. "
                f"Received: '{type(subcommand_parser).__name__}'."
            )

        # Do not overwrite existing subcommands or aliases
        all_names = (subcommand, *add_parser_kwargs.get("aliases", ()))
        for name in all_names:
            if name in subparsers_action._name_parser_map:
                raise ValueError(f"Subcommand '{name}' already exists for '{target_parser.prog}'")

        # Use add_parser to register the subcommand name and any aliases
        placeholder_parser = subparsers_action.add_parser(subcommand, **add_parser_kwargs)

        # To ensure accurate usage strings, recursively update 'prog' values
        # within the injected parser to match its new location in the command hierarchy.
        subcommand_parser.update_prog(placeholder_parser.prog)

        # Replace the parser created by add_parser() with our pre-configured one
        subparsers_action._name_parser_map[subcommand] = subcommand_parser

        # Remap any aliases to our pre-configured parser
        for alias in add_parser_kwargs.get("aliases", ()):
            subparsers_action._name_parser_map[alias] = subcommand_parser

    def detach_subcommand(self, subcommand_path: Iterable[str], subcommand: str) -> "Cmd2ArgumentParser":
        """Detach a subcommand from a command at the specified path.

        :param subcommand_path: sequence of subcommand names leading to the parser hosting the
                                subcommand to be detached. An empty sequence indicates this parser.
        :param subcommand: name of the subcommand to detach
        :return: the detached parser
        :raises ValueError: if the command path is invalid or the subcommand doesn't exist
        """
        target_parser = self.find_parser(subcommand_path)
        subparsers_action = target_parser.get_subparsers_action()

        try:
            return cast(
                Cmd2ArgumentParser,
                subparsers_action.remove_parser(subcommand),  # type: ignore[attr-defined]
            )
        except ValueError:
            raise ValueError(f"Subcommand '{subcommand}' does not exist for '{target_parser.prog}'") from None

    def error(self, message: str) -> NoReturn:
        """Override that applies custom formatting to the error message."""
        lines = message.split("\n")
        formatted_message = ""
        for linum, line in enumerate(lines):
            if linum == 0:
                formatted_message = "Error: " + line
            else:
                formatted_message += "\n       " + line

        self.print_usage(sys.stderr)

        # Use console to add style since it will respect ALLOW_STYLE's value
        console = self._get_formatter().console
        with console.capture() as capture:
            console.print(formatted_message, style=Cmd2Style.ERROR)
        formatted_message = f"{capture.get()}"

        self.exit(2, f"{formatted_message}\n")

    def _get_formatter(self, **kwargs: Any) -> Cmd2HelpFormatter:
        """Override with customizations for Cmd2HelpFormatter."""
        return cast(Cmd2HelpFormatter, super()._get_formatter(**kwargs))

    def format_help(self) -> str:
        """Override to add a newline."""
        return super().format_help() + "\n"

    def _get_nargs_pattern(self, action: argparse.Action) -> str:
        """Override to support nargs ranges."""
        nargs_range = action.get_nargs_range()  # type: ignore[attr-defined]
        if nargs_range:
            range_max = "" if nargs_range[1] == constants.INFINITY else nargs_range[1]
            nargs_pattern = f"(-*A{{{nargs_range[0]},{range_max}}}-*)"

            # if this is an optional action, -- is not allowed
            if action.option_strings:
                nargs_pattern = nargs_pattern.replace("-*", "")
                nargs_pattern = nargs_pattern.replace("-", "")
            return nargs_pattern

        return super()._get_nargs_pattern(action)

    def _match_argument(self, action: argparse.Action, arg_strings_pattern: str) -> int:
        """Override to support nargs ranges."""
        nargs_pattern = self._get_nargs_pattern(action)
        match = re.match(nargs_pattern, arg_strings_pattern)

        # raise an exception if we weren't able to find a match
        if match is None:
            nargs_range = action.get_nargs_range()  # type: ignore[attr-defined]
            if nargs_range is not None:
                raise ArgumentError(action, build_range_error(nargs_range[0], nargs_range[1]))

        return super()._match_argument(action, arg_strings_pattern)

    def _check_value(self, action: argparse.Action, value: Any) -> None:
        """Override that supports CompletionItems as choices.

        When displaying choices, use CompletionItem.value instead of the CompletionItem instance.

        :param action: the action being populated
        :param value: value from command line already run through conversion function by argparse
        """
        # Import gettext like argparse does
        from gettext import (
            gettext as _,
        )

        if action.choices is not None and value not in action.choices:
            # If any choice is a CompletionItem, then display its value property.
            choices = [c.value if isinstance(c, CompletionItem) else c for c in action.choices]
            args = {"value": value, "choices": ", ".join(map(repr, choices))}
            msg = _("invalid choice: %(value)r (choose from %(choices)s)")
            raise ArgumentError(action, msg % args)


# Parser type used by cmd2's built-in commands.
# Set it using cmd2.set_default_argument_parser_type().
DEFAULT_ARGUMENT_PARSER: type[Cmd2ArgumentParser] = Cmd2ArgumentParser


def set_default_argument_parser_type(parser_type: type[Cmd2ArgumentParser]) -> None:
    """Set the default Cmd2ArgumentParser class for cmd2's built-in commands.

    Since built-in commands rely on customizations made in Cmd2ArgumentParser,
    your custom parser class should inherit from Cmd2ArgumentParser.

    This should be called prior to instantiating your CLI object.

    See examples/custom_parser.py.
    """
    global DEFAULT_ARGUMENT_PARSER  # noqa: PLW0603
    DEFAULT_ARGUMENT_PARSER = parser_type
