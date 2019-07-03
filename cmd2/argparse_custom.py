# coding=utf-8
import argparse
import re as _re
import sys

from argparse import ZERO_OR_MORE, ONE_OR_MORE, ArgumentError, _
from typing import Callable, Tuple, Union

from .ansi import ansi_aware_write, style_error


class _RangeAction(object):
    def __init__(self, nargs: Union[int, str, Tuple[int, int], None]) -> None:
        self.nargs_min = None
        self.nargs_max = None

        # pre-process special ranged nargs
        if isinstance(nargs, tuple):
            if len(nargs) != 2 or not isinstance(nargs[0], int) or not isinstance(nargs[1], int):
                raise ValueError('Ranged values for nargs must be a tuple of 2 integers')
            if nargs[0] >= nargs[1]:
                raise ValueError('Invalid nargs range. The first value must be less than the second')
            if nargs[0] < 0:
                raise ValueError('Negative numbers are invalid for nargs range.')
            narg_range = nargs
            self.nargs_min = nargs[0]
            self.nargs_max = nargs[1]
            if narg_range[0] == 0:
                if narg_range[1] > 1:
                    self.nargs_adjusted = '*'
                else:
                    # this shouldn't use a range tuple, but yet here we are
                    self.nargs_adjusted = '?'
            else:
                self.nargs_adjusted = '+'
        else:
            self.nargs_adjusted = nargs


# noinspection PyShadowingBuiltins,PyShadowingBuiltins
class _StoreRangeAction(argparse._StoreAction, _RangeAction):
    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=None,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None) -> None:

        _RangeAction.__init__(self, nargs)

        argparse._StoreAction.__init__(self,
                                       option_strings=option_strings,
                                       dest=dest,
                                       nargs=self.nargs_adjusted,
                                       const=const,
                                       default=default,
                                       type=type,
                                       choices=choices,
                                       required=required,
                                       help=help,
                                       metavar=metavar)


# noinspection PyShadowingBuiltins,PyShadowingBuiltins
class _AppendRangeAction(argparse._AppendAction, _RangeAction):
    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=None,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None) -> None:

        _RangeAction.__init__(self, nargs)

        argparse._AppendAction.__init__(self,
                                        option_strings=option_strings,
                                        dest=dest,
                                        nargs=self.nargs_adjusted,
                                        const=const,
                                        default=default,
                                        type=type,
                                        choices=choices,
                                        required=required,
                                        help=help,
                                        metavar=metavar)


def register_custom_actions(parser: argparse.ArgumentParser) -> None:
    """Register custom argument action types"""
    parser.register('action', None, _StoreRangeAction)
    parser.register('action', 'store', _StoreRangeAction)
    parser.register('action', 'append', _AppendRangeAction)


###############################################################################
# Unless otherwise noted, everything below this point are copied from Python's
# argparse implementation with minor tweaks to adjust output.
# Changes are noted if it's buried in a block of copied code. Otherwise the
# function will check for a special case and fall back to the parent function
###############################################################################


# noinspection PyCompatibility,PyShadowingBuiltins,PyShadowingBuiltins
class ACHelpFormatter(argparse.RawTextHelpFormatter):
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

    def _format_args(self, action, default_metavar) -> str:
        get_metavar = self._metavar_formatter(action, default_metavar)
        # Begin cmd2 customization (less verbose)
        if isinstance(action, _RangeAction) and \
                action.nargs_min is not None and action.nargs_max is not None:
            result = '{}{{{}..{}}}'.format('%s' % get_metavar(1), action.nargs_min, action.nargs_max)
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
    """Custom argparse class to override error method to change default help text."""

    def __init__(self, *args, **kwargs) -> None:
        if 'formatter_class' not in kwargs:
            kwargs['formatter_class'] = ACHelpFormatter

        super().__init__(*args, **kwargs)
        register_custom_actions(self)

        self._custom_error_message = ''

    # Begin cmd2 customization
    def set_custom_message(self, custom_message: str = '') -> None:
        """
        Allows an error message override to the error() function, useful when forcing a
        re-parse of arguments with newly required parameters
        """
        self._custom_error_message = custom_message
    # End cmd2 customization

    def add_subparsers(self, **kwargs):
        """Custom override. Sets a default title if one was not given."""
        if 'title' not in kwargs:
            kwargs['title'] = 'sub-commands'

        return super().add_subparsers(**kwargs)

    def error(self, message: str) -> None:
        """Custom override that applies custom formatting to the error message"""
        if self._custom_error_message:
            message = self._custom_error_message
            self._custom_error_message = ''

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

    def _get_nargs_pattern(self, action) -> str:
        # Override _get_nargs_pattern behavior to use the nargs ranges provided by AutoCompleter
        if isinstance(action, _RangeAction) and \
                action.nargs_min is not None and action.nargs_max is not None:
            nargs_pattern = '(-*A{{{},{}}}-*)'.format(action.nargs_min, action.nargs_max)

            # if this is an optional action, -- is not allowed
            if action.option_strings:
                nargs_pattern = nargs_pattern.replace('-*', '')
                nargs_pattern = nargs_pattern.replace('-', '')
            return nargs_pattern

        return super()._get_nargs_pattern(action)

    def _match_argument(self, action, arg_strings_pattern) -> int:
        # Override _match_argument behavior to use the nargs ranges provided by AutoCompleter
        nargs_pattern = self._get_nargs_pattern(action)
        match = _re.match(nargs_pattern, arg_strings_pattern)

        # raise an exception if we weren't able to find a match
        if match is None:
            if isinstance(action, _RangeAction) and \
                    action.nargs_min is not None and action.nargs_max is not None:
                raise ArgumentError(action,
                                    'Expected between {} and {} arguments'.format(action.nargs_min, action.nargs_max))

        return super()._match_argument(action, arg_strings_pattern)
