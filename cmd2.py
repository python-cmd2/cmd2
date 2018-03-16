#!/usr/bin/env python
# coding=utf-8
"""Variant on standard library's cmd with extra features.

To use, simply import cmd2.Cmd instead of cmd.Cmd; use precisely as though you
were using the standard library's cmd, while enjoying the extra features.

Searchable command history (commands: "history")
Load commands from file, save to file, edit commands in file
Multi-line commands
Special-character shortcut commands (beyond cmd's "@" and "!")
Settable environment parameters
Parsing commands with `argparse` argument parsers (flags)
Redirection to file with >, >>; input from file with <
Easy transcript-based testing of applications (see examples/example.py)
Bash-style ``select`` available

Note that redirection with > and | will only work if `self.poutput()`
is used in place of `print`.

- Catherine Devlin, Jan 03 2008 - catherinedevlin.blogspot.com

Git repository on GitHub at https://github.com/python-cmd2/cmd2
"""
import argparse
import atexit
import cmd
import codecs
import collections
import datetime
import functools
import glob
import io
import optparse
import os
import platform
import re
import shlex
import six
import sys
import tempfile
import traceback
import unittest
from code import InteractiveConsole

import pyparsing
import pyperclip

# Newer versions of pyperclip are released as a single file, but older versions had a more complicated structure
try:
    from pyperclip.exceptions import PyperclipException
except ImportError:
    # noinspection PyUnresolvedReferences
    from pyperclip import PyperclipException

# next(it) gets next item of iterator it. This is a replacement for calling it.next() in Python 2 and next(it) in Py3
from six import next

# Possible types for text data. This is basestring() in Python 2 and str in Python 3.
from six import string_types

# Used for sm.input: raw_input() for Python 2 or input() for Python 3
import six.moves as sm

# itertools.zip() for Python 2 or zip() for Python 3 - produces an iterator in both cases
from six.moves import zip

# If using Python 2.7, try to use the subprocess32 package backported from Python 3.2 due to various improvements
# NOTE: The feature to pipe output to a shell command won't work correctly in Python 2.7 without this
try:
    # noinspection PyPackageRequirements
    import subprocess32 as subprocess
except ImportError:
    import subprocess

# Python 3.4 and earlier require contextlib2 for temporarily redirecting stderr and stdout
if sys.version_info < (3, 5):
    from contextlib2 import redirect_stdout, redirect_stderr
else:
    from contextlib import redirect_stdout, redirect_stderr

# Detect whether IPython is installed to determine if the built-in "ipy" command should be included
ipython_available = True
try:
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    from IPython import embed
except ImportError:
    ipython_available = False

# Try to import readline, but allow failure for convenience in Windows unit testing
# Note: If this actually fails, you should install readline on Linux or Mac or pyreadline on Windows
try:
    # noinspection PyUnresolvedReferences
    import readline
except ImportError:
    pass

# BrokenPipeError and FileNotFoundError exist only in Python 3. Use IOError for Python 2.
if six.PY3:
    BROKEN_PIPE_ERROR = BrokenPipeError
    FILE_NOT_FOUND_ERROR = FileNotFoundError
else:
    BROKEN_PIPE_ERROR = FILE_NOT_FOUND_ERROR = IOError

# On some systems, pyperclip will import gtk for its clipboard functionality.
# The following code is a workaround for gtk interfering with printing from a background
# thread while the CLI thread is blocking in raw_input() in Python 2 on Linux.
if six.PY2 and sys.platform.startswith('lin'):
    try:
        # noinspection PyUnresolvedReferences
        import gtk
        gtk.set_interactive(0)
    except ImportError:
        pass

__version__ = '0.8.2'

# Pyparsing enablePackrat() can greatly speed up parsing, but problems have been seen in Python 3 in the past
pyparsing.ParserElement.enablePackrat()

# Override the default whitespace chars in Pyparsing so that newlines are not treated as whitespace
pyparsing.ParserElement.setDefaultWhitespaceChars(' \t')


# The next 3 variables and associated setter functions effect how arguments are parsed for decorated commands
#   which use one of the decorators such as @with_argument_list or @with_argparser
# The defaults are sane and maximize ease of use for new applications based on cmd2.
# To maximize backwards compatibility, we recommend setting USE_ARG_LIST to "False"

# Use POSIX or Non-POSIX (Windows) rules for splitting a command-line string into a list of arguments via shlex.split()
POSIX_SHLEX = False

# Strip outer quotes for convenience if POSIX_SHLEX = False
STRIP_QUOTES_FOR_NON_POSIX = True

# For @options commands, pass a list of argument strings instead of a single argument string to the do_* methods
USE_ARG_LIST = True


def set_posix_shlex(val):
    """ Allows user of cmd2 to choose between POSIX and non-POSIX splitting of args for decorated commands.

    :param val: bool - True => POSIX,  False => Non-POSIX
    """
    global POSIX_SHLEX
    POSIX_SHLEX = val


def set_strip_quotes(val):
    """ Allows user of cmd2 to choose whether to automatically strip outer-quotes when POSIX_SHLEX is False.

    :param val: bool - True => strip quotes on args for decorated commands if POSIX_SHLEX is False.
    """
    global STRIP_QUOTES_FOR_NON_POSIX
    STRIP_QUOTES_FOR_NON_POSIX = val


def set_use_arg_list(val):
    """ Allows user of cmd2 to choose between passing @options commands an argument string or list of arg strings.

    :param val: bool - True => arg is a list of strings,  False => arg is a string (for @options commands)
    """
    global USE_ARG_LIST
    USE_ARG_LIST = val


# noinspection PyUnusedLocal
def basic_complete(text, line, begidx, endidx, match_against):
    """
    Performs tab completion against a list
    :param text: str - the string prefix we are attempting to match (all returned matches must begin with it)
    :param line: str - the current input line with leading whitespace removed
    :param begidx: int - the beginning index of the prefix text
    :param endidx: int - the ending index of the prefix text
    :param match_against: iterable - the list being matched against
    :return: List[str] - a list of possible tab completions
    """
    completions = [cur_str for cur_str in match_against if cur_str.startswith(text)]

    # If there is only 1 match and it's at the end of the line, then add a space
    if len(completions) == 1 and endidx == len(line):
        completions[0] += ' '

    completions.sort()
    return completions


def flag_based_complete(text, line, begidx, endidx, flag_dict, all_else=None):
    """
    Tab completes based on a particular flag preceding the token being completed
    :param text: str - the string prefix we are attempting to match (all returned matches must begin with it)
    :param line: str - the current input line with leading whitespace removed
    :param begidx: int - the beginning index of the prefix text
    :param endidx: int - the ending index of the prefix text
    :param flag_dict: dict - dictionary whose structure is the following:
                             keys - flags (ex: -c, --create) that result in tab completion for the next
                                    argument in the command line
                             values - there are two types of values
                                1. iterable list of strings to match against (dictionaries, lists, etc.)
                                2. function that performs tab completion (ex: path_complete)
    :param all_else: iterable or function - an optional parameter for tab completing any token that isn't preceded
                                            by a flag in flag_dict
    :return: List[str] - a list of possible tab completions
    """

    # Get all tokens prior to token being completed
    try:
        prev_space_index = max(line.rfind(' ', 0, begidx), 0)
        tokens = shlex.split(line[:prev_space_index], posix=POSIX_SHLEX)
    except ValueError:
        # Invalid syntax for shlex (Probably due to missing closing quote)
        return []

    if len(tokens) == 0:
        return []

    completions = []
    match_against = all_else

    # Must have at least the command and one argument for a flag to be present
    if len(tokens) > 1:
        flag = tokens[-1]
        if flag in flag_dict:
            match_against = flag_dict[flag]

    # Perform tab completion using an iterable
    if isinstance(match_against, collections.Iterable):
        completions = [cur_str for cur_str in match_against if cur_str.startswith(text)]

        # If there is only 1 match and it's at the end of the line, then add a space
        if len(completions) == 1 and endidx == len(line):
            completions[0] += ' '

    # Perform tab completion using a function
    elif callable(match_against):
        completions = match_against(text, line, begidx, endidx)

    completions.sort()
    return completions


def index_based_complete(text, line, begidx, endidx, index_dict, all_else=None):
    """
    Tab completes based on a fixed position in the input string
    :param text: str - the string prefix we are attempting to match (all returned matches must begin with it)
    :param line: str - the current input line with leading whitespace removed
    :param begidx: int - the beginning index of the prefix text
    :param endidx: int - the ending index of the prefix text
    :param index_dict: dict - dictionary whose structure is the following:
                             keys - 0-based token indexes into command line that determine which tokens
                                    perform tab completion
                             values - there are two types of values
                                1. iterable list of strings to match against (dictionaries, lists, etc.)
                                2. function that performs tab completion (ex: path_complete)
    :param all_else: iterable or function - an optional parameter for tab completing any token that isn't at an
                                            index in index_dict
    :return: List[str] - a list of possible tab completions
    """

    # Get all tokens prior to token being completed
    try:
        prev_space_index = max(line.rfind(' ', 0, begidx), 0)
        tokens = shlex.split(line[:prev_space_index], posix=POSIX_SHLEX)
    except ValueError:
        # Invalid syntax for shlex (Probably due to missing closing quote)
        return []

    if len(tokens) == 0:
        return []

    completions = []

    # Get the index of the token being completed
    index = len(tokens)

    # Check if token is at an index in the dictionary
    if index in index_dict:
        match_against = index_dict[index]
    else:
        match_against = all_else

    # Perform tab completion using an iterable
    if isinstance(match_against, collections.Iterable):
        completions = [cur_str for cur_str in match_against if cur_str.startswith(text)]

        # If there is only 1 match and it's at the end of the line, then add a space
        if len(completions) == 1 and endidx == len(line):
            completions[0] += ' '

    # Perform tab completion using a function
    elif callable(match_against):
        completions = match_against(text, line, begidx, endidx)

    completions.sort()
    return completions


def path_complete(text, line, begidx, endidx, dir_exe_only=False, dir_only=False):
    """Method called to complete an input line by local file system path completion.

    :param text: str - the string prefix we are attempting to match (all returned matches must begin with it)
    :param line: str - the current input line with leading whitespace removed
    :param begidx: int - the beginning index of the prefix text
    :param endidx: int - the ending index of the prefix text
    :param dir_exe_only: bool - only return directories and executables, not non-executable files
    :param dir_only: bool - only return directories
    :return: List[str] - a list of possible tab completions
    """

    # Get all tokens prior to token being completed
    try:
        prev_space_index = max(line.rfind(' ', 0, begidx), 0)
        tokens = shlex.split(line[:prev_space_index], posix=POSIX_SHLEX)
    except ValueError:
        # Invalid syntax for shlex (Probably due to missing closing quote)
        return []

    if len(tokens) == 0:
        return []

    # Determine if a trailing separator should be appended to directory completions
    add_trailing_sep_if_dir = False
    if endidx == len(line) or (endidx < len(line) and line[endidx] != os.path.sep):
        add_trailing_sep_if_dir = True

    add_sep_after_tilde = False

    # Readline places begidx after ~ and path separators (/) so we need to extract any directory
    # path that appears before the search text
    dirname = line[prev_space_index + 1:begidx]

    # If no directory path and no search text has been entered, then search in the CWD for *
    if not dirname and not text:
        search_str = os.path.join(os.getcwd(), '*')
    else:
        # Purposely don't match any path containing wildcards - what we are doing is complicated enough!
        wildcards = ['*', '?']
        for wildcard in wildcards:
            if wildcard in dirname or wildcard in text:
                return []

        if not dirname:
            dirname = os.getcwd()
        elif dirname == '~':
            # If tilde was used without separator, add a separator after the tilde in the completions
            add_sep_after_tilde = True

        # Build the search string
        search_str = os.path.join(dirname, text + '*')

    # Expand "~" to the real user directory
    search_str = os.path.expanduser(search_str)

    # Find all matching path completions
    path_completions = glob.glob(search_str)

    # If we only want directories and executables, filter everything else out first
    if dir_exe_only:
        path_completions = [c for c in path_completions if os.path.isdir(c) or os.access(c, os.X_OK)]
    elif dir_only:
        path_completions = [c for c in path_completions if os.path.isdir(c)]

    # Get the basename of the paths
    completions = []
    for c in path_completions:
        basename = os.path.basename(c)

        # Add a separator after directories if the next character isn't already a separator
        if os.path.isdir(c) and add_trailing_sep_if_dir:
            basename += os.path.sep

        completions.append(basename)

    # If there is a single completion
    if len(completions) == 1:
        # If it is a file and we are at the end of the line, then add a space
        if os.path.isfile(path_completions[0]) and endidx == len(line):
            completions[0] += ' '
        # If tilde was expanded without a separator, prepend one
        elif os.path.isdir(path_completions[0]) and add_sep_after_tilde:
            completions[0] = os.path.sep + completions[0]

    completions.sort()
    return completions


class OptionParser(optparse.OptionParser):
    """Subclass of optparse.OptionParser which stores a reference to the do_* method it is parsing options for.

    Used mostly for getting access to the do_* method's docstring when printing help.
    """
    def __init__(self):
        # Call super class constructor.  Need to do it in this way for Python 2 and 3 compatibility
        optparse.OptionParser.__init__(self)
        # The do_* method this class is parsing options for.  Used for accessing docstring help.
        self._func = None

    def exit(self, status=0, msg=None):
        """Called at the end of showing help when either -h is used to show help or when bad arguments are provided.

        We override exit so it doesn't automatically exit the application.
        """
        if self.values is not None:
            self.values._exit = True

        if msg:
            print(msg)

    def print_help(self, *args, **kwargs):
        """Called when optparse encounters either -h or --help or bad arguments.  It prints help for options.

        We override it so that before the standard optparse help, it prints the do_* method docstring, if available.
        """
        if self._func.__doc__:
            print(self._func.__doc__)

        optparse.OptionParser.print_help(self, *args, **kwargs)

    def error(self, msg):
        """error(msg : string)

        Print a usage message incorporating 'msg' to stderr and exit.
        If you override this in a subclass, it should not return -- it
        should either exit or raise an exception.
        """
        raise optparse.OptParseError(msg)


def remaining_args(opts_plus_args, arg_list):
    """ Preserves the spacing originally in the arguments after the removal of options.

    :param opts_plus_args: str - original argument string, including options
    :param arg_list:  List[str] - list of strings containing the non-option arguments
    :return: str - non-option arguments as a single string, with original spacing preserved
    """
    pattern = '\s+'.join(re.escape(a) for a in arg_list) + '\s*$'
    match_obj = re.search(pattern, opts_plus_args)
    try:
        remaining = opts_plus_args[match_obj.start():]
    except AttributeError:
        # Don't preserve spacing, but at least we don't crash and we do preserve args and their order
        remaining = ' '.join(arg_list)

    return remaining


