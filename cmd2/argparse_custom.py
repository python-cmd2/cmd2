# coding=utf-8
"""
This module adds capabilities to argparse by patching a few of its functions.
It also defines a parser class called Cmd2ArgumentParser which improves error
and help output over normal argparse. All cmd2 code uses this parser and it is
recommended that developers of cmd2-based apps either use it or write their own
parser that inherits from it. This will give a consistent look-and-feel between
the help/error output of built-in cmd2 commands and the app-specific commands.
If you wish to override the parser used by cmd2's built-in commands, see
override_parser.py example.

Since the new capabilities are added by patching at the argparse API level,
they are available whether or not Cmd2ArgumentParser is used. However, the help
and error output of Cmd2ArgumentParser is customized to notate nargs ranges
whereas any other parser class won't be as explicit in their output.


**Added capabilities**

Extends argparse nargs functionality by allowing tuples which specify a range
(min, max). To specify a max value with no upper bound, use a 1-item tuple
(min,)

Example::

    # -f argument expects at least 3 values
    parser.add_argument('-f', nargs=(3,))

    # -f argument expects 3 to 5 values
    parser.add_argument('-f', nargs=(3, 5))


**Tab Completion**

cmd2 uses its ArgparseCompleter class to enable argparse-based tab completion
on all commands that use the @with_argparse wrappers. Out of the box you get
tab completion of commands, subcommands, and flag names, as well as instructive
hints about the current argument that print when tab is pressed. In addition,
you can add tab completion for each argument's values using parameters passed
to add_argument().

Below are the 5 add_argument() parameters for enabling tab completion of an
argument's value. Only one can be used at a time.

``choices`` - pass a list of values to the choices parameter.

    Example::

        parser.add_argument('-o', '--options', choices=['An Option', 'SomeOtherOption'])
        parser.add_argument('-o', '--options', choices=my_list)

``choices_function`` - pass a function that returns choices. This is good in
cases where the choice list is dynamically generated when the user hits tab.

    Example::

        def my_choices_function():
            ...
            return my_generated_list

        parser.add_argument('-o', '--options', choices_function=my_choices_function)

``choices_method`` - this is equivalent to choices_function, but the function
needs to be an instance method of a cmd2.Cmd or cmd2.CommandSet subclass. When
ArgparseCompleter calls the method, it well detect whether is is bound to a
CommandSet or Cmd subclass.
If bound to a cmd2.Cmd subclass, it will pass the app instance as the `self`
argument. This is good in cases where the list of choices being generated
relies on state data of the cmd2-based app.
If bound to a cmd2.CommandSet subclass, it will pass the CommandSet instance
as the `self` argument.

    Example::

        def my_choices_method(self):
            ...
            return my_generated_list

        parser.add_argument("arg", choices_method=my_choices_method)


``completer_function`` - pass a tab completion function that does custom
completion. Since custom tab completion operations commonly need to modify
cmd2's instance variables related to tab completion, it will be rare to need a
completer function. completer_method should be used in those cases.

    Example::

        def my_completer_function(text, line, begidx, endidx):
            ...
            return completions
        parser.add_argument('-o', '--options', completer_function=my_completer_function)

``completer_method`` - this is equivalent to completer_function, but the function
needs to be an instance method of a cmd2.Cmd or cmd2.CommandSet subclass. When
ArgparseCompleter calls the method, it well detect whether is is bound to a
CommandSet or Cmd subclass.
If bound to a cmd2.Cmd subclass, it will pass the app instance as the `self`
argument. This is good in cases where the list of choices being generated
relies on state data of the cmd2-based app.
If bound to a cmd2.CommandSet subclass, it will pass the CommandSet instance
as the `self` argument, and the app instance as the positional argument.
cmd2 provides a few completer methods for convenience (e.g.,
path_complete, delimiter_complete)

    Example::

        # This adds file-path completion to an argument
        parser.add_argument('-o', '--options', completer_method=cmd2.Cmd.path_complete)


    You can use functools.partial() to prepopulate values of the underlying
    choices and completer functions/methods.

    Example::

        # This says to call path_complete with a preset value for its path_filter argument
        completer_method = functools.partial(path_complete,
                                             path_filter=lambda path: os.path.isdir(path))
        parser.add_argument('-o', '--options', choices_method=completer_method)

Of the 5 tab completion parameters, choices is the only one where argparse
validates user input against items in the choices list. This is because the
other 4 parameters are meant to tab complete data sets that are viewed as
dynamic. Therefore it is up to the developer to validate if the user has typed
an acceptable value for these arguments.

The following functions exist in cases where you may want to manually add a
choice-providing function/method to an existing argparse action. For instance,
in __init__() of a custom action class.

    - set_choices_function(action, func)
    - set_choices_method(action, method)
    - set_completer_function(action, func)
    - set_completer_method(action, method)

There are times when what's being tab completed is determined by a previous
argument on the command line. In theses cases, Autocompleter can pass a
dictionary that maps the command line tokens up through the one being completed
to their argparse argument name. To receive this dictionary, your
choices/completer function should have an argument called arg_tokens.

    Example::

        def my_choices_method(self, arg_tokens)
        def my_completer_method(self, text, line, begidx, endidx, arg_tokens)

All values of the arg_tokens dictionary are lists, even if a particular
argument expects only 1 token. Since ArgparseCompleter is for tab completion,
it does not convert the tokens to their actual argument types or validate their
values. All tokens are stored in the dictionary as the raw strings provided on
the command line. It is up to the developer to determine if the user entered
the correct argument type (e.g. int) and validate their values.

CompletionItem Class - This class was added to help in cases where
uninformative data is being tab completed. For instance, tab completing ID
numbers isn't very helpful to a user without context. Returning a list of
CompletionItems instead of a regular string for completion results will signal
the ArgparseCompleter to output the completion results in a table of completion
tokens with descriptions instead of just a table of tokens::

    Instead of this:
        1     2     3

    The user sees this:
        ITEM_ID     Item Name
        1           My item
        2           Another item
        3           Yet another item


The left-most column is the actual value being tab completed and its header is
that value's name. The right column header is defined using the
descriptive_header parameter of add_argument(). The right column values come
from the CompletionItem.description value.

Example::

    token = 1
    token_description = "My Item"
    completion_item = CompletionItem(token, token_description)

Since descriptive_header and CompletionItem.description are just strings, you
can format them in such a way to have multiple columns::

    ITEM_ID     Item Name            Checked Out    Due Date
    1           My item              True           02/02/2022
    2           Another item         False
    3           Yet another item     False

To use CompletionItems, just return them from your choices or completer
functions.

To avoid printing a ton of information to the screen at once when a user
presses tab, there is a maximum threshold for the number of CompletionItems
that will be shown. Its value is defined in cmd2.Cmd.max_completion_items. It
defaults to 50, but can be changed. If the number of completion suggestions
exceeds this number, they will be displayed in the typical columnized format
and will not include the description value of the CompletionItems.


**Patched argparse functions**

``argparse._ActionsContainer.add_argument`` - adds arguments related to tab
completion and enables nargs range parsing. See _add_argument_wrapper for
more details on these arguments.

``argparse.ArgumentParser._get_nargs_pattern`` - adds support for nargs ranges.
See _get_nargs_pattern_wrapper for more details.

``argparse.ArgumentParser._match_argument`` - adds support for nargs ranges.
See _match_argument_wrapper for more details.

``argparse._SubParsersAction.remove_parser`` - new function which removes a
sub-parser from a sub-parsers group. See _SubParsersAction_remove_parser for
more details.
"""

