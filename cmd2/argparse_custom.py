# coding=utf-8
import argparse
import re as _re
import sys
# noinspection PyUnresolvedReferences,PyProtectedMember
from argparse import ZERO_OR_MORE, ONE_OR_MORE, ArgumentError, _
from typing import Any, Callable, Iterable, List, Optional, Tuple, Union

from .ansi import ansi_aware_write, style_error

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


############################################################################################################
# Patch _ActionsContainer.add_argument with our wrapper to support more arguments
############################################################################################################

# Save original _ActionsContainer.add_argument so we can call it in our wrapper
# noinspection PyProtectedMember
orig_actions_container_add_argument = argparse._ActionsContainer.add_argument


def _add_argument_wrapper(self, *args,
                          nargs: Union[int, str, Tuple[int, int], None] = None,
                          choices_function: Optional[Callable[[], Iterable[Any]]] = None,
                          choices_method: Optional[Callable[[Any], Iterable[Any]]] = None,
                          completer_function: Optional[Callable[[str, str, int, int], List[str]]] = None,
                          completer_method: Optional[Callable[[Any, str, str, int, int], List[str]]] = None,
                          suppress_hint: bool = False,
                          descriptive_header: Optional[str] = None,
                          **kwargs) -> argparse.Action:
    """
    Wrapper around _ActionsContainer.add_argument() which supports more settings used by cmd2

    # Args from original function
    :param self: instance of the _ActionsContainer being added to
    :param args: arguments expected by argparse._ActionsContainer.add_argument

    # Customized arguments from original function
    :param nargs: extends argparse nargs functionality by allowing tuples which specify a range (min, max)

    # Added args used by AutoCompleter
    :param choices_function: function that provides choices for this argument
    :param choices_method: cmd2-app method that provides choices for this argument
    :param completer_function: tab-completion function that provides choices for this argument
    :param completer_method: cmd2-app tab-completion method that provides choices for this argument
    :param suppress_hint: when AutoCompleter has no choices to show during tab completion, it displays the current
                          argument's help text as a hint. Set this to True to suppress the hint. Defaults to False.
    :param descriptive_header: if the provided choices are CompletionItems, then this header will display
                               during tab completion. Defaults to None.

    # Args from original function
    :param kwargs: keyword-arguments recognized by argparse._ActionsContainer.add_argument

    Note: You can only use 1 of the following in your argument:
          choices, choices_function, choices_method, completer_function, completer_method

          See the header of this file for more information

    :return: the created argument action
    """
    # Pre-process special ranged nargs
    nargs_range = None

    if nargs is not None:
        # Check if nargs was given as a range
        if isinstance(nargs, tuple):

            # Validate nargs tuple
            if len(nargs) != 2 or not isinstance(nargs[0], int) or not isinstance(nargs[1], int):
                raise ValueError('Ranged values for nargs must be a tuple of 2 integers')
            if nargs[0] >= nargs[1]:
                raise ValueError('Invalid nargs range. The first value must be less than the second')
            if nargs[0] < 0:
                raise ValueError('Negative numbers are invalid for nargs range')

            # Save the nargs tuple as our range setting
            nargs_range = nargs

            # Convert nargs into a format argparse recognizes
            if nargs_range[0] == 0:
                if nargs_range[1] > 1:
                    nargs_adjusted = argparse.ZERO_OR_MORE
                else:
                    nargs_adjusted = argparse.OPTIONAL
            else:
                nargs_adjusted = argparse.ONE_OR_MORE
        else:
            nargs_adjusted = nargs

        # Add the argparse-recognized version of nargs to kwargs
        kwargs['nargs'] = nargs_adjusted

    # Create the argument using the original add_argument function
    new_arg = orig_actions_container_add_argument(self, *args, **kwargs)

    # Verify consistent use of arguments
    choice_params = [new_arg.choices, choices_function, choices_method, completer_function, completer_method]
    num_set = len(choice_params) - choice_params.count(None)

    if num_set > 1:
        err_msg = ("Only one of the following may be used in an argparser argument at a time:\n"
                   "choices, choices_function, choices_method, completer_function, completer_method")
        raise (ValueError(err_msg))

    # Set the custom attributes
    setattr(new_arg, ATTR_NARGS_RANGE, nargs_range)

    if choices_function:
        setattr(new_arg, ATTR_CHOICES_CALLABLE,
                ChoicesCallable(is_method=False, is_completer=False, to_call=choices_function))
    elif choices_method:
        setattr(new_arg, ATTR_CHOICES_CALLABLE,
                ChoicesCallable(is_method=True, is_completer=False, to_call=choices_method))
    elif completer_function:
        setattr(new_arg, ATTR_CHOICES_CALLABLE,
                ChoicesCallable(is_method=False, is_completer=True, to_call=completer_function))
    elif completer_method:
        setattr(new_arg, ATTR_CHOICES_CALLABLE,
                ChoicesCallable(is_method=True, is_completer=True, to_call=completer_method))

    setattr(new_arg, ATTR_SUPPRESS_TAB_HINT, suppress_hint)
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
        nargs_pattern = '(-*A{{{},{}}}-*)'.format(nargs_range[0], nargs_range[1])

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
    match = _re.match(nargs_pattern, arg_strings_pattern)

    # raise an exception if we weren't able to find a match
    if match is None:
        nargs_range = getattr(action, ATTR_NARGS_RANGE, None)
        if nargs_range is not None:
            raise ArgumentError(action,
                                'Expected between {} and {} arguments'.format(nargs_range[0], nargs_range[1]))

    return orig_argument_parser_match_argument(self, action, arg_strings_pattern)