def _which(editor):
    try:
        editor_path = subprocess.check_output(['which', editor], stderr=subprocess.STDOUT).strip()
        if six.PY3:
            editor_path = editor_path.decode()
    except subprocess.CalledProcessError:
        editor_path = None
    return editor_path


def strip_quotes(arg):
    """ Strip outer quotes from a string.

     Applies to both single and double quotes.

    :param arg: str - string to strip outer quotes from
    :return str - same string with potentially outer quotes stripped
    """
    quote_chars = '"' + "'"

    if len(arg) > 1 and arg[0] == arg[-1] and arg[0] in quote_chars:
        arg = arg[1:-1]
    return arg


def parse_quoted_string(cmdline):
    """Parse a quoted string into a list of arguments."""
    if isinstance(cmdline, list):
        # arguments are already a list, return the list we were passed
        lexed_arglist = cmdline
    else:
        # Use shlex to split the command line into a list of arguments based on shell rules
        lexed_arglist = shlex.split(cmdline, posix=POSIX_SHLEX)
        # If not using POSIX shlex, make sure to strip off outer quotes for convenience
        if not POSIX_SHLEX and STRIP_QUOTES_FOR_NON_POSIX:
            temp_arglist = []
            for arg in lexed_arglist:
                temp_arglist.append(strip_quotes(arg))
            lexed_arglist = temp_arglist
    return lexed_arglist


def with_argument_list(func):
    """A decorator to alter the arguments passed to a do_* cmd2
    method. Default passes a string of whatever the user typed.
    With this decorator, the decorated method will receive a list
    of arguments parsed from user input using shlex.split()."""
    @functools.wraps(func)
    def cmd_wrapper(self, cmdline):
        lexed_arglist = parse_quoted_string(cmdline)
        func(self, lexed_arglist)

    cmd_wrapper.__doc__ = func.__doc__
    return cmd_wrapper


def with_argparser_and_unknown_args(argparser):
    """A decorator to alter a cmd2 method to populate its ``args`` argument by parsing arguments with the given
    instance of argparse.ArgumentParser, but also returning unknown args as a list.

    :param argparser: argparse.ArgumentParser - given instance of ArgumentParser
    :return: function that gets passed parsed args and a list of unknown args
    """

    # noinspection PyProtectedMember
    def arg_decorator(func):
        @functools.wraps(func)
        def cmd_wrapper(instance, cmdline):
            lexed_arglist = parse_quoted_string(cmdline)
            args, unknown = argparser.parse_known_args(lexed_arglist)
            func(instance, args, unknown)

        # argparser defaults the program name to sys.argv[0]
        # we want it to be the name of our command
        argparser.prog = func.__name__[3:]

        # If the description has not been set, then use the method docstring if one exists
        if argparser.description is None and func.__doc__:
            argparser.description = func.__doc__

        cmd_wrapper.__doc__ = argparser.format_help()

        # Mark this function as having an argparse ArgumentParser (used by do_help)
        cmd_wrapper.__dict__['has_parser'] = True

        # If there are subcommands, store their names in a list to support tab-completion of subcommand names
        if argparser._subparsers is not None:
            subcommand_names = argparser._subparsers._group_actions[0]._name_parser_map.keys()
            cmd_wrapper.__dict__['subcommand_names'] = subcommand_names

        return cmd_wrapper

    return arg_decorator


def with_argparser(argparser):
    """A decorator to alter a cmd2 method to populate its ``args`` argument by parsing arguments
    with the given instance of argparse.ArgumentParser.

    :param argparser: argparse.ArgumentParser - given instance of ArgumentParser
    :return: function that gets passed parsed args
    """

    # noinspection PyProtectedMember
    def arg_decorator(func):
        @functools.wraps(func)
        def cmd_wrapper(instance, cmdline):
            lexed_arglist = parse_quoted_string(cmdline)
            args = argparser.parse_args(lexed_arglist)
            func(instance, args)

        # argparser defaults the program name to sys.argv[0]
        # we want it to be the name of our command
        argparser.prog = func.__name__[3:]

        # If the description has not been set, then use the method docstring if one exists
        if argparser.description is None and func.__doc__:
            argparser.description = func.__doc__

        cmd_wrapper.__doc__ = argparser.format_help()

        # Mark this function as having an argparse ArgumentParser (used by do_help)
        cmd_wrapper.__dict__['has_parser'] = True

        # If there are subcommands, store their names in a list to support tab-completion of subcommand names
        if argparser._subparsers is not None:
            subcommand_names = argparser._subparsers._group_actions[0]._name_parser_map.keys()
            cmd_wrapper.__dict__['subcommand_names'] = subcommand_names

        return cmd_wrapper

    return arg_decorator


def options(option_list, arg_desc="arg"):
    """Used as a decorator and passed a list of optparse-style options,
       alters a cmd2 method to populate its ``opts`` argument from its
       raw text argument.

       Example: transform
       def do_something(self, arg):

       into
       @options([make_option('-q', '--quick', action="store_true",
                 help="Makes things fast")],
                 "source dest")
       def do_something(self, arg, opts):
           if opts.quick:
               self.fast_button = True
       """
    if not isinstance(option_list, list):
        # If passed a single option instead of a list of options, convert it to a list with one option
        option_list = [option_list]

    def option_setup(func):
        """Decorator function which modifies on of the do_* methods that use the @options decorator.

        :param func: do_* method which uses the @options decorator
        :return: modified version of the do_* method
        """
        option_parser = OptionParser()
        for option in option_list:
            option_parser.add_option(option)
        # Allow reasonable help for commands defined with @options and an empty list of options
        if len(option_list) > 0:
            option_parser.set_usage("%s [options] %s" % (func.__name__[3:], arg_desc))
        else:
            option_parser.set_usage("%s %s" % (func.__name__[3:], arg_desc))
        option_parser._func = func

        @functools.wraps(func)
        def new_func(instance, arg):
            """For @options commands this replaces the actual do_* methods in the instance __dict__.

            First it does all of the option/argument parsing.  Then it calls the underlying do_* method.

            :param instance: cmd2.Cmd2 derived class application instance
            :param arg: str - command-line arguments provided to the command
            :return: bool - returns whatever the result of calling the underlying do_* method would be
            """
            try:
                # Use shlex to split the command line into a list of arguments based on shell rules
                opts, new_arglist = option_parser.parse_args(shlex.split(arg, posix=POSIX_SHLEX))

                # If not using POSIX shlex, make sure to strip off outer quotes for convenience
                if not POSIX_SHLEX and STRIP_QUOTES_FOR_NON_POSIX:
                    temp_arglist = []
                    for arg in new_arglist:
                        temp_arglist.append(strip_quotes(arg))
                    new_arglist = temp_arglist

                    # Also strip off outer quotes on string option values
                    for key, val in opts.__dict__.items():
                        if isinstance(val, str):
                            opts.__dict__[key] = strip_quotes(val)

                # Must find the remaining args in the original argument list, but
                # mustn't include the command itself
                # if hasattr(arg, 'parsed') and new_arglist[0] == arg.parsed.command:
                #    new_arglist = new_arglist[1:]
                if USE_ARG_LIST:
                    arg = new_arglist
                else:
                    new_args = remaining_args(arg, new_arglist)
                    if isinstance(arg, ParsedString):
                        arg = arg.with_args_replaced(new_args)
                    else:
                        arg = new_args
            except optparse.OptParseError as e:
                print(e)
                option_parser.print_help()
                return
            if hasattr(opts, '_exit'):
                return None
            result = func(instance, arg, opts)
            return result

        new_func.__doc__ = '%s%s' % (func.__doc__ + '\n' if func.__doc__ else '', option_parser.format_help())
        return new_func

    return option_setup


# Can we access the clipboard?  Should always be true on Windows and Mac, but only sometimes on Linux
# noinspection PyUnresolvedReferences
try:
    # Get the version of the pyperclip module as a float
    pyperclip_ver = float('.'.join(pyperclip.__version__.split('.')[:2]))

    # The extraneous output bug in pyperclip on Linux using xclip was fixed in more recent versions of pyperclip
    if sys.platform.startswith('linux') and pyperclip_ver < 1.6:
        # Avoid extraneous output to stderr from xclip when clipboard is empty at cost of overwriting clipboard contents
        pyperclip.copy('')
    else:
        # Try getting the contents of the clipboard
        _ = pyperclip.paste()
except PyperclipException:
    can_clip = False
else:
    can_clip = True


def get_paste_buffer():
    """Get the contents of the clipboard / paste buffer.

    :return: str - contents of the clipboard
    """
    pb_str = pyperclip.paste()

    # If value returned from the clipboard is unicode and this is Python 2, convert to a "normal" Python 2 string first
    if six.PY2 and not isinstance(pb_str, str):
        import unicodedata
        pb_str = unicodedata.normalize('NFKD', pb_str).encode('ascii', 'ignore')

    return pb_str


def write_to_paste_buffer(txt):
    """Copy text to the clipboard / paste buffer.

    :param txt: str - text to copy to the clipboard
    """
    pyperclip.copy(txt)


class ParsedString(str):
    """Subclass of str which also stores a pyparsing.ParseResults object containing structured parse results."""
    # pyarsing.ParseResults - structured parse results, to provide multiple means of access to the parsed data
    parsed = None

    # Function which did the parsing
    parser = None

    def full_parsed_statement(self):
        """Used to reconstruct the full parsed statement when a command isn't recognized."""
        new = ParsedString('%s %s' % (self.parsed.command, self.parsed.args))
        new.parsed = self.parsed
        new.parser = self.parser
        return new

    def with_args_replaced(self, newargs):
        """Used for @options commands when USE_ARG_LIST is False.

        It helps figure out what the args are after removing options.
        """
        new = ParsedString(newargs)
        new.parsed = self.parsed
        new.parser = self.parser
        new.parsed['args'] = newargs
        new.parsed.statement['args'] = newargs
        return new


def replace_with_file_contents(fname):
    """Action to perform when successfully matching parse element definition for inputFrom parser.

    :param fname: str - filename
    :return: str - contents of file "fname"
    """
    try:
        with open(os.path.expanduser(fname[0])) as source_file:
            result = source_file.read()
    except IOError:
        result = '< %s' % fname[0]  # wasn't a file after all

    # TODO: IF pyparsing input parser logic gets fixed to support empty file, add support to get from paste buffer
    return result


class EmbeddedConsoleExit(SystemExit):
    """Custom exception class for use with the py command."""
    pass


class EmptyStatement(Exception):
    """Custom exception class for handling behavior when the user just presses <Enter>."""
    pass


# Regular expression to match ANSI escape codes
ANSI_ESCAPE_RE = re.compile(r'\x1b[^m]*m')


def strip_ansi(text):
    """Strip ANSI escape codes from a string.

    :param text: str - a string which may contain ANSI escape codes
    :return: str - the same string with any ANSI escape codes removed
    """
    return ANSI_ESCAPE_RE.sub('', text)


def _pop_readline_history(clear_history=True):
    """Returns a copy of readline's history and optionally clears it (default)"""
    # noinspection PyArgumentList
    history = [
        readline.get_history_item(i)
        for i in range(1, 1 + readline.get_current_history_length())
    ]
    if clear_history:
        readline.clear_history()
    return history


def _push_readline_history(history, clear_history=True):
    """Restores readline's history and optionally clears it first (default)"""
    if clear_history:
        readline.clear_history()
    for line in history:
        readline.add_history(line)


def _complete_from_cmd(cmd_obj, text, line, begidx, endidx):
    """Complete as though the user was typing inside cmd's cmdloop()"""
    from itertools import takewhile
    command_subcommand_params = line.split(None, 3)

    if len(command_subcommand_params) < (3 if text else 2):
        n = len(command_subcommand_params[0])
        n += sum(1 for _ in takewhile(str.isspace, line[n:]))
        return cmd_obj.completenames(text, line[n:], begidx - n, endidx - n)

    command, subcommand = command_subcommand_params[:2]
    n = len(command) + sum(1 for _ in takewhile(str.isspace, line))
    cfun = getattr(cmd_obj, 'complete_' + subcommand, cmd_obj.complete)
    return cfun(text, line[n:], begidx - n, endidx - n)