import argparse
import re
import sys
# noinspection PyUnresolvedReferences,PyProtectedMember
from argparse import (
    ONE_OR_MORE,
    ZERO_OR_MORE,
    ArgumentError,
    _,
)
from typing import (
    Any,
    Callable,
    Optional,
    Tuple,
    Type,
    Union,
)

from . import (
    ansi,
    constants,
)

############################################################################################################
# The following are names of custom argparse argument attributes added by cmd2
############################################################################################################

# A tuple specifying nargs as a range (min, max)
ATTR_NARGS_RANGE = 'nargs_range'

# ChoicesCallable object that specifies the function to be called which provides choices to the argument
ATTR_CHOICES_CALLABLE = 'choices_callable'

# Pressing tab normally displays the help text for the argument if no choices are available
# Setting this attribute to True will suppress these hints
ATTR_SUPPRESS_TAB_HINT = 'suppress_tab_hint'

# Descriptive header that prints when using CompletionItems
ATTR_DESCRIPTIVE_COMPLETION_HEADER = 'desc_completion_header'


def generate_range_error(range_min: int, range_max: Union[int, float]) -> str:
    """Generate an error message when the the number of arguments provided is not within the expected range"""
    err_str = "expected "

    if range_max == constants.INFINITY:
        err_str += "at least {} argument".format(range_min)

        if range_min != 1:
            err_str += "s"
    else:
        if range_min == range_max:
            err_str += "{} argument".format(range_min)
        else:
            err_str += "{} to {} argument".format(range_min, range_max)

        if range_max != 1:
            err_str += "s"

    return err_str