# Overwrite ArgumentParser._match_argument with our wrapper
# noinspection PyProtectedMember
argparse.ArgumentParser._match_argument = _match_argument_wrapper

############################################################################################################
# Unless otherwise noted, everything below this point are copied from Python's
# argparse implementation with minor tweaks to adjust output.
# Changes are noted if it's buried in a block of copied code. Otherwise the
# function will check for a special case and fall back to the parent function
############################################################################################################


# noinspection PyCompatibility,PyShadowingBuiltins,PyShadowingBuiltins
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
                req_parts = _re.findall(part_regexp, req_usage)
                opt_parts = _re.findall(part_regexp, opt_usage)
                pos_parts = _re.findall(part_regexp, pos_usage)
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

    def _metavar_formatter(self, action, default_metavar) -> Callable:
        if action.metavar is not None:
            result = action.metavar
        elif action.choices is not None:
            choice_strs = [str(choice) for choice in action.choices]
            # Begin cmd2 customization (added space after comma)
            result = '{%s}' % ', '.join(choice_strs)
            # End cmd2 customization
        else:
            result = default_metavar

        # noinspection PyMissingOrEmptyDocstring
        def format(tuple_size):
            if isinstance(result, tuple):
                return result
            else:
                return (result, ) * tuple_size
        return format

    # noinspection PyProtectedMember
    def _format_args(self, action, default_metavar) -> str:
        get_metavar = self._metavar_formatter(action, default_metavar)
        # Begin cmd2 customization (less verbose)
        nargs_range = getattr(action, ATTR_NARGS_RANGE, None)

        if nargs_range is not None:
            result = '{}{{{}..{}}}'.format('%s' % get_metavar(1), nargs_range[0], nargs_range[1])
        elif action.nargs == ZERO_OR_MORE:
            result = '[%s [...]]' % get_metavar(1)
        elif action.nargs == ONE_OR_MORE:
            result = '%s [...]' % get_metavar(1)
        # End cmd2 customization
        else:
            result = super()._format_args(action, default_metavar)
        return result


# noinspection PyCompatibility
class Cmd2ArgParser(argparse.ArgumentParser):
    """Custom ArgumentParser class that improves error and help output"""

    def __init__(self, *args, **kwargs) -> None:
        if 'formatter_class' not in kwargs:
            kwargs['formatter_class'] = Cmd2HelpFormatter

        super().__init__(*args, **kwargs)

    def add_subparsers(self, **kwargs):
        """Custom override. Sets a default title if one was not given."""
        if 'title' not in kwargs:
            kwargs['title'] = 'sub-commands'

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
        formatted_message = style_error(formatted_message)
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
        # Override _print_message to use ansi_aware_write() since we use ANSI escape characters to support color
        if message:
            if file is None:
                file = sys.stderr
            ansi_aware_write(file, message)