class AddSubmenu(object):
    """Conveniently add a submenu (Cmd-like class) to a Cmd

    e.g. given "class SubMenu(Cmd): ..." then

    @AddSubmenu(SubMenu(), 'sub')
    class MyCmd(cmd.Cmd):
        ....

    will have the following effects:
    1. 'sub' will interactively enter the cmdloop of a SubMenu instance
    2. 'sub cmd args' will call do_cmd(args) in a SubMenu instance
    3. 'sub ... [TAB]' will have the same behavior as [TAB] in a SubMenu cmdloop
       i.e., autocompletion works the way you think it should
    4. 'help sub [cmd]' will print SubMenu's help (calls its do_help())
    """

    class _Nonexistent(object):
        """
        Used to mark missing attributes.
        Disable __dict__ creation since this class does nothing
        """
        __slots__ = ()  #

    def __init__(self,
                 submenu,
                 command,
                 aliases=(),
                 reformat_prompt="{super_prompt}>> {sub_prompt}",
                 shared_attributes=None,
                 require_predefined_shares=True,
                 create_subclass=False,
                 preserve_shares=False,
                 persistent_history_file=None
                 ):
        """Set up the class decorator

        submenu (Cmd):              Instance of something cmd.Cmd-like

        command (str):              The command the user types to access the SubMenu instance

        aliases (iterable):         More commands that will behave like "command"

        reformat_prompt (str):      Format str or None to disable
            if it's a string, it should contain one or more of:
                {super_prompt}:     The current cmd's prompt
                {command}:          The command in the current cmd with which it was called
                {sub_prompt}:       The subordinate cmd's original prompt
            the default is "{super_prompt}{command} {sub_prompt}"

        shared_attributes (dict):   dict of the form {'subordinate_attr': 'parent_attr'}
            the attributes are copied to the submenu at the last moment; the submenu's
            attributes are backed up before this and restored afterward

        require_predefined_shares: The shared attributes above must be independently
            defined in the subordinate Cmd (default: True)

        create_subclass: put the modifications in a subclass rather than modifying
            the existing class (default: False)
        """
        self.submenu = submenu
        self.command = command
        self.aliases = aliases
        if persistent_history_file:
            self.persistent_history_file = os.path.expanduser(persistent_history_file)
        else:
            self.persistent_history_file = None

        if reformat_prompt is not None and not isinstance(reformat_prompt, str):
            raise ValueError("reformat_prompt should be either a format string or None")
        self.reformat_prompt = reformat_prompt

        self.shared_attributes = {} if shared_attributes is None else shared_attributes
        if require_predefined_shares:
            for attr in self.shared_attributes.keys():
                if not hasattr(submenu, attr):
                    raise AttributeError("The shared attribute '{attr}' is not defined in {cmd}. Either define {attr} "
                                         "in {cmd} or set require_predefined_shares=False."
                                         .format(cmd=submenu.__class__.__name__, attr=attr))

        self.create_subclass = create_subclass
        self.preserve_shares = preserve_shares

    def _get_original_attributes(self):
        return {
            attr: getattr(self.submenu, attr, AddSubmenu._Nonexistent)
            for attr in self.shared_attributes.keys()
        }

    def _copy_in_shared_attrs(self, parent_cmd):
        for sub_attr, par_attr in self.shared_attributes.items():
            setattr(self.submenu, sub_attr, getattr(parent_cmd, par_attr))

    def _copy_out_shared_attrs(self, parent_cmd, original_attributes):
        if self.preserve_shares:
            for sub_attr, par_attr in self.shared_attributes.items():
                setattr(parent_cmd, par_attr, getattr(self.submenu, sub_attr))
        else:
            for attr, value in original_attributes.items():
                if attr is not AddSubmenu._Nonexistent:
                    setattr(self.submenu, attr, value)
                else:
                    delattr(self.submenu, attr)

    def __call__(self, cmd_obj):
        """Creates a subclass of Cmd wherein the given submenu can be accessed via the given command"""
        def enter_submenu(parent_cmd, line):
            """
            This function will be bound to do_<submenu> and will change the scope of the CLI to that of the
            submenu.
            """
            submenu = self.submenu
            original_attributes = self._get_original_attributes()
            history = _pop_readline_history()

            if self.persistent_history_file:
                try:
                    readline.read_history_file(self.persistent_history_file)
                except FILE_NOT_FOUND_ERROR:
                    pass

            try:
                # copy over any shared attributes
                self._copy_in_shared_attrs(parent_cmd)

                if line.parsed.args:
                    # Remove the menu argument and execute the command in the submenu
                    line = submenu.parser_manager.parsed(line.parsed.args)
                    submenu.precmd(line)
                    ret = submenu.onecmd(line)
                    submenu.postcmd(ret, line)
                else:
                    if self.reformat_prompt is not None:
                        prompt = submenu.prompt
                        submenu.prompt = self.reformat_prompt.format(
                            super_prompt=parent_cmd.prompt,
                            command=self.command,
                            sub_prompt=prompt,
                        )
                    submenu.cmdloop()
                    if self.reformat_prompt is not None:
                        # noinspection PyUnboundLocalVariable
                        self.submenu.prompt = prompt
            finally:
                # copy back original attributes
                self._copy_out_shared_attrs(parent_cmd, original_attributes)

                # write submenu history
                if self.persistent_history_file:
                    readline.write_history_file(self.persistent_history_file)
                # reset main app history before exit
                _push_readline_history(history)

        def complete_submenu(_self, text, line, begidx, endidx):
            """
            This function will be bound to complete_<submenu> and will perform the complete commands of the submenu.
            """
            submenu = self.submenu
            original_attributes = self._get_original_attributes()
            try:
                # copy over any shared attributes
                self._copy_in_shared_attrs(_self)
                return _complete_from_cmd(submenu, text, line, begidx, endidx)
            finally:
                # copy back original attributes
                self._copy_out_shared_attrs(_self, original_attributes)

        original_do_help = cmd_obj.do_help
        original_complete_help = cmd_obj.complete_help

        def help_submenu(_self, line):
            """
            This function will be bound to help_<submenu> and will call the help commands of the submenu.
            """
            tokens = line.split(None, 1)
            if tokens and (tokens[0] == self.command or tokens[0] in self.aliases):
                self.submenu.do_help(tokens[1] if len(tokens) == 2 else '')
            else:
                original_do_help(_self, line)

        def _complete_submenu_help(_self, text, line, begidx, endidx):
            """autocomplete to match help_submenu()'s behavior"""
            tokens = line.split(None, 1)
            if len(tokens) == 2 and (
                    not (not tokens[1].startswith(self.command) and not any(
                        tokens[1].startswith(alias) for alias in self.aliases))
            ):
                return self.submenu.complete_help(
                    text,
                    tokens[1],
                    begidx - line.index(tokens[1]),
                    endidx - line.index(tokens[1]),
                )
            else:
                return original_complete_help(_self, text, line, begidx, endidx)

        if self.create_subclass:
            class _Cmd(cmd_obj):
                do_help = help_submenu
                complete_help = _complete_submenu_help
        else:
            _Cmd = cmd_obj
            _Cmd.do_help = help_submenu
            _Cmd.complete_help = _complete_submenu_help

        # Create bindings in the parent command to the submenus commands.
        setattr(_Cmd, 'do_' + self.command, enter_submenu)
        setattr(_Cmd, 'complete_' + self.command, complete_submenu)

        # Create additional bindings for aliases
        for _alias in self.aliases:
            setattr(_Cmd, 'do_' + _alias, enter_submenu)
            setattr(_Cmd, 'complete_' + _alias, complete_submenu)
        return _Cmd