class CompletionItem(str):
    """
    Completion item with descriptive text attached

    See header of this file for more information
    """
    def __new__(cls, value: object, *args, **kwargs) -> str:
        return super().__new__(cls, value)

    # noinspection PyUnusedLocal
    def __init__(self, value: object, desc: str = '', *args, **kwargs) -> None:
        """
        CompletionItem Initializer

        :param value: the value being tab completed
        :param desc: description text to display
        :param args: args for str __init__
        :param kwargs: kwargs for str __init__
        """
        super().__init__(*args, **kwargs)
        self.description = desc


############################################################################################################
# Class and functions related to ChoicesCallable
############################################################################################################
class ChoicesCallable:
    """
    Enables using a callable as the choices provider for an argparse argument.
    While argparse has the built-in choices attribute, it is limited to an iterable.
    """
    def __init__(self, is_method: bool, is_completer: bool, to_call: Callable):
        """
        Initializer
        :param is_method: True if to_call is an instance method of a cmd2 app. False if it is a function.
        :param is_completer: True if to_call is a tab completion routine which expects
                             the args: text, line, begidx, endidx
        :param to_call: the callable object that will be called to provide choices for the argument
        """
        self.is_method = is_method
        self.is_completer = is_completer
        self.to_call = to_call


def _set_choices_callable(action: argparse.Action, choices_callable: ChoicesCallable) -> None:
    """
    Set the choices_callable attribute of an argparse Action
    :param action: action being edited
    :param choices_callable: the ChoicesCallable instance to use
    :raises: TypeError if used on incompatible action type
    """
    # Verify consistent use of parameters
    if action.choices is not None:
        err_msg = ("None of the following parameters can be used alongside a choices parameter:\n"
                   "choices_function, choices_method, completer_function, completer_method")
        raise (TypeError(err_msg))
    elif action.nargs == 0:
        err_msg = ("None of the following parameters can be used on an action that takes no arguments:\n"
                   "choices_function, choices_method, completer_function, completer_method")
        raise (TypeError(err_msg))

    setattr(action, ATTR_CHOICES_CALLABLE, choices_callable)


def set_choices_function(action: argparse.Action, choices_function: Callable) -> None:
    """Set choices_function on an argparse action"""
    _set_choices_callable(action, ChoicesCallable(is_method=False, is_completer=False, to_call=choices_function))


def set_choices_method(action: argparse.Action, choices_method: Callable) -> None:
    """Set choices_method on an argparse action"""
    _set_choices_callable(action, ChoicesCallable(is_method=True, is_completer=False, to_call=choices_method))


def set_completer_function(action: argparse.Action, completer_function: Callable) -> None:
    """Set completer_function on an argparse action"""
    _set_choices_callable(action, ChoicesCallable(is_method=False, is_completer=True, to_call=completer_function))


def set_completer_method(action: argparse.Action, completer_method: Callable) -> None:
    """Set completer_method on an argparse action"""
    _set_choices_callable(action, ChoicesCallable(is_method=True, is_completer=True, to_call=completer_method))


############################################################################################################
# Patch _ActionsContainer.add_argument with our wrapper to support more arguments
############################################################################################################

# Save original _ActionsContainer.add_argument so we can call it in our wrapper
# noinspection PyProtectedMember
orig_actions_container_add_argument = argparse._ActionsContainer.add_argument


def _add_argument_wrapper(self, *args,
                          nargs: Union[int, str, Tuple[int], Tuple[int, int], None] = None,
                          choices_function: Optional[Callable] = None,
                          choices_method: Optional[Callable] = None,
                          completer_function: Optional[Callable] = None,
                          completer_method: Optional[Callable] = None,
                          suppress_tab_hint: bool = False,
                          descriptive_header: Optional[str] = None,
                          **kwargs) -> argparse.Action:
    """
    Wrapper around _ActionsContainer.add_argument() which supports more settings used by cmd2

    # Args from original function
    :param self: instance of the _ActionsContainer being added to
    :param args: arguments expected by argparse._ActionsContainer.add_argument

    # Customized arguments from original function
    :param nargs: extends argparse nargs functionality by allowing tuples which specify a range (min, max)
                  to specify a max value with no upper bound, use a 1-item tuple (min,)

    # Added args used by ArgparseCompleter
    :param choices_function: function that provides choices for this argument
    :param choices_method: cmd2-app method that provides choices for this argument
    :param completer_function: tab completion function that provides choices for this argument
    :param completer_method: cmd2-app tab completion method that provides choices for this argument
    :param suppress_tab_hint: when ArgparseCompleter has no results to show during tab completion, it displays the
                              current argument's help text as a hint. Set this to True to suppress the hint. If this
                              argument's help text is set to argparse.SUPPRESS, then tab hints will not display
                              regardless of the value passed for suppress_tab_hint. Defaults to False.
    :param descriptive_header: if the provided choices are CompletionItems, then this header will display
                               during tab completion. Defaults to None.

    # Args from original function
    :param kwargs: keyword-arguments recognized by argparse._ActionsContainer.add_argument

    Note: You can only use 1 of the following in your argument:
          choices, choices_function, choices_method, completer_function, completer_method

          See the header of this file for more information

    :return: the created argument action
    :raises: ValueError on incorrect parameter usage
    """
    # Verify consistent use of arguments
    choices_callables = [choices_function, choices_method, completer_function, completer_method]
    num_params_set = len(choices_callables) - choices_callables.count(None)

    if num_params_set > 1:
        err_msg = ("Only one of the following parameters may be used at a time:\n"
                   "choices_function, choices_method, completer_function, completer_method")
        raise (ValueError(err_msg))

    # Pre-process special ranged nargs
    nargs_range = None

    if nargs is not None:
        # Check if nargs was given as a range
        if isinstance(nargs, tuple):

            # Handle 1-item tuple by setting max to INFINITY
            if len(nargs) == 1:
                nargs = (nargs[0], constants.INFINITY)

            # Validate nargs tuple
            if len(nargs) != 2 or not isinstance(nargs[0], int) or \
                    not (isinstance(nargs[1], int) or nargs[1] == constants.INFINITY):
                raise ValueError('Ranged values for nargs must be a tuple of 1 or 2 integers')
            if nargs[0] >= nargs[1]:
                raise ValueError('Invalid nargs range. The first value must be less than the second')
            if nargs[0] < 0:
                raise ValueError('Negative numbers are invalid for nargs range')

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
        kwargs['nargs'] = nargs_adjusted

    # Create the argument using the original add_argument function
    new_arg = orig_actions_container_add_argument(self, *args, **kwargs)

    # Set the custom attributes
    setattr(new_arg, ATTR_NARGS_RANGE, nargs_range)

    if choices_function:
        set_choices_function(new_arg, choices_function)
    elif choices_method:
        set_choices_method(new_arg, choices_method)
    elif completer_function:
        set_completer_function(new_arg, completer_function)
    elif completer_method:
        set_completer_method(new_arg, completer_method)

    setattr(new_arg, ATTR_SUPPRESS_TAB_HINT, suppress_tab_hint)
    setattr(new_arg, ATTR_DESCRIPTIVE_COMPLETION_HEADER, descriptive_header)

    return new_arg