class Cmd(cmd.Cmd):
    """An easy but powerful framework for writing line-oriented command interpreters.

    Extends the Python Standard Library’s cmd package by adding a lot of useful features
    to the out of the box configuration.

    Line-oriented command interpreters are often useful for test harnesses, internal tools, and rapid prototypes.
    """
    # Attributes used to configure the ParserManager (all are not dynamically settable at runtime)
    blankLinesAllowed = False
    commentGrammars = pyparsing.Or([pyparsing.pythonStyleComment, pyparsing.cStyleComment])
    commentInProgress = pyparsing.Literal('/*') + pyparsing.SkipTo(pyparsing.stringEnd ^ '*/')
    legalChars = u'!#$%.:?@_-' + pyparsing.alphanums + pyparsing.alphas8bit
    multilineCommands = []
    prefixParser = pyparsing.Empty()
    redirector = '>'        # for sending output to file
    shortcuts = {'?': 'help', '!': 'shell', '@': 'load', '@@': '_relative_load'}
    aliases = dict()
    terminators = [';']     # make sure your terminators are not in legalChars!

    # Attributes which are NOT dynamically settable at runtime
    allow_cli_args = True       # Should arguments passed on the command-line be processed as commands?
    allow_redirection = True    # Should output redirection and pipes be allowed
    default_to_shell = False    # Attempt to run unrecognized commands as shell commands
    quit_on_sigint = True       # Quit the loop on interrupt instead of just resetting prompt
    reserved_words = []

    # Attributes which ARE dynamically settable at runtime
    colors = (platform.system() != 'Windows')
    continuation_prompt = '> '
    debug = False
    echo = False
    editor = os.environ.get('EDITOR')
    if not editor:
        if sys.platform[:3] == 'win':
            editor = 'notepad'
        else:
            # Favor command-line editors first so we don't leave the terminal to edit
            for editor in ['vim', 'vi', 'emacs', 'nano', 'pico', 'gedit', 'kate', 'subl', 'geany', 'atom']:
                if _which(editor):
                    break
    feedback_to_output = False  # Do not include nonessentials in >, | output by default (things like timing)
    locals_in_py = True
    quiet = False  # Do not suppress nonessential output
    timing = False  # Prints elapsed time for each command

    # To make an attribute settable with the "do_set" command, add it to this ...
    # This starts out as a dictionary but gets converted to an OrderedDict sorted alphabetically by key
    settable = {'colors': 'Colorized output (*nix only)',
                'continuation_prompt': 'On 2nd+ line of input',
                'debug': 'Show full error stack on error',
                'echo': 'Echo command issued into output',
                'editor': 'Program used by ``edit``',
                'feedback_to_output': 'Include nonessentials in `|`, `>` results',
                'locals_in_py': 'Allow access to your application in py via self',
                'prompt': 'The prompt issued to solicit input',
                'quiet': "Don't print nonessential feedback",
                'timing': 'Report execution times'}

    def __init__(self, completekey='tab', stdin=None, stdout=None, persistent_history_file='',
                 persistent_history_length=1000, use_ipython=False, transcript_files=None):
        """An easy but powerful framework for writing line-oriented command interpreters, extends Python's cmd package.

        :param completekey: str - (optional) readline name of a completion key, default to Tab
        :param stdin: (optional) alternate input file object, if not specified, sys.stdin is used
        :param stdout: (optional) alternate output file object, if not specified, sys.stdout is used
        :param persistent_history_file: str - (optional) file path to load a persistent readline history from
        :param persistent_history_length: int - (optional) max number of lines which will be written to the history file
        :param use_ipython: (optional) should the "ipy" command be included for an embedded IPython shell
        :param transcript_files: str - (optional) allows running transcript tests when allow_cli_args is False
        """
        # If use_ipython is False, make sure the do_ipy() method doesn't exit
        if not use_ipython:
            try:
                del Cmd.do_ipy
            except AttributeError:
                pass

        # If persistent readline history is enabled, then read history from file and register to write to file at exit
        if persistent_history_file:
            persistent_history_file = os.path.expanduser(persistent_history_file)
            try:
                readline.read_history_file(persistent_history_file)
                # default history len is -1 (infinite), which may grow unruly
                readline.set_history_length(persistent_history_length)
            except FILE_NOT_FOUND_ERROR:
                pass
            atexit.register(readline.write_history_file, persistent_history_file)

        # Call super class constructor.  Need to do it in this way for Python 2 and 3 compatibility
        cmd.Cmd.__init__(self, completekey=completekey, stdin=stdin, stdout=stdout)

        # Commands to exclude from the help menu or history command
        self.exclude_from_help = ['do_eof', 'do_eos', 'do__relative_load']
        self.excludeFromHistory = '''history edit eof eos'''.split()

        self._finalize_app_parameters()

        self.initial_stdout = sys.stdout
        self.history = History()
        self.pystate = {}
        self.keywords = self.reserved_words + [fname[3:] for fname in dir(self) if fname.startswith('do_')]
        self.parser_manager = ParserManager(redirector=self.redirector, terminators=self.terminators,
                                            multilineCommands=self.multilineCommands,
                                            legalChars=self.legalChars, commentGrammars=self.commentGrammars,
                                            commentInProgress=self.commentInProgress,
                                            blankLinesAllowed=self.blankLinesAllowed, prefixParser=self.prefixParser,
                                            preparse=self.preparse, postparse=self.postparse, aliases=self.aliases,
                                            shortcuts=self.shortcuts)
        self._transcript_files = transcript_files

        # Used to enable the ability for a Python script to quit the application
        self._should_quit = False

        # True if running inside a Python script or interactive console, False otherwise
        self._in_py = False

        # Stores results from the last command run to enable usage of results in a Python script or interactive console
        # Built-in commands don't make use of this.  It is purely there for user-defined commands and convenience.
        self._last_result = None

        # Used to save state during a redirection
        self.kept_state = None
        self.kept_sys = None

        # Codes used for exit conditions
        self._STOP_AND_EXIT = True  # cmd convention

        self._colorcodes = {'bold': {True: '\x1b[1m', False: '\x1b[22m'},
                            'cyan': {True: '\x1b[36m', False: '\x1b[39m'},
                            'blue': {True: '\x1b[34m', False: '\x1b[39m'},
                            'red': {True: '\x1b[31m', False: '\x1b[39m'},
                            'magenta': {True: '\x1b[35m', False: '\x1b[39m'},
                            'green': {True: '\x1b[32m', False: '\x1b[39m'},
                            'underline': {True: '\x1b[4m', False: '\x1b[24m'},
                            'yellow': {True: '\x1b[33m', False: '\x1b[39m'}}

        # Used load command to store the current script dir as a LIFO queue to support _relative_load command
        self._script_dir = []

        # Used when piping command output to a shell command
        self.pipe_proc = None

        # Used by complete() for readline tab completion
        self.completion_matches = []

        # Used to keep track of whether we are redirecting or piping output
        self.redirecting = False

        # If this string is non-empty, then this warning message will print if a broken pipe error occurs while printing
        self.broken_pipe_warning = ''

    # -----  Methods related to presenting output to the user -----

    @property
    def visible_prompt(self):
        """Read-only property to get the visible prompt with any ANSI escape codes stripped.

        Used by transcript testing to make it easier and more reliable when users are doing things like coloring the
        prompt using ANSI color codes.

        :return: str - prompt stripped of any ANSI escape codes
        """
        return strip_ansi(self.prompt)

    def _finalize_app_parameters(self):
        self.commentGrammars.ignore(pyparsing.quotedString).setParseAction(lambda x: '')
        # noinspection PyUnresolvedReferences
        self.shortcuts = sorted(self.shortcuts.items(), reverse=True)

        # Make sure settable parameters are sorted alphabetically by key
        self.settable = collections.OrderedDict(sorted(self.settable.items(), key=lambda t: t[0]))

    def poutput(self, msg, end='\n'):
        """Convenient shortcut for self.stdout.write(); by default adds newline to end if not already present.

        Also handles BrokenPipeError exceptions for when a commands's output has been piped to another process and
        that process terminates before the cmd2 command is finished executing.

        :param msg: str - message to print to current stdout - anything convertible to a str with '{}'.format() is OK
        :param end: str - string appended after the end of the message if not already present, default a newline
        """
        if msg is not None and msg != '':
            try:
                msg_str = '{}'.format(msg)
                self.stdout.write(msg_str)
                if not msg_str.endswith(end):
                    self.stdout.write(end)
            except BROKEN_PIPE_ERROR:
                # This occurs if a command's output is being piped to another process and that process closes before the
                # command is finished. If you would like your application to print a warning message, then set the
                # broken_pipe_warning attribute to the message you want printed.
                if self.broken_pipe_warning:
                    sys.stderr.write(self.broken_pipe_warning)

    def perror(self, errmsg, exception_type=None, traceback_war=True):
        """ Print error message to sys.stderr and if debug is true, print an exception Traceback if one exists.

        :param errmsg: str - error message to print out
        :param exception_type: str - (optional) type of exception which precipitated this error message
        :param traceback_war: bool - (optional) if True, print a message to let user know they can enable debug
        :return:
        """
        if self.debug:
            traceback.print_exc()

        if exception_type is None:
            err = self.colorize("ERROR: {}\n".format(errmsg), 'red')
            sys.stderr.write(err)
        else:
            err = "EXCEPTION of type '{}' occurred with message: '{}'\n".format(exception_type, errmsg)
            sys.stderr.write(self.colorize(err, 'red'))

        if traceback_war:
            war = "To enable full traceback, run the following command:  'set debug true'\n"
            sys.stderr.write(self.colorize(war, 'yellow'))

    def pfeedback(self, msg):
        """For printing nonessential feedback.  Can be silenced with `quiet`.
           Inclusion in redirected output is controlled by `feedback_to_output`."""
        if not self.quiet:
            if self.feedback_to_output:
                self.poutput(msg)
            else:
                sys.stderr.write("{}\n".format(msg))

    def ppaged(self, msg, end='\n'):
        """Print output using a pager if it would go off screen and stdout isn't currently being redirected.

        Never uses a pager inside of a script (Python or text) or when output is being redirected or piped.

        :param msg: str - message to print to current stdout - anything convertible to a str with '{}'.format() is OK
        :param end: str - string appended after the end of the message if not already present, default a newline
        """
        if msg is not None and msg != '':
            try:
                msg_str = '{}'.format(msg)
                if not msg_str.endswith(end):
                    msg_str += end

                # Don't attempt to use a pager that can block if redirecting or running a script (either text or Python)
                if not self.redirecting and not self._in_py and not self._script_dir:
                    if sys.platform.startswith('win'):
                        pager_cmd = 'more'
                    else:
                        # Here is the meaning of the various flags we are using with the less command:
                        # -S causes lines longer than the screen width to be chopped (truncated) rather than wrapped
                        # -R causes ANSI "color" escape sequences to be output in raw form (i.e. colors are displayed)
                        # -X disables sending the termcap initialization and deinitialization strings to the terminal
                        # -F causes less to automatically exit if the entire file can be displayed on the first screen
                        pager_cmd = 'less -SRXF'
                    self.pipe_proc = subprocess.Popen(pager_cmd, shell=True, stdin=subprocess.PIPE)
                    try:
                        self.pipe_proc.stdin.write(msg_str.encode('utf-8', 'replace'))
                        self.pipe_proc.stdin.close()
                    except (IOError, KeyboardInterrupt):
                        pass

                    # Less doesn't respect ^C, but catches it for its own UI purposes (aborting search etc. inside less)
                    while True:
                        try:
                            self.pipe_proc.wait()
                        except KeyboardInterrupt:
                            pass
                        else:
                            break
                    self.pipe_proc = None
                else:
                    self.stdout.write(msg_str)
            except BROKEN_PIPE_ERROR:
                # This occurs if a command's output is being piped to another process and that process closes before the
                # command is finished. If you would like your application to print a warning message, then set the
                # broken_pipe_warning attribute to the message you want printed.
                if self.broken_pipe_warning:
                    sys.stderr.write(self.broken_pipe_warning)

    def colorize(self, val, color):
        """Given a string (``val``), returns that string wrapped in UNIX-style
           special characters that turn on (and then off) text color and style.
           If the ``colors`` environment parameter is ``False``, or the application
           is running on Windows, will return ``val`` unchanged.
           ``color`` should be one of the supported strings (or styles):
           red/blue/green/cyan/magenta, bold, underline"""
        if self.colors and (self.stdout == self.initial_stdout):
            return self._colorcodes[color][True] + val + self._colorcodes[color][False]
        return val

    # -----  Methods which override stuff in cmd -----

    # noinspection PyMethodOverriding
    def completenames(self, text, line, begidx, endidx):
        """Override of cmd method which completes command names both for command completion and help."""
        # Call super class method.  Need to do it this way for Python 2 and 3 compatibility
        cmd_completion = cmd.Cmd.completenames(self, text)

        # If we are completing the initial command name and get exactly 1 result and are at end of line, add a space
        if begidx == 0 and len(cmd_completion) == 1 and endidx == len(line):
            cmd_completion[0] += ' '

        return cmd_completion

    def get_subcommands(self, command):
        """
        Returns a list of a command's subcommands if they exist
        :param command:
        :return: A subcommand list or None
        """

        subcommand_names = None

        # Check if is a valid command
        funcname = self._func_named(command)

        if funcname:
            # Check to see if this function was decorated with an argparse ArgumentParser
            func = getattr(self, funcname)
            subcommand_names = func.__dict__.get('subcommand_names', None)

        return subcommand_names

    def complete(self, text, state):
        """Override of command method which returns the next possible completion for 'text'.

        If a command has not been entered, then complete against command list.
        Otherwise try to call complete_<command> to get list of completions.

        This method gets called directly by readline because it is set as the tab-completion function.

        This completer function is called as complete(text, state), for state in 0, 1, 2, …, until it returns a
        non-string value. It should return the next possible completion starting with text.

        :param text: str - the current word that user is typing
        :param state: int - non-negative integer
        """
        if state == 0:
            import readline
            origline = readline.get_line_buffer()
            line = origline.lstrip()
            stripped = len(origline) - len(line)
            begidx = readline.get_begidx() - stripped
            endidx = readline.get_endidx() - stripped

            # If begidx is greater than 0, then the cursor is past the command
            if begidx > 0:

                # Parse the command line
                command, args, expanded_line = self.parseline(line)

                # We overwrote line with a properly formatted but fully stripped version
                # Restore the end spaces from the original since line is only supposed to be
                # lstripped when passed to completer functions according to Python docs
                rstripped_len = len(origline) - len(origline.rstrip())
                expanded_line += ' ' * rstripped_len

                # Fix the index values if expanded_line has a different size than line
                if len(expanded_line) != len(line):
                    diff = len(expanded_line) - len(line)
                    begidx += diff
                    endidx += diff

                # Overwrite line to pass into completers
                line = expanded_line

                if command == '':
                    compfunc = self.completedefault
                else:
                    # Get the completion function for this command
                    try:
                        compfunc = getattr(self, 'complete_' + command)
                    except AttributeError:
                        if self.default_to_shell and command in self._get_exes_in_path(command, False):
                            compfunc = functools.partial(path_complete)
                        else:
                            compfunc = self.completedefault

                    # If there are subcommands, then try completing those if the cursor is in
                    # the token at index 1, otherwise default to using compfunc
                    subcommands = self.get_subcommands(command)
                    if subcommands is not None:
                        index_dict = {1: subcommands}
                        compfunc = functools.partial(index_based_complete,
                                                     index_dict=index_dict,
                                                     all_else=compfunc)

                # Call the completer function
                self.completion_matches = compfunc(text, line, begidx, endidx)

            else:
                # Complete the command against aliases and command names
                strs_to_match = list(self.aliases.keys())

                # Add command names
                strs_to_match.extend(self.get_command_names())

                # Perform matching
                completions = [cur_str for cur_str in strs_to_match if cur_str.startswith(text)]

                # If there is only 1 match and it's at the end of the line, then add a space
                if len(completions) == 1 and endidx == len(line):
                    completions[0] += ' '

                self.completion_matches = completions

        try:
            return self.completion_matches[state]
        except IndexError:
            return None

    def get_command_names(self):
        """ Returns a list of commands """
        return [cur_name[3:] for cur_name in self.get_names() if cur_name.startswith('do_')]

    def complete_help(self, text, line, begidx, endidx):
        """
        Override of parent class method to handle tab completing subcommands
        """

        # Get all tokens prior to token being completed
        try:
            prev_space_index = max(line.rfind(' ', 0, begidx), 0)
            tokens = shlex.split(line[:prev_space_index], posix=POSIX_SHLEX)
        except ValueError:
            # Invalid syntax for shlex (Probably due to missing closing quote)
            return []

        completions = []

        # If we have "help" and a completed command token, then attempt to match subcommands
        if len(tokens) == 2:

            # Match subcommands if any exist
            subcommands = self.get_subcommands(tokens[1])
            if subcommands is not None:
                completions = [cur_sub for cur_sub in subcommands if cur_sub.startswith(text)]

        # Run normal help completion from the parent class
        else:
            completions = cmd.Cmd.complete_help(self, text, line, begidx, endidx)

            # If only 1 command has been matched and it's at the end of the line,
            # then add a space if it has subcommands
            if len(completions) == 1 and endidx == len(line) and self.get_subcommands(completions[0]) is not None:
                completions[0] += ' '

        completions.sort()
        return completions

    def precmd(self, statement):
        """Hook method executed just before the command is processed by ``onecmd()`` and after adding it to the history.

        :param statement: ParsedString - subclass of str which also contains pyparsing ParseResults instance
        :return: ParsedString - a potentially modified version of the input ParsedString statement
        """
        return statement

    # -----  Methods which are cmd2-specific lifecycle hooks which are not present in cmd -----

    # noinspection PyMethodMayBeStatic
    def preparse(self, raw):
        """Hook method executed just before the command line is interpreted, but after the input prompt is generated.

        :param raw: str - raw command line input
        :return: str - potentially modified raw command line input
        """
        return raw

    # noinspection PyMethodMayBeStatic
    def postparse(self, parse_result):
        """Hook that runs immediately after parsing the command-line but before ``parsed()`` returns a ParsedString.

        :param parse_result: pyparsing.ParseResults - parsing results output by the pyparsing parser
        :return: pyparsing.ParseResults - potentially modified ParseResults object
        """
        return parse_result

    # noinspection PyMethodMayBeStatic
    def postparsing_precmd(self, statement):
        """This runs after parsing the command-line, but before anything else; even before adding cmd to history.

        NOTE: This runs before precmd() and prior to any potential output redirection or piping.

        If you wish to fatally fail this command and exit the application entirely, set stop = True.

        If you wish to just fail this command you can do so by raising an exception:

        - raise EmptyStatement - will silently fail and do nothing
        - raise <AnyOtherException> - will fail and print an error message

        :param statement: - the parsed command-line statement
        :return: (bool, statement) - (stop, statement) containing a potentially modified version of the statement
        """
        stop = False
        return stop, statement

    # noinspection PyMethodMayBeStatic
    def postparsing_postcmd(self, stop):
        """This runs after everything else, including after postcmd().

        It even runs when an empty line is entered.  Thus, if you need to do something like update the prompt due
        to notifications from a background thread, then this is the method you want to override to do it.

        :param stop: bool - True implies the entire application should exit.
        :return: bool - True implies the entire application should exit.
        """
        if not sys.platform.startswith('win'):
            # Fix those annoying problems that occur with terminal programs like "less" when you pipe to them
            if self.stdin.isatty():
                proc = subprocess.Popen(shlex.split('stty sane'))
                proc.communicate()
        return stop

    def parseline(self, line):
        """Parse the line into a command name and a string containing the arguments.

        NOTE: This is an override of a parent class method.  It is only used by other parent class methods.  But
        we do need to override it here so that the additional shortcuts present in cmd2 get properly expanded for
        purposes of tab completion.

        Used for command tab completion.  Returns a tuple containing (command, args, line).
        'command' and 'args' may be None if the line couldn't be parsed.

        :param line: str - line read by readline
        :return: (str, str, str) - tuple containing (command, args, line)
        """
        line = line.strip()

        if not line:
            # Deal with empty line or all whitespace line
            return None, None, line

        # Handle aliases
        for cur_alias in self.aliases:
            if line == cur_alias or line.startswith(cur_alias + ' '):
                line = line.replace(cur_alias, self.aliases[cur_alias], 1)
                break

        # Expand command shortcuts to the full command name
        for (shortcut, expansion) in self.shortcuts:
            if line.startswith(shortcut):
                # If the next character after the shortcut isn't a space, then insert one
                shortcut_len = len(shortcut)
                if len(line) == shortcut_len or line[shortcut_len] != ' ':
                    expansion += ' '

                # Expand the shortcut
                line = line.replace(shortcut, expansion, 1)
                break

        i, n = 0, len(line)
        while i < n and line[i] in self.identchars:
            i += 1
        command, arg = line[:i], line[i:].strip()

        # Make sure there is a space between the command and args
        # This can occur when a character not in self.identchars bumps against the command (ex: help@)
        if len(command) > 0 and len(arg) > 0 and line[len(command)] != ' ':
            line = line.replace(command, command + ' ', 1)

        return command, arg, line

    def onecmd_plus_hooks(self, line):
        """Top-level function called by cmdloop() to handle parsing a line and running the command and all of its hooks.

        :param line: str - line of text read from input
        :return: bool - True if cmdloop() should exit, False otherwise
        """
        stop = 0
        try:
            statement = self._complete_statement(line)
            (stop, statement) = self.postparsing_precmd(statement)
            if stop:
                return self.postparsing_postcmd(stop)

            try:
                if self.allow_redirection:
                    self._redirect_output(statement)
                timestart = datetime.datetime.now()
                statement = self.precmd(statement)
                stop = self.onecmd(statement)
                stop = self.postcmd(stop, statement)
                if self.timing:
                    self.pfeedback('Elapsed: %s' % str(datetime.datetime.now() - timestart))
            finally:
                if self.allow_redirection:
                    self._restore_output(statement)
        except EmptyStatement:
            pass
        except ValueError as ex:
            # If shlex.split failed on syntax, let user know whats going on
            self.perror("Invalid syntax: {}".format(ex), traceback_war=False)
        except Exception as ex:
            self.perror(ex, type(ex).__name__)
        finally:
            return self.postparsing_postcmd(stop)

    def runcmds_plus_hooks(self, cmds):
        """Convenience method to run multiple commands by onecmd_plus_hooks.

        This method adds the given cmds to the command queue and processes the
        queue until completion or an error causes it to abort. Scripts that are
        loaded will have their commands added to the queue. Scripts may even
        load other scripts recursively. This means, however, that you should not
        use this method if there is a running cmdloop or some other event-loop.
        This method is only intended to be used in "one-off" scenarios.

        NOTE: You may need this method even if you only have one command. If
        that command is a load, then you will need this command to fully process
        all the subsequent commands that are loaded from the script file. This
        is an improvement over onecmd_plus_hooks, which expects to be used
        inside of a command loop which does the processing of loaded commands.

        Example: cmd_obj.runcmds_plus_hooks(['load myscript.txt'])

        :param cmds: list - Command strings suitable for onecmd_plus_hooks.
        :return: bool - True implies the entire application should exit.

        """
        stop = False
        self.cmdqueue = list(cmds) + self.cmdqueue
        try:
            while self.cmdqueue and not stop:
                line = self.cmdqueue.pop(0)
                if self.echo and line != 'eos':
                    self.poutput('{}{}'.format(self.prompt, line))

                stop = self.onecmd_plus_hooks(line)
        finally:
            # Clear out the command queue and script directory stack, just in
            # case we hit an error and they were not completed.
            self.cmdqueue = []
            self._script_dir = []
            # NOTE: placing this return here inside the finally block will
            # swallow exceptions. This is consistent with what is done in
            # onecmd_plus_hooks and _cmdloop, although it may not be
            # necessary/desired here.
            return stop

    def _complete_statement(self, line):
        """Keep accepting lines of input until the command is complete."""
        if not line or (not pyparsing.Or(self.commentGrammars).setParseAction(lambda x: '').transformString(line)):
            raise EmptyStatement()
        statement = self.parser_manager.parsed(line)
        while statement.parsed.multilineCommand and (statement.parsed.terminator == ''):
            statement = '%s\n%s' % (statement.parsed.raw,
                                    self.pseudo_raw_input(self.continuation_prompt))
            statement = self.parser_manager.parsed(statement)
        if not statement.parsed.command:
            raise EmptyStatement()
        return statement

    def _redirect_output(self, statement):
        """Handles output redirection for >, >>, and |.

        :param statement: ParsedString - subclass of str which also contains pyparsing ParseResults instance
        """
        if statement.parsed.pipeTo:
            self.kept_state = Statekeeper(self, ('stdout',))

            # Create a pipe with read and write sides
            read_fd, write_fd = os.pipe()

            # Make sure that self.poutput() expects unicode strings in Python 3 and byte strings in Python 2
            write_mode = 'w'
            read_mode = 'r'
            if six.PY2:
                write_mode = 'wb'
                read_mode = 'rb'

            # Open each side of the pipe and set stdout accordingly
            # noinspection PyTypeChecker
            self.stdout = io.open(write_fd, write_mode)
            self.redirecting = True
            # noinspection PyTypeChecker
            subproc_stdin = io.open(read_fd, read_mode)

            # We want Popen to raise an exception if it fails to open the process.  Thus we don't set shell to True.
            try:
                self.pipe_proc = subprocess.Popen(shlex.split(statement.parsed.pipeTo), stdin=subproc_stdin)
            except Exception as ex:
                # Restore stdout to what it was and close the pipe
                self.stdout.close()
                subproc_stdin.close()
                self.pipe_proc = None
                self.kept_state.restore()
                self.kept_state = None
                self.redirecting = False

                # Re-raise the exception
                raise ex
        elif statement.parsed.output:
            if (not statement.parsed.outputTo) and (not can_clip):
                raise EnvironmentError('Cannot redirect to paste buffer; install ``xclip`` and re-run to enable')
            self.kept_state = Statekeeper(self, ('stdout',))
            self.kept_sys = Statekeeper(sys, ('stdout',))
            self.redirecting = True
            if statement.parsed.outputTo:
                mode = 'w'
                if statement.parsed.output == 2 * self.redirector:
                    mode = 'a'
                sys.stdout = self.stdout = open(os.path.expanduser(statement.parsed.outputTo), mode)
            else:
                sys.stdout = self.stdout = tempfile.TemporaryFile(mode="w+")
                if statement.parsed.output == '>>':
                    self.poutput(get_paste_buffer())

    def _restore_output(self, statement):
        """Handles restoring state after output redirection as well as the actual pipe operation if present.

        :param statement: ParsedString - subclass of str which also contains pyparsing ParseResults instance
        """
        # If we have redirected output to a file or the clipboard or piped it to a shell command, then restore state
        if self.kept_state is not None:
            # If we redirected output to the clipboard
            if statement.parsed.output and not statement.parsed.outputTo:
                self.stdout.seek(0)
                write_to_paste_buffer(self.stdout.read())

            try:
                # Close the file or pipe that stdout was redirected to
                self.stdout.close()
            except BROKEN_PIPE_ERROR:
                pass
            finally:
                # Restore self.stdout
                self.kept_state.restore()
                self.kept_state = None

            # If we were piping output to a shell command, then close the subprocess the shell command was running in
            if self.pipe_proc is not None:
                self.pipe_proc.communicate()
                self.pipe_proc = None

        # Restore sys.stdout if need be
        if self.kept_sys is not None:
            self.kept_sys.restore()
            self.kept_sys = None

        self.redirecting = False

    def _func_named(self, arg):
        """Gets the method name associated with a given command.

        :param arg: str - command to look up method name which implements it
        :return: str - method name which implements the given command
        """
        result = None
        target = 'do_' + arg
        if target in dir(self):
            result = target
        return result

    def onecmd(self, line):
        """ This executes the actual do_* method for a command.

        If the command provided doesn't exist, then it executes _default() instead.

        :param line: ParsedString - subclass of string including the pyparsing ParseResults
        :return: bool - a flag indicating whether the interpretation of commands should stop
        """
        statement = self.parser_manager.parsed(line)
        funcname = self._func_named(statement.parsed.command)
        if not funcname:
            return self.default(statement)

        # Since we have a valid command store it in the history
        if statement.parsed.command not in self.excludeFromHistory:
            self.history.append(statement.parsed.raw)

        try:
            func = getattr(self, funcname)
        except AttributeError:
            return self.default(statement)

        stop = func(statement)
        return stop

    def default(self, statement):
        """Executed when the command given isn't a recognized command implemented by a do_* method.

        :param statement: ParsedString - subclass of string including the pyparsing ParseResults
        :return:
        """
        arg = statement.full_parsed_statement()
        if self.default_to_shell:
            result = os.system(arg)
            # If os.system() succeeded, then don't print warning about unknown command
            if not result:
                return

        # Print out a message stating this is an unknown command
        self.poutput('*** Unknown syntax: {}\n'.format(arg))

    @staticmethod
    def _surround_ansi_escapes(prompt, start="\x01", end="\x02"):
        """Overcome bug in GNU Readline in relation to calculation of prompt length in presence of ANSI escape codes.

        :param prompt: str - original prompt
        :param start: str - start code to tell GNU Readline about beginning of invisible characters
        :param end: str - end code to tell GNU Readline about end of invisible characters
        :return: str - prompt safe to pass to GNU Readline
        """
        # Windows terminals don't use ANSI escape codes and Windows readline isn't based on GNU Readline
        if sys.platform == "win32":
            return prompt

        escaped = False
        result = ""

        for c in prompt:
            if c == "\x1b" and not escaped:
                result += start + c
                escaped = True
            elif c.isalpha() and escaped:
                result += c + end
                escaped = False
            else:
                result += c

        return result

    def pseudo_raw_input(self, prompt):
        """
        began life as a copy of cmd's cmdloop; like raw_input but

        - accounts for changed stdin, stdout
        - if input is a pipe (instead of a tty), look at self.echo
          to decide whether to print the prompt and the input
        """

        # Deal with the vagaries of readline and ANSI escape codes
        safe_prompt = self._surround_ansi_escapes(prompt)

        if self.use_rawinput:
            try:
                if sys.stdin.isatty():
                    line = sm.input(safe_prompt)
                else:
                    line = sm.input()
                    if self.echo:
                        sys.stdout.write('{}{}\n'.format(safe_prompt, line))
            except EOFError:
                line = 'eof'
        else:
            if self.stdin.isatty():
                # on a tty, print the prompt first, then read the line
                self.poutput(safe_prompt, end='')
                self.stdout.flush()
                line = self.stdin.readline()
                if len(line) == 0:
                    line = 'eof'
            else:
                # we are reading from a pipe, read the line to see if there is
                # anything there, if so, then decide whether to print the
                # prompt or not
                line = self.stdin.readline()
                if len(line):
                    # we read something, output the prompt and the something
                    if self.echo:
                        self.poutput('{}{}'.format(safe_prompt, line))
                else:
                    line = 'eof'
        return line.strip()

    def _cmdloop(self):
        """Repeatedly issue a prompt, accept input, parse an initial prefix
        off the received input, and dispatch to action methods, passing them
        the remainder of the line as argument.

        This serves the same role as cmd.cmdloop().

        :return: bool - True implies the entire application should exit.
        """
        # An almost perfect copy from Cmd; however, the pseudo_raw_input portion
        # has been split out so that it can be called separately
        if self.use_rawinput and self.completekey:
            try:
                self.old_completer = readline.get_completer()
                self.old_delims = readline.get_completer_delims()
                readline.set_completer(self.complete)
                # Don't treat "-" as a readline delimiter since it is commonly used in filesystem paths
                readline.set_completer_delims(self.old_delims.replace('-', ''))
                readline.parse_and_bind(self.completekey + ": complete")
            except NameError:
                pass
        stop = None
        try:
            while not stop:
                if self.cmdqueue:
                    # Run command out of cmdqueue if nonempty (populated by load command or commands at invocation)
                    line = self.cmdqueue.pop(0)

                    if self.echo and line != 'eos':
                        self.poutput('{}{}'.format(self.prompt, line))
                else:
                    # Otherwise, read a command from stdin
                    if not self.quit_on_sigint:
                        try:
                            line = self.pseudo_raw_input(self.prompt)
                        except KeyboardInterrupt:
                            self.poutput('^C')
                            line = ''
                    else:
                        line = self.pseudo_raw_input(self.prompt)

                # Run the command along with all associated pre and post hooks
                stop = self.onecmd_plus_hooks(line)
        finally:
            if self.use_rawinput and self.completekey:
                try:
                    readline.set_completer(self.old_completer)
                    readline.set_completer_delims(self.old_delims)
                except NameError:
                    pass

            # Need to set empty list this way because Python 2 doesn't support the clear() method on lists
            self.cmdqueue = []
            self._script_dir = []

            return stop

    @with_argument_list
    def do_alias(self, arglist):
        """Define or display aliases

Usage:  Usage: alias [<name> <value>]
    Where:
        name - name of the alias being added or edited
        value - what the alias will be resolved to
                this can contain spaces and does not need to be quoted

    Without arguments, `alias' prints a list of all aliases in a resuable form

    Example: alias ls !ls -lF
"""
        # If no args were given, then print a list of current aliases
        if len(arglist) == 0:
            for cur_alias in self.aliases:
                self.poutput("alias {} {}".format(cur_alias, self.aliases[cur_alias]))

        # The user is creating an alias
        elif len(arglist) >= 2:
            name = arglist[0]
            value = ' '.join(arglist[1:])

            # Make sure the alias does not match an existing command
            cmd_func = self._func_named(name)
            if cmd_func is not None:
                self.perror("Alias names cannot match an existing command: {!r}".format(name), traceback_war=False)
                return

            # Check for a valid name
            for cur_char in name:
                if cur_char not in self.identchars:
                    self.perror("Alias names can only contain the following characters: {}".format(self.identchars),
                                traceback_war=False)
                    return

            # Set the alias
            self.aliases[name] = value
            self.poutput("Alias created")

        else:
            self.do_help('alias')

    def complete_alias(self, text, line, begidx, endidx):
        """ Tab completion for alias """
        index_dict = \
            {
                1: self.aliases,
                2: self.get_command_names()
            }
        return index_based_complete(text, line, begidx, endidx, index_dict, path_complete)

    @with_argument_list
    def do_unalias(self, arglist):
        """Unsets aliases

Usage:  Usage: unalias [-a] name [name ...]
    Where:
        name - name of the alias being unset

    Options:
        -a     remove all alias definitions
"""
        if len(arglist) == 0:
            self.do_help('unalias')

        if '-a' in arglist:
            self.aliases.clear()
            self.poutput("All aliases cleared")

        else:
            # Get rid of duplicates
            arglist = list(set(arglist))

            for cur_arg in arglist:
                if cur_arg in self.aliases:
                    del self.aliases[cur_arg]
                    self.poutput("Alias {!r} cleared".format(cur_arg))
                else:
                    self.perror("Alias {!r} does not exist".format(cur_arg), traceback_war=False)

    def complete_unalias(self, text, line, begidx, endidx):
        """ Tab completion for unalias """
        return basic_complete(text, line, begidx, endidx, self.aliases)

    @with_argument_list
    def do_help(self, arglist):
        """List available commands with "help" or detailed help with "help cmd"."""
        if arglist:
            # Getting help for a specific command
            funcname = self._func_named(arglist[0])
            if funcname:
                # Check to see if this function was decorated with an argparse ArgumentParser
                func = getattr(self, funcname)
                if func.__dict__.get('has_parser', False):
                    # Function has an argparser, so get help based on all the arguments in case there are sub-commands
                    new_arglist = arglist[1:]
                    new_arglist.append('-h')

                    # Temporarily redirect all argparse output to both sys.stdout and sys.stderr to self.stdout
                    with redirect_stdout(self.stdout):
                        with redirect_stderr(self.stdout):
                            func(new_arglist)
                else:
                    # No special behavior needed, delegate to cmd base class do_help()
                    cmd.Cmd.do_help(self, funcname[3:])
        else:
            # Show a menu of what commands help can be gotten for
            self._help_menu()

    def _help_menu(self):
        """Show a list of commands which help can be displayed for.
        """
        # Get a list of all method names
        names = self.get_names()

        # Remove any command names which are explicitly excluded from the help menu
        for name in self.exclude_from_help:
            if name in names:
                names.remove(name)

        cmds_doc = []
        cmds_undoc = []
        help_dict = {}
        for name in names:
            if name[:5] == 'help_':
                help_dict[name[5:]] = 1
        names.sort()
        # There can be duplicates if routines overridden
        prevname = ''
        for name in names:
            if name[:3] == 'do_':
                if name == prevname:
                    continue
                prevname = name
                command = name[3:]
                if command in help_dict:
                    cmds_doc.append(command)
                    del help_dict[command]
                elif getattr(self, name).__doc__:
                    cmds_doc.append(command)
                else:
                    cmds_undoc.append(command)
        self.poutput("%s\n" % str(self.doc_leader))
        self.print_topics(self.doc_header, cmds_doc, 15, 80)
        self.print_topics(self.misc_header, list(help_dict.keys()), 15, 80)
        self.print_topics(self.undoc_header, cmds_undoc, 15, 80)

    def do_shortcuts(self, _):
        """Lists shortcuts (aliases) available."""
        result = "\n".join('%s: %s' % (sc[0], sc[1]) for sc in sorted(self.shortcuts))
        self.poutput("Shortcuts for other commands:\n{}\n".format(result))

    def do_eof(self, _):
        """Called when <Ctrl>-D is pressed."""
        # End of script should not exit app, but <Ctrl>-D should.
        print('')  # Required for clearing line when exiting submenu
        return self._STOP_AND_EXIT

    def do_quit(self, _):
        """Exits this application."""
        self._should_quit = True
        return self._STOP_AND_EXIT

    def select(self, opts, prompt='Your choice? '):
        """Presents a numbered menu to the user.  Modelled after
           the bash shell's SELECT.  Returns the item chosen.

           Argument ``opts`` can be:

             | a single string -> will be split into one-word options
             | a list of strings -> will be offered as options
             | a list of tuples -> interpreted as (value, text), so
                                   that the return value can differ from
                                   the text advertised to the user """
        local_opts = opts
        if isinstance(opts, string_types):
            local_opts = list(zip(opts.split(), opts.split()))
        fulloptions = []
        for opt in local_opts:
            if isinstance(opt, string_types):
                fulloptions.append((opt, opt))
            else:
                try:
                    fulloptions.append((opt[0], opt[1]))
                except IndexError:
                    fulloptions.append((opt[0], opt[0]))
        for (idx, (value, text)) in enumerate(fulloptions):
            self.poutput('  %2d. %s\n' % (idx + 1, text))
        while True:
            response = sm.input(prompt)
            hlen = readline.get_current_history_length()
            if hlen >= 1 and response != '':
                readline.remove_history_item(hlen - 1)
            try:
                response = int(response)
                result = fulloptions[response - 1][0]
                break
            except (ValueError, IndexError):
                self.poutput("{!r} isn't a valid choice. Pick a number between 1 and {}:\n".format(response,
                                                                                                   len(fulloptions)))
        return result

    def cmdenvironment(self):
        """Get a summary report of read-only settings which the user cannot modify at runtime.

        :return: str - summary report of read-only settings which the user cannot modify at runtime
        """
        read_only_settings = """
        Commands may be terminated with: {}
        Arguments at invocation allowed: {}
        Output redirection and pipes allowed: {}
        Parsing of @options commands:
            Shell lexer mode for command argument splitting: {}
            Strip Quotes after splitting arguments: {}
            Argument type: {}
        """.format(str(self.terminators), self.allow_cli_args, self.allow_redirection,
                   "POSIX" if POSIX_SHLEX else "non-POSIX",
                   "True" if STRIP_QUOTES_FOR_NON_POSIX and not POSIX_SHLEX else "False",
                   "List of argument strings" if USE_ARG_LIST else "string of space-separated arguments")
        return read_only_settings

    def show(self, args, parameter):
        param = ''
        if parameter:
            param = parameter.strip().lower()
        result = {}
        maxlen = 0
        for p in self.settable:
            if (not param) or p.startswith(param):
                result[p] = '%s: %s' % (p, str(getattr(self, p)))
                maxlen = max(maxlen, len(result[p]))
        if result:
            for p in sorted(result):
                if args.long:
                    self.poutput('{} # {}'.format(result[p].ljust(maxlen), self.settable[p]))
                else:
                    self.poutput(result[p])

            # If user has requested to see all settings, also show read-only settings
            if args.all:
                self.poutput('\nRead only settings:{}'.format(self.cmdenvironment()))
        else:
            raise LookupError("Parameter '%s' not supported (type 'show' for list of parameters)." % param)

    set_parser = argparse.ArgumentParser()
    set_parser.add_argument('-a', '--all', action='store_true', help='display read-only settings as well')
    set_parser.add_argument('-l', '--long', action='store_true', help='describe function of parameter')
    set_parser.add_argument('settable', nargs='*', help='[param_name] [value]')

    @with_argparser(set_parser)
    def do_set(self, args):
        """Sets a settable parameter or shows current settings of parameters.

        Accepts abbreviated parameter names so long as there is no ambiguity.
        Call without arguments for a list of settable parameters with their values.
        """
        try:
            param_name, val = args.settable
            val = val.strip()
            param_name = param_name.strip().lower()
            if param_name not in self.settable:
                hits = [p for p in self.settable if p.startswith(param_name)]
                if len(hits) == 1:
                    param_name = hits[0]
                else:
                    return self.show(args, param_name)
            current_val = getattr(self, param_name)
            if (val[0] == val[-1]) and val[0] in ("'", '"'):
                val = val[1:-1]
            else:
                val = cast(current_val, val)
            setattr(self, param_name, val)
            self.poutput('%s - was: %s\nnow: %s\n' % (param_name, current_val, val))
            if current_val != val:
                try:
                    onchange_hook = getattr(self, '_onchange_%s' % param_name)
                    onchange_hook(old=current_val, new=val)
                except AttributeError:
                    pass
        except (ValueError, AttributeError):
            param = ''
            if args.settable:
                param = args.settable[0]
            self.show(args, param)

    def do_shell(self, command):
        """Execute a command as if at the OS prompt.

    Usage:  shell <command> [arguments]"""
        proc = subprocess.Popen(command, stdout=self.stdout, shell=True)
        proc.communicate()

    @staticmethod
    def _get_exes_in_path(starts_with, at_eol):
        """
        Called by complete_shell to get names of executables in a user's path

        :param starts_with: str - what the exes should start with
        :param at_eol: bool - tells if the user's cursor is at the end of the command line
        :return: List[str] - a list of possible tab completions
        """

        # Purposely don't match any executable containing wildcards
        wildcards = ['*', '?']
        for wildcard in wildcards:
            if wildcard in starts_with:
                return []

        # Get a list of every directory in the PATH environment variable and ignore symbolic links
        paths = [p for p in os.getenv('PATH').split(os.path.pathsep) if not os.path.islink(p)]

        # Use a set to store exe names since there can be duplicates
        exes = set()

        # Find every executable file in the user's path that matches the pattern
        for path in paths:
            full_path = os.path.join(path, starts_with)
            matches = [f for f in glob.glob(full_path + '*') if os.path.isfile(f) and os.access(f, os.X_OK)]

            for match in matches:
                exes.add(os.path.basename(match))

        # Sort the exes alphabetically
        results = list(exes)
        results.sort()

        # If there is a single completion and we are at end of the line, then add a space at the end for convenience
        if len(results) == 1 and at_eol:
            results[0] += ' '

        return results

    def complete_shell(self, text, line, begidx, endidx):
        """Handles tab completion of executable commands and local file system paths for the shell command

        :param text: str - the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: str - the current input line with leading whitespace removed
        :param begidx: int - the beginning index of the prefix text
        :param endidx: int - the ending index of the prefix text
        :return: List[str] - a list of possible tab completions
        """

        # Get all tokens prior to token being completed
        try:
            prev_space_index = max(line.rfind(' ', 0, begidx), 0)
            tokens = shlex.split(line[:prev_space_index], posix=POSIX_SHLEX)
        except ValueError:
            # Invalid syntax for shlex (Probably due to missing closing quote)
            return []

        if len(tokens) == 0:
            return []

        # Check if we are still completing the shell command
        if len(tokens) == 1:

            # Readline places begidx after ~ and path separators (/) so we need to get the whole token
            # and see if it begins with a possible path in case we need to do path completion
            # to find the shell command executables
            cmd_token = line[prev_space_index + 1:begidx + 1]

            # Don't tab complete anything if no shell command has been started
            if len(cmd_token) == 0:
                return []

            # Look for path characters in the token
            if not (cmd_token.startswith('~') or os.path.sep in cmd_token):
                # No path characters are in this token, it is OK to try shell command completion.
                command_completions = self._get_exes_in_path(text, endidx == len(line))

                if command_completions:
                    return command_completions

            # If we have no results, try path completion to find the shell commands
            return path_complete(text, line, begidx, endidx, dir_exe_only=True)

        # We are past the shell command, so do path completion
        else:
            return path_complete(text, line, begidx, endidx)

    def cmd_with_subs_completer(self, text, line, begidx, endidx, base):
        """
        This is a function provided for convenience to those who want an easy way to add
        tab completion to functions that implement subcommands. By setting this as the
        completer of the base command function, the correct completer for the chosen subcommand
        will be called.

        The use of this function requires a particular naming scheme.
        Example:
            A command called print has 2 subcommands [names, addresses]
            The tab-completion functions for the subcommands must be called:
            names      -> complete_print_names
            addresses  -> complete_print_addresses

            To make sure these functions get called, set the tab-completer for the print function
            in a similar fashion to what follows where base is the name of the root command (print)

            complete_print = functools.partialmethod(cmd2.Cmd.cmd_with_subs_completer, base='print')

            When the subcommand's completer is called, this function will have stripped off all content from the
            beginning of he command line before the subcommand, meaning the line parameter always starts with the
            subcommand name and the index parameters reflect this change.

            For instance, the command "print names -d 2" becomes "names -d 2"
            begidx and endidx are incremented accordingly

        :param text: str - the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: str - the current input line with leading whitespace removed
        :param begidx: int - the beginning index of the prefix text
        :param endidx: int - the ending index of the prefix text
        :param base: str - the name of the base command that owns the subcommands
        :return: List[str] - a list of possible tab completions
        """

        # The subcommand is the token at index 1 in the command line
        subcmd_index = 1

        # Get all tokens prior to token being completed
        try:
            prev_space_index = max(line.rfind(' ', 0, begidx), 0)
            tokens = shlex.split(line[:prev_space_index], posix=POSIX_SHLEX)
        except ValueError:
            # Invalid syntax for shlex (Probably due to missing closing quote)
            return []

        completions = []

        # Get the index of the token being completed
        index = len(tokens)

        # If the token being completed is past the subcommand name, then do subcommand specific tab-completion
        if index > subcmd_index:

            # Get the subcommand name
            subcommand = tokens[subcmd_index]

            # Find the offset into line where the subcommand name begins
            subcmd_start = 0
            for cur_index in range(0, subcmd_index + 1):
                cur_token = tokens[cur_index]
                subcmd_start = line.find(cur_token, subcmd_start)

                if cur_index != subcmd_index:
                    subcmd_start += len(cur_token)

            # Strip off everything before subcommand name
            orig_line = line
            line = line[subcmd_start:]

            # Update the indexes
            diff = len(orig_line) - len(line)
            begidx -= diff
            endidx -= diff

            # Call the subcommand specific completer
            completer = 'complete_{}_{}'.format(base, subcommand)
            try:
                compfunc = getattr(self, completer)
                completions = compfunc(text, line, begidx, endidx)
            except AttributeError:
                pass

        return completions

    # noinspection PyBroadException
    def do_py(self, arg):
        """
        py <command>: Executes a Python command.
        py: Enters interactive Python mode.
        End with ``Ctrl-D`` (Unix) / ``Ctrl-Z`` (Windows), ``quit()``, '`exit()``.
        Non-python commands can be issued with ``cmd("your command")``.
        Run python code from external script files with ``run("script.py")``
        """
        if self._in_py:
            self.perror("Recursively entering interactive Python consoles is not allowed.", traceback_war=False)
            return
        self._in_py = True

        try:
            self.pystate['self'] = self
            arg = arg.strip()

            # Support the run command even if called prior to invoking an interactive interpreter
            def run(filename):
                """Run a Python script file in the interactive console.

                :param filename: str - filename of *.py script file to run
                """
                try:
                    with open(filename) as f:
                        interp.runcode(f.read())
                except IOError as e:
                    self.perror(e)

            def onecmd_plus_hooks(cmd_plus_args):
                """Run a cmd2.Cmd command from a Python script or the interactive Python console.

                :param cmd_plus_args: str - command line including command and arguments to run
                :return: bool - True if cmdloop() should exit once leaving the interactive Python console
                """
                return self.onecmd_plus_hooks(cmd_plus_args + '\n')

            self.pystate['run'] = run
            self.pystate['cmd'] = onecmd_plus_hooks

            localvars = (self.locals_in_py and self.pystate) or {}
            interp = InteractiveConsole(locals=localvars)
            interp.runcode('import sys, os;sys.path.insert(0, os.getcwd())')

            if arg:
                interp.runcode(arg)
            else:
                # noinspection PyShadowingBuiltins
                def quit():
                    """Function callable from the interactive Python console to exit that environment"""
                    raise EmbeddedConsoleExit

                self.pystate['quit'] = quit
                self.pystate['exit'] = quit

                keepstate = None
                try:
                    cprt = 'Type "help", "copyright", "credits" or "license" for more information.'
                    keepstate = Statekeeper(sys, ('stdin', 'stdout'))
                    sys.stdout = self.stdout
                    sys.stdin = self.stdin
                    interp.interact(banner="Python %s on %s\n%s\n(%s)\n%s" %
                                           (sys.version, sys.platform, cprt, self.__class__.__name__,
                                            self.do_py.__doc__))
                except EmbeddedConsoleExit:
                    pass
                if keepstate is not None:
                    keepstate.restore()
        except Exception:
            pass
        finally:
            self._in_py = False
        return self._should_quit

    @with_argument_list
    def do_pyscript(self, arglist):
        """\nRuns a python script file inside the console

    Usage: pyscript <script_path> [script_arguments]

Console commands can be executed inside this script with cmd("your command")
However, you cannot run nested "py" or "pyscript" commands from within this script
Paths or arguments that contain spaces must be enclosed in quotes
"""
        if not arglist:
            self.perror("pyscript command requires at least 1 argument ...", traceback_war=False)
            self.do_help('pyscript')
            return

        # Get the absolute path of the script
        script_path = os.path.expanduser(arglist[0])

        # Save current command line arguments
        orig_args = sys.argv

        # Overwrite sys.argv to allow the script to take command line arguments
        sys.argv = [script_path]
        sys.argv.extend(arglist[1:])

        # Run the script - use repr formatting to escape things which need to be escaped to prevent issues on Windows
        self.do_py("run({!r})".format(script_path))

        # Restore command line arguments to original state
        sys.argv = orig_args

    # Enable tab-completion for pyscript command
    complete_pyscript = functools.partial(path_complete)

    # Only include the do_ipy() method if IPython is available on the system
    if ipython_available:
        # noinspection PyMethodMayBeStatic,PyUnusedLocal
        def do_ipy(self, arg):
            """Enters an interactive IPython shell.

            Run python code from external files with ``run filename.py``
            End with ``Ctrl-D`` (Unix) / ``Ctrl-Z`` (Windows), ``quit()``, '`exit()``.
            """
            banner = 'Entering an embedded IPython shell type quit() or <Ctrl>-d to exit ...'
            exit_msg = 'Leaving IPython, back to {}'.format(sys.argv[0])
            embed(banner1=banner, exit_msg=exit_msg)

    history_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    history_parser_group = history_parser.add_mutually_exclusive_group()
    history_parser_group.add_argument('-r', '--run', action='store_true', help='run selected history items')
    history_parser_group.add_argument('-e', '--edit', action='store_true',
                                      help='edit and then run selected history items')
    history_parser_group.add_argument('-s', '--script', action='store_true', help='script format; no separation lines')
    history_parser_group.add_argument('-o', '--output-file', metavar='FILE', help='output commands to a script file')
    history_parser_group.add_argument('-t', '--transcript', help='output commands and results to a transcript file')
    _history_arg_help = """empty               all history items
a                   one history item by number
a..b, a:b, a:, ..b  items by indices (inclusive)
[string]            items containing string
/regex/             items matching regular expression"""
    history_parser.add_argument('arg', nargs='?', help=_history_arg_help)

    @with_argparser(history_parser)
    def do_history(self, args):
        """View, run, edit, and save previously entered commands."""
        # If an argument was supplied, then retrieve partial contents of the history
        cowardly_refuse_to_run = False
        if args.arg:
            # If a character indicating a slice is present, retrieve
            # a slice of the history
            arg = args.arg
            if '..' in arg or ':' in arg:
                try:
                    # Get a slice of history
                    history = self.history.span(arg)
                except IndexError:
                    history = self.history.get(arg)
            else:
                # Get item(s) from history by index or string search
                history = self.history.get(arg)
        else:
            # If no arg given, then retrieve the entire history
            cowardly_refuse_to_run = True
            # Get a copy of the history so it doesn't get mutated while we are using it
            history = self.history[:]

        if args.run:
            if cowardly_refuse_to_run:
                self.perror("Cowardly refusing to run all previously entered commands.", traceback_war=False)
                self.perror("If this is what you want to do, specify '1:' as the range of history.",
                            traceback_war=False)
            else:
                for runme in history:
                    self.pfeedback(runme)
                    if runme:
                        self.onecmd_plus_hooks(runme)
        elif args.edit:
            fd, fname = tempfile.mkstemp(suffix='.txt', text=True)
            with os.fdopen(fd, 'w') as fobj:
                for command in history:
                    fobj.write('{}\n'.format(command))
            try:
                os.system('"{}" "{}"'.format(self.editor, fname))
                self.do_load(fname)
            except Exception:
                raise
            finally:
                os.remove(fname)
        elif args.output_file:
            try:
                with open(os.path.expanduser(args.output_file), 'w') as fobj:
                    for command in history:
                        fobj.write('{}\n'.format(command))
                plural = 's' if len(history) > 1 else ''
                self.pfeedback('{} command{} saved to {}'.format(len(history), plural, args.output_file))
            except Exception as e:
                self.perror('Saving {!r} - {}'.format(args.output_file, e), traceback_war=False)
        elif args.transcript:
            # Make sure echo is on so commands print to standard out
            saved_echo = self.echo
            self.echo = True

            # Redirect stdout to the transcript file
            saved_self_stdout = self.stdout
            self.stdout = open(args.transcript, 'w')

            # Run all of the commands in the history with output redirected to transcript and echo on
            self.runcmds_plus_hooks(history)

            # Restore stdout to its original state
            self.stdout.close()
            self.stdout = saved_self_stdout

            # Set echo back to its original state
            self.echo = saved_echo

            # Post-process the file to escape un-escaped "/" regex escapes
            with open(args.transcript, 'r') as fin:
                data = fin.read()
            post_processed_data = data.replace('/', '\/')
            with open(args.transcript, 'w') as fout:
                fout.write(post_processed_data)

            plural = 's' if len(history) > 1 else ''
            self.pfeedback('{} command{} and outputs saved to transcript file {!r}'.format(len(history), plural,
                                                                                           args.transcript))
        else:
            # Display the history items retrieved
            for hi in history:
                if args.script:
                    self.poutput(hi)
                else:
                    self.poutput(hi.pr())

    @with_argument_list
    def do_edit(self, arglist):
        """Edit a file in a text editor.

Usage:  edit [file_path]
    Where:
        * file_path - path to a file to open in editor

The editor used is determined by the ``editor`` settable parameter.
"set editor (program-name)" to change or set the EDITOR environment variable.
"""
        if not self.editor:
            raise EnvironmentError("Please use 'set editor' to specify your text editing program of choice.")
        filename = arglist[0] if arglist else ''
        if filename:
            os.system('"{}" "{}"'.format(self.editor, filename))
        else:
            os.system('"{}"'.format(self.editor))

    # Enable tab-completion for edit command
    complete_edit = functools.partial(path_complete)

    @property
    def _current_script_dir(self):
        """Accessor to get the current script directory from the _script_dir LIFO queue."""
        if self._script_dir:
            return self._script_dir[-1]
        else:
            return None

    @with_argument_list
    def do__relative_load(self, arglist):
        """Runs commands in script file that is encoded as either ASCII or UTF-8 text.

    Usage:  _relative_load <file_path>

    optional argument:
    file_path   a file path pointing to a script

Script should contain one command per line, just like command would be typed in console.

If this is called from within an already-running script, the filename will be interpreted
relative to the already-running script's directory.

NOTE: This command is intended to only be used within text file scripts.
        """
        # If arg is None or arg is an empty string this is an error
        if not arglist:
            self.perror('_relative_load command requires a file path:', traceback_war=False)
            return

        file_path = arglist[0].strip()
        # NOTE: Relative path is an absolute path, it is just relative to the current script directory
        relative_path = os.path.join(self._current_script_dir or '', file_path)
        self.do_load(relative_path)

    def do_eos(self, _):
        """Handles cleanup when a script has finished executing."""
        if self._script_dir:
            self._script_dir.pop()

    @with_argument_list
    def do_load(self, arglist):
        """Runs commands in script file that is encoded as either ASCII or UTF-8 text.

    Usage:  load <file_path>

    * file_path - a file path pointing to a script

Script should contain one command per line, just like command would be typed in console.
        """
        # If arg is None or arg is an empty string this is an error
        if not arglist:
            self.perror('load command requires a file path:', traceback_war=False)
            return

        file_path = arglist[0].strip()
        expanded_path = os.path.abspath(os.path.expanduser(file_path))

        # Make sure expanded_path points to a file
        if not os.path.isfile(expanded_path):
            self.perror('{} does not exist or is not a file'.format(expanded_path), traceback_war=False)
            return

        # Make sure the file is not empty
        if os.path.getsize(expanded_path) == 0:
            self.perror('{} is empty'.format(expanded_path), traceback_war=False)
            return

        # Make sure the file is ASCII or UTF-8 encoded text
        if not self.is_text_file(expanded_path):
            self.perror('{} is not an ASCII or UTF-8 encoded text file'.format(expanded_path), traceback_war=False)
            return

        try:
            # Read all lines of the script and insert into the head of the
            # command queue. Add an "end of script (eos)" command to cleanup the
            # self._script_dir list when done. Specify file encoding in Python
            # 3, but Python 2 doesn't allow that argument to open().
            kwargs = {'encoding': 'utf-8'} if six.PY3 else {}
            with open(expanded_path, **kwargs) as target:
                self.cmdqueue = target.read().splitlines() + ['eos'] + self.cmdqueue
        except IOError as e:
            self.perror('Problem accessing script from {}:\n{}'.format(expanded_path, e))
            return

        self._script_dir.append(os.path.dirname(expanded_path))

    # Enable tab-completion for load command
    complete_load = functools.partial(path_complete)

    @staticmethod
    def is_text_file(file_path):
        """
        Returns if a file contains only ASCII or UTF-8 encoded text
        :param file_path: path to the file being checked
        """
        expanded_path = os.path.abspath(os.path.expanduser(file_path.strip()))
        valid_text_file = False

        # Check if the file is ASCII
        try:
            with codecs.open(expanded_path, encoding='ascii', errors='strict') as f:
                # Make sure the file has at least one line of text
                # noinspection PyUnusedLocal
                if sum(1 for line in f) > 0:
                    valid_text_file = True
        except IOError:
            pass
        except UnicodeDecodeError:
            # The file is not ASCII. Check if it is UTF-8.
            try:
                with codecs.open(expanded_path, encoding='utf-8', errors='strict') as f:
                    # Make sure the file has at least one line of text
                    # noinspection PyUnusedLocal
                    if sum(1 for line in f) > 0:
                        valid_text_file = True
            except IOError:
                pass
            except UnicodeDecodeError:
                # Not UTF-8
                pass

        return valid_text_file

    def run_transcript_tests(self, callargs):
        """Runs transcript tests for provided file(s).

        This is called when either -t is provided on the command line or the transcript_files argument is provided
        during construction of the cmd2.Cmd instance.

        :param callargs: List[str] - list of transcript test file names
        """
        class TestMyAppCase(Cmd2TestCase):
            cmdapp = self

        self.__class__.testfiles = callargs
        sys.argv = [sys.argv[0]]  # the --test argument upsets unittest.main()
        testcase = TestMyAppCase()
        runner = unittest.TextTestRunner()
        runner.run(testcase)

    def cmdloop(self, intro=None):
        """This is an outer wrapper around _cmdloop() which deals with extra features provided by cmd2.

        _cmdloop() provides the main loop equivalent to cmd.cmdloop().  This is a wrapper around that which deals with
        the following extra features provided by cmd2:
        - commands at invocation
        - transcript testing
        - intro banner

        :param intro: str - if provided this overrides self.intro and serves as the intro banner printed once at start
        """
        if self.allow_cli_args:
            parser = optparse.OptionParser()
            parser.add_option('-t', '--test', dest='test',
                              action="store_true",
                              help='Test against transcript(s) in FILE (wildcards OK)')
            (callopts, callargs) = parser.parse_args()

            # If transcript testing was called for, use other arguments as transcript files
            if callopts.test:
                self._transcript_files = callargs

            # If commands were supplied at invocation, then add them to the command queue
            if callargs:
                self.cmdqueue.extend(callargs)

        # Always run the preloop first
        self.preloop()

        # If transcript-based regression testing was requested, then do that instead of the main loop
        if self._transcript_files is not None:
            self.run_transcript_tests(self._transcript_files)
        else:
            # If an intro was supplied in the method call, allow it to override the default
            if intro is not None:
                self.intro = intro

            # Print the intro, if there is one, right after the preloop
            if self.intro is not None:
                self.poutput(str(self.intro) + "\n")

            # And then call _cmdloop() to enter the main loop
            self._cmdloop()

        # Run the postloop() no matter what
        self.postloop()