# Overwrite _ActionsContainer.add_argument with our wrapper
# noinspection PyProtectedMember
argparse._ActionsContainer.add_argument = _add_argument_wrapper

############################################################################################################
# Patch ArgumentParser._get_nargs_pattern with our wrapper to nargs ranges
############################################################################################################

# Save original ArgumentParser._get_nargs_pattern so we can call it in our wrapper
# noinspection PyProtectedMember
orig_argument_parser_get_nargs_pattern = argparse.ArgumentParser._get_nargs_pattern


# noinspection PyProtectedMember
def _get_nargs_pattern_wrapper(self, action) -> str:
    # Wrapper around ArgumentParser._get_nargs_pattern behavior to support nargs ranges
    nargs_range = getattr(action, ATTR_NARGS_RANGE, None)
    if nargs_range is not None:
        if nargs_range[1] == constants.INFINITY:
            range_max = ''
        else:
            range_max = nargs_range[1]

        nargs_pattern = '(-*A{{{},{}}}-*)'.format(nargs_range[0], range_max)

        # if this is an optional action, -- is not allowed
        if action.option_strings:
            nargs_pattern = nargs_pattern.replace('-*', '')
            nargs_pattern = nargs_pattern.replace('-', '')
        return nargs_pattern

    return orig_argument_parser_get_nargs_pattern(self, action)


# Overwrite ArgumentParser._get_nargs_pattern with our wrapper
# noinspection PyProtectedMember
argparse.ArgumentParser._get_nargs_pattern = _get_nargs_pattern_wrapper


############################################################################################################
# Patch ArgumentParser._match_argument with our wrapper to nargs ranges
############################################################################################################
# noinspection PyProtectedMember
orig_argument_parser_match_argument = argparse.ArgumentParser._match_argument


# noinspection PyProtectedMember
def _match_argument_wrapper(self, action, arg_strings_pattern) -> int:
    # Wrapper around ArgumentParser._match_argument behavior to support nargs ranges
    nargs_pattern = self._get_nargs_pattern(action)
    match = re.match(nargs_pattern, arg_strings_pattern)

    # raise an exception if we weren't able to find a match
    if match is None:
        nargs_range = getattr(action, ATTR_NARGS_RANGE, None)
        if nargs_range is not None:
            raise ArgumentError(action, generate_range_error(nargs_range[0], nargs_range[1]))

    return orig_argument_parser_match_argument(self, action, arg_strings_pattern)


# Overwrite ArgumentParser._match_argument with our wrapper
# noinspection PyProtectedMember
argparse.ArgumentParser._match_argument = _match_argument_wrapper


############################################################################################################
# Patch argparse._SubParsersAction to add remove_parser function
############################################################################################################

# noinspection PyPep8Naming
def _SubParsersAction_remove_parser(self, name: str):
    """
    Removes a sub-parser from a sub-parsers group

    This is a custom method being added to the argparse._SubParsersAction
    class so cmd2 can remove subcommands from a parser.

    :param self: instance of the _SubParsersAction being edited
    :param name: name of the subcommand for the sub-parser to remove
    """
    # Remove this subcommand from its base command's help text
    for choice_action in self._choices_actions:
        if choice_action.dest == name:
            self._choices_actions.remove(choice_action)
            break

    # Remove this subcommand and all its aliases from the base command
    subparser = self._name_parser_map.get(name)
    if subparser is not None:
        to_remove = []
        for cur_name, cur_parser in self._name_parser_map.items():
            if cur_parser is subparser:
                to_remove.append(cur_name)
        for cur_name in to_remove:
            del self._name_parser_map[cur_name]


# noinspection PyProtectedMember
setattr(argparse._SubParsersAction, 'remove_parser', _SubParsersAction_remove_parser)


############################################################################################################
# Unless otherwise noted, everything below this point are copied from Python's
# argparse implementation with minor tweaks to adjust output.
# Changes are noted if it's buried in a block of copied code. Otherwise the
# function will check for a special case and fall back to the parent function
############################################################################################################


# noinspection PyCompatibility,PyShadowingBuiltins
class Cmd2HelpFormatter(argparse.RawTextHelpFormatter):
    """Custom help formatter to configure ordering of help text"""

    def _format_usage(self, usage, actions, groups, prefix) -> str:
        if prefix is None:
            prefix = _('Usage: ')

        # if usage is specified, use that
        if usage is not None:
            usage %= dict(prog=self._prog)

        # if no optionals or positionals are available, usage is just prog
        elif usage is None and not actions:
            usage = '%(prog)s' % dict(prog=self._prog)

        # if optionals and positionals are available, calculate usage
        elif usage is None:
            prog = '%(prog)s' % dict(prog=self._prog)

            # split optionals from positionals
            optionals = []
            positionals = []
            # Begin cmd2 customization (separates required and optional, applies to all changes in this function)
            required_options = []
            for action in actions:
                if action.option_strings:
                    if action.required:
                        required_options.append(action)
                    else:
                        optionals.append(action)
                else:
                    positionals.append(action)
            # End cmd2 customization

            # build full usage string
            format = self._format_actions_usage
            action_usage = format(required_options + optionals + positionals, groups)
            usage = ' '.join([s for s in [prog, action_usage] if s])

            # wrap the usage parts if it's too long
            text_width = self._width - self._current_indent
            if len(prefix) + len(usage) > text_width:

                # Begin cmd2 customization

                # break usage into wrappable parts
                part_regexp = r'\(.*?\)+|\[.*?\]+|\S+'
                req_usage = format(required_options, groups)
                opt_usage = format(optionals, groups)
                pos_usage = format(positionals, groups)
                req_parts = re.findall(part_regexp, req_usage)
                opt_parts = re.findall(part_regexp, opt_usage)
                pos_parts = re.findall(part_regexp, pos_usage)
                assert ' '.join(req_parts) == req_usage
                assert ' '.join(opt_parts) == opt_usage
                assert ' '.join(pos_parts) == pos_usage

                # End cmd2 customization

                # helper for wrapping lines
                # noinspection PyMissingOrEmptyDocstring,PyShadowingNames
                def get_lines(parts, indent, prefix=None):
                    lines = []
                    line = []
                    if prefix is not None:
                        line_len = len(prefix) - 1
                    else:
                        line_len = len(indent) - 1
                    for part in parts:
                        if line_len + 1 + len(part) > text_width and line:
                            lines.append(indent + ' '.join(line))
                            line = []
                            line_len = len(indent) - 1
                        line.append(part)
                        line_len += len(part) + 1
                    if line:
                        lines.append(indent + ' '.join(line))
                    if prefix is not None:
                        lines[0] = lines[0][len(indent):]
                    return lines

                # if prog is short, follow it with optionals or positionals
                if len(prefix) + len(prog) <= 0.75 * text_width:
                    indent = ' ' * (len(prefix) + len(prog) + 1)
                    # Begin cmd2 customization
                    if req_parts:
                        lines = get_lines([prog] + req_parts, indent, prefix)
                        lines.extend(get_lines(opt_parts, indent))
                        lines.extend(get_lines(pos_parts, indent))
                    elif opt_parts:
                        lines = get_lines([prog] + opt_parts, indent, prefix)
                        lines.extend(get_lines(pos_parts, indent))
                    elif pos_parts:
                        lines = get_lines([prog] + pos_parts, indent, prefix)
                    else:
                        lines = [prog]
                    # End cmd2 customization

                # if prog is long, put it on its own line
                else:
                    indent = ' ' * len(prefix)
                    # Begin cmd2 customization
                    parts = req_parts + opt_parts + pos_parts
                    lines = get_lines(parts, indent)
                    if len(lines) > 1:
                        lines = []
                        lines.extend(get_lines(req_parts, indent))
                        lines.extend(get_lines(opt_parts, indent))
                        lines.extend(get_lines(pos_parts, indent))
                    # End cmd2 customization
                    lines = [prog] + lines

                # join lines into usage
                usage = '\n'.join(lines)

        # prefix with 'Usage:'
        return '%s%s\n\n' % (prefix, usage)

    def _format_action_invocation(self, action) -> str:
        if not action.option_strings:
            default = self._get_default_metavar_for_positional(action)
            metavar, = self._metavar_formatter(action, default)(1)
            return metavar

        else:
            parts = []

            # if the Optional doesn't take a value, format is:
            #    -s, --long
            if action.nargs == 0:
                parts.extend(action.option_strings)
                return ', '.join(parts)

            # Begin cmd2 customization (less verbose)
            # if the Optional takes a value, format is:
            #    -s, --long ARGS
            else:
                default = self._get_default_metavar_for_optional(action)
                args_string = self._format_args(action, default)

                return ', '.join(action.option_strings) + ' ' + args_string
            # End cmd2 customization

    # noinspection PyMethodMayBeStatic
    def _determine_metavar(self, action, default_metavar) -> Union[str, Tuple]:
        """Custom method to determine what to use as the metavar value of an action"""
        if action.metavar is not None:
            result = action.metavar
        elif action.choices is not None:
            choice_strs = [str(choice) for choice in action.choices]
            # Begin cmd2 customization (added space after comma)
            result = '{%s}' % ', '.join(choice_strs)
            # End cmd2 customization
        else:
            result = default_metavar
        return result

    def _metavar_formatter(self, action, default_metavar) -> Callable:
        metavar = self._determine_metavar(action, default_metavar)

        # noinspection PyMissingOrEmptyDocstring
        def format(tuple_size):
            if isinstance(metavar, tuple):
                return metavar
            else:
                return (metavar, ) * tuple_size
        return format

    # noinspection PyProtectedMember
    def _format_args(self, action, default_metavar) -> str:
        """Customized to handle ranged nargs and make other output less verbose"""
        metavar = self._determine_metavar(action, default_metavar)
        metavar_formatter = self._metavar_formatter(action, default_metavar)

        # Handle nargs specified as a range
        nargs_range = getattr(action, ATTR_NARGS_RANGE, None)
        if nargs_range is not None:
            if nargs_range[1] == constants.INFINITY:
                range_str = '{}+'.format(nargs_range[0])
            else:
                range_str = '{}..{}'.format(nargs_range[0], nargs_range[1])

            return '{}{{{}}}'.format('%s' % metavar_formatter(1), range_str)

        # Make this output less verbose. Do not customize the output when metavar is a
        # tuple of strings. Allow argparse's formatter to handle that instead.
        elif isinstance(metavar, str):
            if action.nargs == ZERO_OR_MORE:
                return '[%s [...]]' % metavar_formatter(1)
            elif action.nargs == ONE_OR_MORE:
                return '%s [...]' % metavar_formatter(1)
            elif isinstance(action.nargs, int) and action.nargs > 1:
                return '{}{{{}}}'.format('%s' % metavar_formatter(1), action.nargs)

        return super()._format_args(action, default_metavar)