# noinspection PyPep8Naming
class ParserManager:
    """
    Class which encapsulates all of the pyparsing parser functionality for cmd2 in a single location.
    """
    def __init__(self, redirector, terminators, multilineCommands, legalChars, commentGrammars, commentInProgress,
                 blankLinesAllowed, prefixParser, preparse, postparse, aliases, shortcuts):
        """Creates and uses parsers for user input according to app's parameters."""

        self.commentGrammars = commentGrammars
        self.preparse = preparse
        self.postparse = postparse
        self.aliases = aliases
        self.shortcuts = shortcuts

        self.main_parser = self._build_main_parser(redirector=redirector, terminators=terminators,
                                                   multilineCommands=multilineCommands, legalChars=legalChars,
                                                   commentInProgress=commentInProgress,
                                                   blankLinesAllowed=blankLinesAllowed, prefixParser=prefixParser)
        self.input_source_parser = self._build_input_source_parser(legalChars=legalChars,
                                                                   commentInProgress=commentInProgress)

    def _build_main_parser(self, redirector, terminators, multilineCommands, legalChars, commentInProgress,
                           blankLinesAllowed, prefixParser):
        """Builds a PyParsing parser for interpreting user commands."""

        # Build several parsing components that are eventually compiled into overall parser
        output_destination_parser = (pyparsing.Literal(redirector * 2) |
                                     (pyparsing.WordStart() + redirector) |
                                     pyparsing.Regex('[^=]' + redirector))('output')

        terminator_parser = pyparsing.Or(
            [(hasattr(t, 'parseString') and t) or pyparsing.Literal(t) for t in terminators])('terminator')
        string_end = pyparsing.stringEnd ^ '\nEOF'
        multilineCommand = pyparsing.Or(
            [pyparsing.Keyword(c, caseless=False) for c in multilineCommands])('multilineCommand')
        oneline_command = (~multilineCommand + pyparsing.Word(legalChars))('command')
        pipe = pyparsing.Keyword('|', identChars='|')
        do_not_parse = self.commentGrammars | commentInProgress | pyparsing.quotedString
        after_elements = \
            pyparsing.Optional(pipe + pyparsing.SkipTo(output_destination_parser ^ string_end,
                                                       ignore=do_not_parse)('pipeTo')) + \
            pyparsing.Optional(output_destination_parser +
                               pyparsing.SkipTo(string_end,
                                                ignore=do_not_parse).setParseAction(lambda x: x[0].strip())('outputTo'))

        multilineCommand.setParseAction(lambda x: x[0])
        oneline_command.setParseAction(lambda x: x[0])

        if blankLinesAllowed:
            blankLineTerminationParser = pyparsing.NoMatch
        else:
            blankLineTerminator = (pyparsing.lineEnd + pyparsing.lineEnd)('terminator')
            blankLineTerminator.setResultsName('terminator')
            blankLineTerminationParser = ((multilineCommand ^ oneline_command) +
                                          pyparsing.SkipTo(blankLineTerminator, ignore=do_not_parse).setParseAction(
                                                   lambda x: x[0].strip())('args') + blankLineTerminator)('statement')

        multilineParser = (((multilineCommand ^ oneline_command) +
                            pyparsing.SkipTo(terminator_parser,
                                             ignore=do_not_parse).setParseAction(lambda x: x[0].strip())('args') +
                            terminator_parser)('statement') +
                           pyparsing.SkipTo(output_destination_parser ^ pipe ^ string_end,
                                            ignore=do_not_parse).setParseAction(lambda x: x[0].strip())('suffix') +
                           after_elements)
        multilineParser.ignore(commentInProgress)

        singleLineParser = ((oneline_command +
                             pyparsing.SkipTo(terminator_parser ^ string_end ^ pipe ^ output_destination_parser,
                                              ignore=do_not_parse).setParseAction(
                                 lambda x: x[0].strip())('args'))('statement') +
                            pyparsing.Optional(terminator_parser) + after_elements)

        blankLineTerminationParser = blankLineTerminationParser.setResultsName('statement')

        parser = prefixParser + (
            string_end |
            multilineParser |
            singleLineParser |
            blankLineTerminationParser |
            multilineCommand + pyparsing.SkipTo(string_end, ignore=do_not_parse)
        )
        parser.ignore(self.commentGrammars)
        return parser

    @staticmethod
    def _build_input_source_parser(legalChars, commentInProgress):
        """Builds a PyParsing parser for alternate user input sources (from file, pipe, etc.)"""

        input_mark = pyparsing.Literal('<')
        input_mark.setParseAction(lambda x: '')
        file_name = pyparsing.Word(legalChars + '/\\')
        input_from = file_name('inputFrom')
        input_from.setParseAction(replace_with_file_contents)
        # a not-entirely-satisfactory way of distinguishing < as in "import from" from <
        # as in "lesser than"
        inputParser = input_mark + pyparsing.Optional(input_from) + pyparsing.Optional('>') + \
            pyparsing.Optional(file_name) + (pyparsing.stringEnd | '|')
        inputParser.ignore(commentInProgress)
        return inputParser

    def parsed(self, raw):
        """ This function is where the actual parsing of each line occurs.

        :param raw: str - the line of text as it was entered
        :return: ParsedString - custom subclass of str with extra attributes
        """
        if isinstance(raw, ParsedString):
            p = raw
        else:
            # preparse is an overridable hook; default makes no changes
            s = self.preparse(raw)
            s = self.input_source_parser.transformString(s.lstrip())
            s = self.commentGrammars.transformString(s)

            # Handle aliases
            for cur_alias in self.aliases:
                if s == cur_alias or s.startswith(cur_alias + ' '):
                    s = s.replace(cur_alias, self.aliases[cur_alias], 1)
                    break

            for (shortcut, expansion) in self.shortcuts:
                if s.startswith(shortcut):
                    s = s.replace(shortcut, expansion + ' ', 1)
                    break
            try:
                result = self.main_parser.parseString(s)
            except pyparsing.ParseException:
                # If we have a parsing failure, treat it is an empty command and move to next prompt
                result = self.main_parser.parseString('')
            result['raw'] = raw
            result['command'] = result.multilineCommand or result.command
            result = self.postparse(result)
            p = ParsedString(result.args)
            p.parsed = result
            p.parser = self.parsed
        return p


class HistoryItem(str):
    """Class used to represent an item in the History list.

    Thin wrapper around str class which adds a custom format for printing. It
    also keeps track of its index in the list as well as a lowercase
    representation of itself for convenience/efficiency.

    """
    listformat = '-------------------------[{}]\n{}\n'

    # noinspection PyUnusedLocal
    def __init__(self, instr):
        str.__init__(self)
        self.lowercase = self.lower()
        self.idx = None

    def pr(self):
        """Represent a HistoryItem in a pretty fashion suitable for printing.

        :return: str - pretty print string version of a HistoryItem
        """
        return self.listformat.format(self.idx, str(self).rstrip())


class History(list):
    """ A list of HistoryItems that knows how to respond to user requests. """

    # noinspection PyMethodMayBeStatic
    def _zero_based_index(self, onebased):
        result = onebased
        if result > 0:
            result -= 1
        return result

    def _to_index(self, raw):
        if raw:
            result = self._zero_based_index(int(raw))
        else:
            result = None
        return result

    spanpattern = re.compile(r'^\s*(?P<start>-?\d+)?\s*(?P<separator>:|(\.{2,}))?\s*(?P<end>-?\d+)?\s*$')

    def span(self, raw):
        """Parses the input string search for a span pattern and if if found, returns a slice from the History list.

        :param raw: str - string potentially containing a span of the forms a..b, a:b, a:, ..b
        :return: List[HistoryItem] - slice from the History list
        """
        if raw.lower() in ('*', '-', 'all'):
            raw = ':'
        results = self.spanpattern.search(raw)
        if not results:
            raise IndexError
        if not results.group('separator'):
            return [self[self._to_index(results.group('start'))]]
        start = self._to_index(results.group('start')) or 0  # Ensure start is not None
        end = self._to_index(results.group('end'))
        reverse = False
        if end is not None:
            if end < start:
                (start, end) = (end, start)
                reverse = True
            end += 1
        result = self[start:end]
        if reverse:
            result.reverse()
        return result

    rangePattern = re.compile(r'^\s*(?P<start>[\d]+)?\s*-\s*(?P<end>[\d]+)?\s*$')

    def append(self, new):
        """Append a HistoryItem to end of the History list

        :param new: str - command line to convert to HistoryItem and add to the end of the History list
        """
        new = HistoryItem(new)
        list.append(self, new)
        new.idx = len(self)

    def get(self, getme=None):
        """Get an item or items from the History list using 1-based indexing.

        :param getme: int or str - item(s) to get - either an integer index or string to search for
        :return: List[str] - list of HistoryItems matching the retrieval criteria
        """
        if not getme:
            return self
        try:
            getme = int(getme)
            if getme < 0:
                return self[:(-1 * getme)]
            else:
                return [self[getme - 1]]
        except IndexError:
            return []
        except ValueError:
            range_result = self.rangePattern.search(getme)
            if range_result:
                start = range_result.group('start') or None
                end = range_result.group('start') or None
                if start:
                    start = int(start) - 1
                if end:
                    end = int(end)
                return self[start:end]

            # noinspection PyUnresolvedReferences
            getme = getme.strip()

            if getme.startswith(r'/') and getme.endswith(r'/'):
                finder = re.compile(getme[1:-1], re.DOTALL | re.MULTILINE | re.IGNORECASE)

                def isin(hi):
                    """Listcomp filter function for doing a regular expression search of History.

                    :param hi: HistoryItem
                    :return: bool - True if search matches
                    """
                    return finder.search(hi)
            else:
                def isin(hi):
                    """Listcomp filter function for doing a case-insensitive string search of History.

                    :param hi: HistoryItem
                    :return: bool - True if search matches
                    """
                    return getme.lower() in hi.lowercase
            return [itm for itm in self if isin(itm)]