# noinspection PyCompatibility
class Cmd2ArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser class that improves error and help output"""

    def __init__(self,
                 prog=None,
                 usage=None,
                 description=None,
                 epilog=None,
                 parents=None,
                 formatter_class=Cmd2HelpFormatter,
                 prefix_chars='-',
                 fromfile_prefix_chars=None,
                 argument_default=None,
                 conflict_handler='error',
                 add_help=True,
                 allow_abbrev=True) -> None:
        super(Cmd2ArgumentParser, self).__init__(
            prog=prog,
            usage=usage,
            description=description,
            epilog=epilog,
            parents=parents if parents else [],
            formatter_class=formatter_class,
            prefix_chars=prefix_chars,
            fromfile_prefix_chars=fromfile_prefix_chars,
            argument_default=argument_default,
            conflict_handler=conflict_handler,
            add_help=add_help,
            allow_abbrev=allow_abbrev)

    def add_subparsers(self, **kwargs):
        """
        Custom override. Sets a default title if one was not given.

        :param kwargs: additional keyword arguments
        :return: argparse Subparser Action
        """
        if 'title' not in kwargs:
            kwargs['title'] = 'subcommands'

        return super().add_subparsers(**kwargs)

    def error(self, message: str) -> None:
        """Custom override that applies custom formatting to the error message"""
        lines = message.split('\n')
        linum = 0
        formatted_message = ''
        for line in lines:
            if linum == 0:
                formatted_message = 'Error: ' + line
            else:
                formatted_message += '\n       ' + line
            linum += 1

        self.print_usage(sys.stderr)
        formatted_message = ansi.style_error(formatted_message)
        self.exit(2, '{}\n\n'.format(formatted_message))

    # noinspection PyProtectedMember
    def format_help(self) -> str:
        """Copy of format_help() from argparse.ArgumentParser with tweaks to separately display required parameters"""
        formatter = self._get_formatter()

        # usage
        formatter.add_usage(self.usage, self._actions,
                            self._mutually_exclusive_groups)

        # description
        formatter.add_text(self.description)

        # Begin cmd2 customization (separate required and optional arguments)

        # positionals, optionals and user-defined groups
        for action_group in self._action_groups:
            if action_group.title == 'optional arguments':
                # check if the arguments are required, group accordingly
                req_args = []
                opt_args = []
                for action in action_group._group_actions:
                    if action.required:
                        req_args.append(action)
                    else:
                        opt_args.append(action)

                # separately display required arguments
                formatter.start_section('required arguments')
                formatter.add_text(action_group.description)
                formatter.add_arguments(req_args)
                formatter.end_section()

                # now display truly optional arguments
                formatter.start_section(action_group.title)
                formatter.add_text(action_group.description)
                formatter.add_arguments(opt_args)
                formatter.end_section()
            else:
                formatter.start_section(action_group.title)
                formatter.add_text(action_group.description)
                formatter.add_arguments(action_group._group_actions)
                formatter.end_section()

        # End cmd2 customization

        # epilog
        formatter.add_text(self.epilog)

        # determine help from format above
        return formatter.format_help() + '\n'

    def _print_message(self, message, file=None):
        # Override _print_message to use style_aware_write() since we use ANSI escape characters to support color
        if message:
            if file is None:
                file = sys.stderr
            ansi.style_aware_write(file, message)


class Cmd2AttributeWrapper:
    """
    Wraps a cmd2-specific attribute added to an argparse Namespace.
    This makes it easy to know which attributes in a Namespace are
    arguments from a parser and which were added by cmd2.
    """
    def __init__(self, attribute: Any):
        self.__attribute = attribute

    def get(self) -> Any:
        """Get the value of the attribute"""
        return self.__attribute

    def set(self, new_val: Any) -> None:
        """Set the value of the attribute"""
        self.__attribute = new_val


# The default ArgumentParser class for a cmd2 app
DEFAULT_ARGUMENT_PARSER = Cmd2ArgumentParser


def set_default_argument_parser(parser: Type[argparse.ArgumentParser]) -> None:
    """Set the default ArgumentParser class for a cmd2 app"""
    global DEFAULT_ARGUMENT_PARSER
    DEFAULT_ARGUMENT_PARSER = parser