def cast(current, new):
    """Tries to force a new value into the same type as the current when trying to set the value for a parameter.

    :param current: current value for the parameter, type varies
    :param new: str - new value
    :return: new value with same type as current, or the current value if there was an error casting
    """
    typ = type(current)
    if typ == bool:
        try:
            return bool(int(new))
        except (ValueError, TypeError):
            pass
        try:
            new = new.lower()
        except AttributeError:
            pass
        if (new == 'on') or (new[0] in ('y', 't')):
            return True
        if (new == 'off') or (new[0] in ('n', 'f')):
            return False
    else:
        try:
            return typ(new)
        except (ValueError, TypeError):
            pass
    print("Problem setting parameter (now %s) to %s; incorrect type?" % (current, new))
    return current


class Statekeeper(object):
    """Class used to save and restore state during load and py commands as well as when redirecting output or pipes."""
    def __init__(self, obj, attribs):
        """Use the instance attributes as a generic key-value store to copy instance attributes from outer object.

        :param obj: instance of cmd2.Cmd derived class (your application instance)
        :param attribs: Tuple[str] - tuple of strings listing attributes of obj to save a copy of
        """
        self.obj = obj
        self.attribs = attribs
        if self.obj:
            self._save()

    def _save(self):
        """Create copies of attributes from self.obj inside this Statekeeper instance."""
        for attrib in self.attribs:
            setattr(self, attrib, getattr(self.obj, attrib))

    def restore(self):
        """Overwrite attributes in self.obj with the saved values stored in this Statekeeper instance."""
        if self.obj:
            for attrib in self.attribs:
                setattr(self.obj, attrib, getattr(self, attrib))


class OutputTrap(object):
    """Instantiate an OutputTrap to divert/capture ALL stdout output.  For use in transcript testing."""

    def __init__(self):
        self.contents = ''

    def write(self, txt):
        """Add text to the internal contents.

        :param txt: str
        """
        self.contents += txt

    def read(self):
        """Read from the internal contents and then clear them out.

        :return: str - text from the internal contents
        """
        result = self.contents
        self.contents = ''
        return result


class Cmd2TestCase(unittest.TestCase):
    """Subclass this, setting CmdApp, to make a unittest.TestCase class
       that will execute the commands in a transcript file and expect the results shown.
       See example.py"""
    cmdapp = None

    def fetchTranscripts(self):
        self.transcripts = {}
        for fileset in self.cmdapp.testfiles:
            for fname in glob.glob(fileset):
                tfile = open(fname)
                self.transcripts[fname] = iter(tfile.readlines())
                tfile.close()
        if not len(self.transcripts):
            raise Exception("No test files found - nothing to test.")

    def setUp(self):
        if self.cmdapp:
            self.fetchTranscripts()

            # Trap stdout
            self._orig_stdout = self.cmdapp.stdout
            self.cmdapp.stdout = OutputTrap()

    def runTest(self):  # was testall
        if self.cmdapp:
            its = sorted(self.transcripts.items())
            for (fname, transcript) in its:
                self._test_transcript(fname, transcript)

    def _test_transcript(self, fname, transcript):
        line_num = 0
        finished = False
        line = strip_ansi(next(transcript))
        line_num += 1
        while not finished:
            # Scroll forward to where actual commands begin
            while not line.startswith(self.cmdapp.visible_prompt):
                try:
                    line = strip_ansi(next(transcript))
                except StopIteration:
                    finished = True
                    break
                line_num += 1
            command = [line[len(self.cmdapp.visible_prompt):]]
            line = next(transcript)
            # Read the entirety of a multi-line command
            while line.startswith(self.cmdapp.continuation_prompt):
                command.append(line[len(self.cmdapp.continuation_prompt):])
                try:
                    line = next(transcript)
                except StopIteration:
                    raise (StopIteration,
                           'Transcript broke off while reading command beginning at line {} with\n{}'.format(line_num,
                                                                                                             command[0])
                           )
                line_num += 1
            command = ''.join(command)
            # Send the command into the application and capture the resulting output
            # TODO: Should we get the return value and act if stop == True?
            self.cmdapp.onecmd_plus_hooks(command)
            result = self.cmdapp.stdout.read()
            # Read the expected result from transcript
            if strip_ansi(line).startswith(self.cmdapp.visible_prompt):
                message = '\nFile {}, line {}\nCommand was:\n{}\nExpected: (nothing)\nGot:\n{}\n'.format(
                          fname, line_num, command, result)
                self.assert_(not (result.strip()), message)
                continue
            expected = []
            while not strip_ansi(line).startswith(self.cmdapp.visible_prompt):
                expected.append(line)
                try:
                    line = next(transcript)
                except StopIteration:
                    finished = True
                    break
                line_num += 1
            expected = ''.join(expected)

            # transform the expected text into a valid regular expression
            expected = self._transform_transcript_expected(expected)
            message = '\nFile {}, line {}\nCommand was:\n{}\nExpected:\n{}\nGot:\n{}\n'.format(
                      fname, line_num, command, expected, result)
            self.assertTrue(re.match(expected, result, re.MULTILINE | re.DOTALL), message)

    def _transform_transcript_expected(self, s):
        """parse the string with slashed regexes into a valid regex

        Given a string like:

            Match a 10 digit phone number: /\d{3}-\d{3}-\d{4}/

        Turn it into a valid regular expression which matches the literal text
        of the string and the regular expression. We have to remove the slashes
        because they differentiate between plain text and a regular expression.
        Unless the slashes are escaped, in which case they are interpreted as
        plain text, or there is only one slash, which is treated as plain text
        also.

        Check the tests in tests/test_transcript.py to see all the edge
        cases.
        """
        regex = ''
        start = 0

        while True:
            (regex, first_slash_pos, start) = self._escaped_find(regex, s, start, False)
            if first_slash_pos == -1:
                # no more slashes, add the rest of the string and bail
                regex += re.escape(s[start:])
                break
            else:
                # there is a slash, add everything we have found so far
                # add stuff before the first slash as plain text
                regex += re.escape(s[start:first_slash_pos])
                start = first_slash_pos+1
                # and go find the next one
                (regex, second_slash_pos, start) = self._escaped_find(regex, s, start, True)
                if second_slash_pos > 0:
                    # add everything between the slashes (but not the slashes)
                    # as a regular expression
                    regex += s[start:second_slash_pos]
                    # and change where we start looking for slashed on the
                    # turn through the loop
                    start = second_slash_pos + 1
                else:
                    # No closing slash, we have to add the first slash,
                    # and the rest of the text
                    regex += re.escape(s[start-1:])
                    break
        return regex

    @staticmethod
    def _escaped_find(regex, s, start, in_regex):
        """
        Find the next slash in {s} after {start} that is not preceded by a backslash.

        If we find an escaped slash, add everything up to and including it to regex,
        updating {start}. {start} therefore serves two purposes, tells us where to start
        looking for the next thing, and also tells us where in {s} we have already
        added things to {regex}

        {in_regex} specifies whether we are currently searching in a regex, we behave
        differently if we are or if we aren't.
        """

        while True:
            pos = s.find('/', start)
            if pos == -1:
                # no match, return to caller
                break
            elif pos == 0:
                # slash at the beginning of the string, so it can't be
                # escaped. We found it.
                break
            else:
                # check if the slash is preceeded by a backslash
                if s[pos-1:pos] == '\\':
                    # it is.
                    if in_regex:
                        # add everything up to the backslash as a
                        # regular expression
                        regex += s[start:pos-1]
                        # skip the backslash, and add the slash
                        regex += s[pos]
                    else:
                        # add everything up to the backslash as escaped
                        # plain text
                        regex += re.escape(s[start:pos-1])
                        # and then add the slash as escaped
                        # plain text
                        regex += re.escape(s[pos])
                    # update start to show we have handled everything
                    # before it
                    start = pos+1
                    # and continue to look
                else:
                    # slash is not escaped, this is what we are looking for
                    break
        return regex, pos, start

    def tearDown(self):
        if self.cmdapp:
            # Restore stdout
            self.cmdapp.stdout = self._orig_stdout


def namedtuple_with_two_defaults(typename, field_names, default_values=('', '')):
    """Wrapper around namedtuple which lets you treat the last value as optional.

    :param typename: str - type name for the Named tuple
    :param field_names: List[str] or space-separated string of field names
    :param default_values: (optional) 2-element tuple containing the default values for last 2 parameters in named tuple
                            Defaults to an empty string for both of them
    :return: namedtuple type
    """
    T = collections.namedtuple(typename, field_names)
    # noinspection PyUnresolvedReferences
    T.__new__.__defaults__ = default_values
    return T


class CmdResult(namedtuple_with_two_defaults('CmdResult', ['out', 'err', 'war'])):
    """Derive a class to store results from a named tuple so we can tweak dunder methods for convenience.

    This is provided as a convenience and an example for one possible way for end users to store results in
    the self._last_result attribute of cmd2.Cmd class instances.  See the "python_scripting.py" example for how it can
    be used to enable conditional control flow.

    Named tuple attributes
    ----------------------
    out - this is intended to store normal output data from the command and can be of any type that makes sense
    err: str - (optional) this is intended to store an error message and it being non-empty indicates there was an error
                Defaults to an empty string
    war: str - (optional) this is intended to store a warning message which isn't quite an error, but of note
               Defaults to an empty string.

    NOTE: Named tuples are immutable.  So the contents are there for access, not for modification.
    """
    def __bool__(self):
        """If err is an empty string, treat the result as a success; otherwise treat it as a failure."""
        return not self.err

    def __nonzero__(self):
        """Python 2 uses this method for determining Truthiness"""
        return self.__bool__()


if __name__ == '__main__':
    # If run as the main application, simply start a bare-bones cmd2 application with only built-in functionality.

    # Set "use_ipython" to True to include the ipy command if IPython is installed, which supports advanced interactive
    # debugging of your application via introspection on self.
    app = Cmd(use_ipython=False)
    app.cmdloop()
