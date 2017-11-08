#!/usr/bin/env python
# coding=utf-8
"""Variant on standard library's cmd with extra features.

To use, simply import cmd2.Cmd instead of cmd.Cmd; use precisely as though you
were using the standard library's cmd, while enjoying the extra features.

Searchable command history (commands: "history", "list", "run")
Load commands from file, save to file, edit commands in file
Multi-line commands
Case-insensitive commands
Special-character shortcut commands (beyond cmd's "@" and "!")
Settable environment parameters
Optional _onchange_{paramname} called when environment parameter changes
Parsing commands with `optparse` options (flags)
Redirection to file with >, >>; input from file with <
Easy transcript-based testing of applications (see examples/example.py)
Bash-style ``select`` available

Note that redirection with > and | will only work if `self.poutput()`
is used in place of `print`.

- Catherine Devlin, Jan 03 2008 - catherinedevlin.blogspot.com

Git repository on GitHub at https://github.com/python-cmd2/cmd2
"""
import cmd
import codecs
import collections
import datetime
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
from optparse import make_option

import pyparsing
import pyperclip

# Newer versions of pyperclip are released as a single file, but older versions had a more complicated structure
try:
    from pyperclip.exceptions import PyperclipException
except ImportError:
    # noinspection PyUnresolvedReferences
    from pyperclip import PyperclipException

# On some systems, pyperclip will import gtk for its clipboard functionality.
# The following code is a workaround for gtk interfering with printing from a background
# thread while the CLI thread is blocking in raw_input() in Python 2 on Linux.
try:
    # noinspection PyUnresolvedReferences
    import gtk
    gtk.set_interactive(0)
except ImportError:
    pass

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

# BrokenPipeError is only in Python 3. Use IOError for Python 2.
if six.PY3:
    BROKEN_PIPE_ERROR = BrokenPipeError
else:
    BROKEN_PIPE_ERROR = IOError

__version__ = '0.7.8'

# Pyparsing enablePackrat() can greatly speed up parsing, but problems have been seen in Python 3 in the past
pyparsing.ParserElement.enablePackrat()

# Override the default whitespace chars in Pyparsing so that newlines are not treated as whitespace
pyparsing.ParserElement.setDefaultWhitespaceChars(' \t')


# The next 3 variables and associated setter functions effect how arguments are parsed for commands using @options.
# The defaults are "sane" and maximize ease of use for new applications based on cmd2.
# To maximize backwards compatibility, we recommend setting USE_ARG_LIST to "False"

# Use POSIX or Non-POSIX (Windows) rules for splitting a command-line string into a list of arguments via shlex.split()
POSIX_SHLEX = False

# Strip outer quotes for convenience if POSIX_SHLEX = False
STRIP_QUOTES_FOR_NON_POSIX = True

# For option commands, pass a list of argument strings instead of a single argument string to the do_* methods
USE_ARG_LIST = True


def set_posix_shlex(val):
    """ Allows user of cmd2 to choose between POSIX and non-POSIX splitting of args for @options commands.

    :param val: bool - True => POSIX,  False => Non-POSIX
    """
    global POSIX_SHLEX
    POSIX_SHLEX = val


def set_strip_quotes(val):
    """ Allows user of cmd2 to choose whether to automatically strip outer-quotes when POSIX_SHLEX is False.

    :param val: bool - True => strip quotes on args and option args for @option commands if POSIX_SHLEX is False.
    """
    global STRIP_QUOTES_FOR_NON_POSIX
    STRIP_QUOTES_FOR_NON_POSIX = val


def set_use_arg_list(val):
    """ Allows user of cmd2 to choose between passing @options commands an argument string or list of arg strings.

    :param val: bool - True => arg is a list of strings,  False => arg is a string (for @options commands)
    """
    global USE_ARG_LIST
    USE_ARG_LIST = val


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


class Cmd(cmd.Cmd):
    """An easy but powerful framework for writing line-oriented command interpreters.

    Extends the Python Standard Library’s cmd package by adding a lot of useful features
    to the out of the box configuration.

    Line-oriented command interpreters are often useful for test harnesses, internal tools, and rapid prototypes.
    """
    # Attributes used to configure the ParserManager (all are not dynamically settable at runtime)
    blankLinesAllowed = False
    case_insensitive = True  # Commands recognized regardless of case
    commentGrammars = pyparsing.Or([pyparsing.pythonStyleComment, pyparsing.cStyleComment])
    commentInProgress = pyparsing.Literal('/*') + pyparsing.SkipTo(pyparsing.stringEnd ^ '*/')
    legalChars = u'!#$%.:?@_-' + pyparsing.alphanums + pyparsing.alphas8bit
    multilineCommands = []  # NOTE: Multiline commands can never be abbreviated, even if abbrev is True
    prefixParser = pyparsing.Empty()
    redirector = '>'        # for sending output to file
    shortcuts = {'?': 'help', '!': 'shell', '@': 'load', '@@': '_relative_load'}
    terminators = [';']     # make sure your terminators are not in legalChars!

    # Attributes which are NOT dynamically settable at runtime
    allow_cli_args = True       # Should arguments passed on the command-line be processed as commands?
    allow_redirection = True    # Should output redirection and pipes be allowed
    default_to_shell = False    # Attempt to run unrecognized commands as shell commands
    excludeFromHistory = '''run ru r history histor histo hist his hi h edit edi ed e eof eo eos'''.split()
    exclude_from_help = ['do_eof', 'do_eos']  # Commands to exclude from the help menu
    reserved_words = []

    # Attributes which ARE dynamically settable at runtime
    abbrev = False  # Abbreviated commands recognized
    autorun_on_edit = False  # Should files automatically run after editing (doesn't apply to commands)
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
    settable = {'abbrev': 'Accept abbreviated commands',
                'autorun_on_edit': 'Automatically run files after editing',
                'colors': 'Colorized output (*nix only)',
                'continuation_prompt': 'On 2nd+ line of input',
                'debug': 'Show full error stack on error',
                'echo': 'Echo command issued into output',
                'editor': 'Program used by ``edit``',
                'feedback_to_output': 'Include nonessentials in `|`, `>` results',
                'locals_in_py': 'Allow access to your application in py via self',
                'prompt': 'The prompt issued to solicit input',
                'quiet': "Don't print nonessential feedback",
                'timing': 'Report execution times'}

    def __init__(self, completekey='tab', stdin=None, stdout=None, use_ipython=False, transcript_files=None):
        """An easy but powerful framework for writing line-oriented command interpreters, extends Python's cmd package.

        :param completekey: str - (optional) readline name of a completion key, default to Tab
        :param stdin: (optional) alternate input file object, if not specified, sys.stdin is used
        :param stdout: (optional) alternate output file object, if not specified, sys.stdout is used
        :param use_ipython: (optional) should the "ipy" command be included for an embedded IPython shell
        :param transcript_files: str - (optional) allows running transcript tests when allow_cli_args is False
        """
        # If use_ipython is False, make sure the do_ipy() method doesn't exit
        if not use_ipython:
            try:
                del Cmd.do_ipy
            except AttributeError:
                pass

        # Call super class constructor.  Need to do it in this way for Python 2 and 3 compatibility
        cmd.Cmd.__init__(self, completekey=completekey, stdin=stdin, stdout=stdout)

        self._finalize_app_parameters()
        self.initial_stdout = sys.stdout
        self.history = History()
        self.pystate = {}
        self.keywords = self.reserved_words + [fname[3:] for fname in dir(self) if fname.startswith('do_')]
        self.parser_manager = ParserManager(redirector=self.redirector, terminators=self.terminators,
                                            multilineCommands=self.multilineCommands,
                                            legalChars=self.legalChars, commentGrammars=self.commentGrammars,
                                            commentInProgress=self.commentInProgress,
                                            case_insensitive=self.case_insensitive,
                                            blankLinesAllowed=self.blankLinesAllowed, prefixParser=self.prefixParser,
                                            preparse=self.preparse, postparse=self.postparse, shortcuts=self.shortcuts)
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
                # command is finished.  We intentionally don't print a warning message here since we know that stdout
                # will be restored by the _restore_output() method.  If you would like your application to print a
                # warning message, then override this method.
                pass

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
        """Override of cmd2 method which completes command names both for command completion and help."""
        command = text
        if self.case_insensitive:
            command = text.lower()

        # Call super class method.  Need to do it this way for Python 2 and 3 compatibility
        cmd_completion = cmd.Cmd.completenames(self, command)

        # If we are completing the initial command name and get exactly 1 result and are at end of line, add a space
        if begidx == 0 and len(cmd_completion) == 1 and endidx == len(line):
            cmd_completion[0] += ' '

        return cmd_completion

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

        # Expand command shortcuts to the full command name
        for (shortcut, expansion) in self.shortcuts:
            if line.startswith(shortcut):
                line = line.replace(shortcut, expansion + ' ', 1)
                break

        i, n = 0, len(line)
        while i < n and line[i] in self.identchars:
            i += 1
        command, arg = line[:i], line[i:].strip()
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
            if statement.parsed.command not in self.excludeFromHistory:
                self.history.append(statement.parsed.raw)
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
                stop = self.onecmd_plus_hooks(self.cmdqueue.pop(0))
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

                # Re-raise the exception
                raise ex
        elif statement.parsed.output:
            if (not statement.parsed.outputTo) and (not can_clip):
                raise EnvironmentError('Cannot redirect to paste buffer; install ``xclip`` and re-run to enable')
            self.kept_state = Statekeeper(self, ('stdout',))
            self.kept_sys = Statekeeper(sys, ('stdout',))
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

    def _func_named(self, arg):
        """Gets the method name associated with a given command.

        If self.abbrev is False, it is always just looks for do_arg.  However, if self.abbrev is True,
        it allows abbreviated command names and looks for any commands which start with do_arg.

        :param arg: str - command to look up method name which implements it
        :return: str - method name which implements the given command
        """
        result = None
        target = 'do_' + arg
        if target in dir(self):
            result = target
        else:
            if self.abbrev:  # accept shortened versions of commands
                funcs = [func for func in self.keywords if func.startswith(arg) and func not in self.multilineCommands]
                if len(funcs) == 1:
                    result = 'do_' + funcs[0]
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

    # noinspection PyUnusedLocal
    def do_cmdenvironment(self, args):
        """Summary report of interactive parameters."""
        self.poutput("""
        Commands are case-sensitive: {}
        Commands may be terminated with: {}
        Arguments at invocation allowed: {}
        Output redirection and pipes allowed: {}
        Parsing of @options commands:
            Shell lexer mode for command argument splitting: {}
            Strip Quotes after splitting arguments: {}
            Argument type: {}
        \n""".format(not self.case_insensitive, str(self.terminators), self.allow_cli_args, self.allow_redirection,
                     "POSIX" if POSIX_SHLEX else "non-POSIX",
                     "True" if STRIP_QUOTES_FOR_NON_POSIX and not POSIX_SHLEX else "False",
                     "List of argument strings" if USE_ARG_LIST else "string of space-separated arguments"))

    def do_help(self, arg):
        """List available commands with "help" or detailed help with "help cmd"."""
        if arg:
            # Getting help for a specific command
            funcname = self._func_named(arg)
            if funcname:
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

    # noinspection PyUnusedLocal
    def do_shortcuts(self, args):
        """Lists shortcuts (aliases) available."""
        result = "\n".join('%s: %s' % (sc[0], sc[1]) for sc in sorted(self.shortcuts))
        self.poutput("Shortcuts for other commands:\n{}\n".format(result))

    # noinspection PyUnusedLocal
    def do_eof(self, arg):
        """Called when <Ctrl>-D is pressed."""
        # End of script should not exit app, but <Ctrl>-D should.
        return self._STOP_AND_EXIT

    def do_quit(self, arg):
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
            try:
                response = int(response)
                result = fulloptions[response - 1][0]
                break
            except (ValueError, IndexError):
                self.poutput("{!r} isn't a valid choice. Pick a number between 1 and {}:\n".format(response,
                                                                                                   len(fulloptions)))
        return result

    @options([make_option('-l', '--long', action="store_true", help="describe function of parameter")])
    def do_show(self, arg, opts):
        """Shows value of a parameter."""
        # If arguments are being passed as a list instead of as a string
        if USE_ARG_LIST:
            if arg:
                arg = arg[0]
            else:
                arg = ''

        param = arg.strip().lower()
        result = {}
        maxlen = 0
        for p in self.settable:
            if (not param) or p.startswith(param):
                result[p] = '%s: %s' % (p, str(getattr(self, p)))
                maxlen = max(maxlen, len(result[p]))
        if result:
            for p in sorted(result):
                if opts.long:
                    self.poutput('{} # {}'.format(result[p].ljust(maxlen), self.settable[p]))
                else:
                    self.poutput(result[p])
        else:
            raise LookupError("Parameter '%s' not supported (type 'show' for list of parameters)." % param)

    def do_set(self, arg):
        """Sets a settable parameter.

        Accepts abbreviated parameter names so long as there is no ambiguity.
        Call without arguments for a list of settable parameters with their values.
        """
        try:
            statement, param_name, val = arg.parsed.raw.split(None, 2)
            val = val.strip()
            param_name = param_name.strip().lower()
            if param_name not in self.settable:
                hits = [p for p in self.settable if p.startswith(param_name)]
                if len(hits) == 1:
                    param_name = hits[0]
                else:
                    return self.do_show(param_name)
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
            self.do_show(arg)

    def do_shell(self, command):
        """Execute a command as if at the OS prompt.

    Usage:  shell <command> [arguments]"""
        proc = subprocess.Popen(command, stdout=self.stdout, shell=True)
        proc.communicate()

    def path_complete(self, text, line, begidx, endidx, dir_exe_only=False, dir_only=False):
        """Method called to complete an input line by local file system path completion.

        :param text: str - the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: str - the current input line with leading whitespace removed
        :param begidx: int - the beginning indexe of the prefix text
        :param endidx: int - the ending index of the prefix text
        :param dir_exe_only: bool - only return directories and executables, not non-executable files
        :param dir_only: bool - only return directories
        :return: List[str] - a list of possible tab completions
        """
        # Deal with cases like load command and @ key when path completion is immediately after a shortcut
        for (shortcut, expansion) in self.shortcuts:
            if line.startswith(shortcut):
                # If the next character after the shortcut isn't a space, then insert one and adjust indices
                shortcut_len = len(shortcut)
                if len(line) == shortcut_len or line[shortcut_len] != ' ':
                    line = line.replace(shortcut, shortcut + ' ', 1)
                    begidx += 1
                    endidx += 1
                break

        # Determine if a trailing separator should be appended to directory completions
        add_trailing_sep_if_dir = False
        if endidx == len(line) or (endidx < len(line) and line[endidx] != os.path.sep):
            add_trailing_sep_if_dir = True

        add_sep_after_tilde = False
        # If no path and no search text has been entered, then search in the CWD for *
        if not text and line[begidx - 1] == ' ' and (begidx >= len(line) or line[begidx] == ' '):
            search_str = os.path.join(os.getcwd(), '*')
        else:
            # Parse out the path being searched
            prev_space_index = line.rfind(' ', 0, begidx)
            dirname = line[prev_space_index + 1:begidx]

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
            # If it is a file and we are at the end of the line, then add a space for convenience
            if os.path.isfile(path_completions[0]) and endidx == len(line):
                completions[0] += ' '
            # If tilde was expanded without a separator, prepend one
            elif os.path.isdir(path_completions[0]) and add_sep_after_tilde:
                completions[0] = os.path.sep + completions[0]

        # If there are multiple completions, then sort them alphabetically
        return sorted(completions)

    # Enable tab completion of paths for relevant commands
    complete_edit = path_complete
    complete_load = path_complete
    complete_save = path_complete

    # noinspection PyUnusedLocal
    @staticmethod
    def _shell_command_complete(text, line, begidx, endidx):
        """Method called to complete an input line by environment PATH executable completion.

        :param text: str - the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: str - the current input line with leading whitespace removed
        :param begidx: int - the beginning index of the prefix text
        :param endidx: int - the ending index of the prefix text
        :return: List[str] - a list of possible tab completions
        """

        # Purposely don't match any executable containing wildcards
        wildcards = ['*', '?']
        for wildcard in wildcards:
            if wildcard in text:
                return []

        # Get a list of every directory in the PATH environment variable and ignore symbolic links
        paths = [p for p in os.getenv('PATH').split(os.path.pathsep) if not os.path.islink(p)]

        # Find every executable file in the PATH that matches the pattern
        exes = []
        for path in paths:
            full_path = os.path.join(path, text)
            matches = [f for f in glob.glob(full_path + '*') if os.path.isfile(f) and os.access(f, os.X_OK)]

            for match in matches:
                exes.append(os.path.basename(match))

        # If there is a single completion and we are at end of the line, then add a space at the end for convenience
        if len(exes) == 1 and endidx == len(line):
            exes[0] += ' '

        # If there are multiple completions, then sort them alphabetically
        return sorted(exes)

    # noinspection PyUnusedLocal
    def complete_shell(self, text, line, begidx, endidx):
        """Handles tab completion of executable commands and local file system paths.

        :param text: str - the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: str - the current input line with leading whitespace removed
        :param begidx: int - the beginning index of the prefix text
        :param endidx: int - the ending index of the prefix text
        :return: List[str] - a list of possible tab completions
        """

        # First we strip off the shell command or shortcut key
        if line.startswith('!'):
            stripped_line = line.lstrip('!')
            initial_length = len('!')
        else:
            stripped_line = line[len('shell'):]
            initial_length = len('shell')

        line_parts = stripped_line.split()

        # Don't tab complete anything if user only typed shell or !
        if not line_parts:
            return []

        # Find the start index of the first thing after the shell or !
        cmd_start = line.find(line_parts[0], initial_length)
        cmd_end = cmd_start + len(line_parts[0])

        # Check if we are in the command token
        if cmd_start <= begidx <= cmd_end:

            # See if text is part of a path
            possible_path = line[cmd_start:begidx]

            # There is nothing to search
            if len(possible_path) == 0 and not text:
                return []

            if os.path.sep not in possible_path and possible_path != '~':
                # The text before the search text is not a directory path.
                # It is OK to try shell command completion.
                command_completions = self._shell_command_complete(text, line, begidx, endidx)

                if command_completions:
                    return command_completions

            # If we have no results, try path completion
            return self.path_complete(text, line, begidx, endidx, dir_exe_only=True)

        # Past command token
        else:
            # Do path completion
            return self.path_complete(text, line, begidx, endidx)

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

    # noinspection PyUnusedLocal
    @options([], arg_desc='<script_path> [script_arguments]')
    def do_pyscript(self, arg, opts=None):
        """\nRuns a python script file inside the console

Console commands can be executed inside this script with cmd("your command")
However, you cannot run nested "py" or "pyscript" commands from within this script
Paths or arguments that contain spaces must be enclosed in quotes
"""
        if not arg:
            self.perror("pyscript command requires at least 1 argument ...", traceback_war=False)
            self.do_help('pyscript')
            return

        if not USE_ARG_LIST:
            arg = shlex.split(arg, posix=POSIX_SHLEX)

        # Get the absolute path of the script
        script_path = os.path.expanduser(arg[0])

        # Save current command line arguments
        orig_args = sys.argv

        # Overwrite sys.argv to allow the script to take command line arguments
        sys.argv = [script_path]
        sys.argv.extend(arg[1:])

        # Run the script - use repr formatting to escape things which need to be escaped to prevent issues on Windows
        self.do_py("run({!r})".format(script_path))

        # Restore command line arguments to original state
        sys.argv = orig_args

    # Enable tab completion of paths for pyscript command
    complete_pyscript = path_complete

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

    @options([make_option('-s', '--script', action="store_true", help="Script format; no separation lines"),
              ], arg_desc='(limit on which commands to include)')
    def do_history(self, arg, opts):
        """history [arg]: lists past commands issued

        | no arg:         list all
        | arg is integer: list one history item, by index
        | a..b, a:b, a:, ..b -> list history items by a span of indices (inclusive)
        | arg is string:  list all commands matching string search
        | arg is /enclosed in forward-slashes/: regular expression search
        """
        # If arguments are being passed as a list instead of as a string
        if USE_ARG_LIST:
            if arg:
                arg = arg[0]
            else:
                arg = ''

        # If an argument was supplied, then retrieve partial contents of the history
        if arg:
            # If a character indicating a slice is present, retrieve a slice of the history
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
            history = self.history

        # Display the history items retrieved
        for hi in history:
            if opts.script:
                self.poutput(hi)
            else:
                self.poutput(hi.pr())

    def _last_matching(self, arg):
        """Return the last item from the history list that matches arg.  Or if arg not provided, return last item.

        If not match is found, return None.

        :param arg: str - text to search for in history
        :return: str - last match, last item, or None, depending on arg.
        """
        try:
            if arg:
                return self.history.get(arg)[-1]
            else:
                return self.history[-1]
        except IndexError:
            return None

    @options([], arg_desc="""[N]|[file_path]
    * N         - Number of command (from history), or `*` for all commands in history (default: last command)
    * file_path - path to a file to open in editor""")
    def do_edit(self, arg, opts=None):
        """Edit a file or command in a text editor.

The editor used is determined by the ``editor`` settable parameter.
"set editor (program-name)" to change or set the EDITOR environment variable.

The optional arguments are mutually exclusive.  Either a command number OR a file name can be supplied.
If neither is supplied, the most recent command in the history is edited.

Edited commands are always run after the editor is closed.

Edited files are run on close if the ``autorun_on_edit`` settable parameter is True.
"""
        if not self.editor:
            raise EnvironmentError("Please use 'set editor' to specify your text editing program of choice.")
        filename = None
        if arg and arg[0]:
            try:
                # Try to convert argument to an integer
                history_idx = int(arg[0])
            except ValueError:
                # Argument passed is not convertible to an integer, so treat it as a file path
                filename = arg[0]
                history_item = ''
            else:
                # Argument passed IS convertible to an integer, so treat it as a history index

                # Save off original index for pringing
                orig_indx = history_idx

                # Convert negative index into equivalent positive one
                if history_idx < 0:
                    history_idx += len(self.history) + 1

                # Make sure the index is actually within the history
                if 1 <= history_idx <= len(self.history):
                    history_item = self._last_matching(history_idx)
                else:
                    self.perror('index {!r} does not exist within the history'.format(orig_indx), traceback_war=False)
                    return

        else:
            try:
                history_item = self.history[-1]
            except IndexError:
                self.perror('edit must be called with argument if history is empty', traceback_war=False)
                return

        delete_tempfile = False
        if history_item:
            if filename is None:
                fd, filename = tempfile.mkstemp(suffix='.txt', text=True)
                os.close(fd)
                delete_tempfile = True

            f = open(os.path.expanduser(filename), 'w')
            f.write(history_item or '')
            f.close()

        os.system('"{}" "{}"'.format(self.editor, filename))

        if self.autorun_on_edit or history_item:
            self.do_load(filename)

        if delete_tempfile:
            os.remove(filename)

    saveparser = (pyparsing.Optional(pyparsing.Word(pyparsing.nums) ^ '*')("idx") +
                  pyparsing.Optional(pyparsing.Word(legalChars + '/\\'))("fname") +
                  pyparsing.stringEnd)

    def do_save(self, arg):
        """Saves command(s) from history to file.

    Usage:  save [N] [file_path]

    * N         - Number of command (from history), or `*` for all commands in history (default: last command)
    * file_path - location to save script of command(s) to (default: value stored in temporary file)"""
        try:
            args = self.saveparser.parseString(arg)
        except pyparsing.ParseException:
            self.perror('Could not understand save target %s' % arg, traceback_war=False)
            raise SyntaxError(self.do_save.__doc__)

        # If a filename was supplied then use that, otherwise use a temp file
        if args.fname:
            fname = args.fname
        else:
            fd, fname = tempfile.mkstemp(suffix='.txt', text=True)
            os.close(fd)

        if args.idx == '*':
            saveme = '\n\n'.join(self.history[:])
        elif args.idx:
            saveme = self.history[int(args.idx) - 1]
        else:
            # Wrap in try to deal with case of empty history
            try:
                # Since this save command has already been added to history, need to go one more back for previous
                saveme = self.history[-2]
            except IndexError:
                self.perror('History is empty, nothing to save.', traceback_war=False)
                return
        try:
            f = open(os.path.expanduser(fname), 'w')
            f.write(saveme)
            f.close()
            self.pfeedback('Saved to {}'.format(fname))
        except Exception as e:
            self.perror('Saving {!r} - {}'.format(fname, e), traceback_war=False)

    @property
    def _current_script_dir(self):
        """Accessor to get the current script directory from the _script_dir LIFO queue."""
        if self._script_dir:
            return self._script_dir[-1]
        else:
            return None

    def do__relative_load(self, file_path):
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
        if not file_path:
            self.perror('_relative_load command requires a file path:', traceback_war=False)
            return

        file_path = file_path.strip()
        # NOTE: Relative path is an absolute path, it is just relative to the current script directory
        relative_path = os.path.join(self._current_script_dir or '', file_path)
        self.do_load(relative_path)

    def do_eos(self, _):
        """Handles cleanup when a script has finished executing."""
        if self._script_dir:
            self._script_dir.pop()

    def do_load(self, file_path):
        """Runs commands in script file that is encoded as either ASCII or UTF-8 text.

    Usage:  load <file_path>

    * file_path - a file path pointing to a script

Script should contain one command per line, just like command would be typed in console.
        """
        # If arg is None or arg is an empty string this is an error
        if not file_path:
            self.perror('load command requires a file path:', traceback_war=False)
            return

        expanded_path = os.path.abspath(os.path.expanduser(file_path.strip()))

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

    def do_run(self, arg):
        """run [arg]: re-runs an earlier command

    no arg                               -> run most recent command
    arg is integer                       -> run one history item, by index
    arg is string                        -> run most recent command by string search
    arg is /enclosed in forward-slashes/ -> run most recent by regex"""
        runme = self._last_matching(arg)
        self.pfeedback(runme)
        if runme:
            return self.onecmd_plus_hooks(runme)

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
                 case_insensitive, blankLinesAllowed, prefixParser, preparse, postparse, shortcuts):
        """Creates and uses parsers for user input according to app's parameters."""

        self.commentGrammars = commentGrammars
        self.preparse = preparse
        self.postparse = postparse
        self.shortcuts = shortcuts

        self.main_parser = self._build_main_parser(redirector=redirector, terminators=terminators,
                                                   multilineCommands=multilineCommands, legalChars=legalChars,
                                                   commentInProgress=commentInProgress,
                                                   case_insensitive=case_insensitive,
                                                   blankLinesAllowed=blankLinesAllowed, prefixParser=prefixParser)
        self.input_source_parser = self._build_input_source_parser(legalChars=legalChars,
                                                                   commentInProgress=commentInProgress)

    def _build_main_parser(self, redirector, terminators, multilineCommands, legalChars,
                           commentInProgress, case_insensitive, blankLinesAllowed, prefixParser):
        """Builds a PyParsing parser for interpreting user commands."""

        # Build several parsing components that are eventually compiled into overall parser
        output_destination_parser = (pyparsing.Literal(redirector * 2) |
                                     (pyparsing.WordStart() + redirector) |
                                     pyparsing.Regex('[^=]' + redirector))('output')

        terminator_parser = pyparsing.Or(
            [(hasattr(t, 'parseString') and t) or pyparsing.Literal(t) for t in terminators])('terminator')
        string_end = pyparsing.stringEnd ^ '\nEOF'
        multilineCommand = pyparsing.Or(
            [pyparsing.Keyword(c, caseless=case_insensitive) for c in multilineCommands])('multilineCommand')
        oneline_command = (~multilineCommand + pyparsing.Word(legalChars))('command')
        pipe = pyparsing.Keyword('|', identChars='|')
        do_not_parse = self.commentGrammars | commentInProgress | pyparsing.quotedString
        after_elements = \
            pyparsing.Optional(pipe + pyparsing.SkipTo(output_destination_parser ^ string_end,
                                                       ignore=do_not_parse)('pipeTo')) + \
            pyparsing.Optional(output_destination_parser +
                               pyparsing.SkipTo(string_end,
                                                ignore=do_not_parse).setParseAction(lambda x: x[0].strip())('outputTo'))
        if case_insensitive:
            multilineCommand.setParseAction(lambda x: x[0].lower())
            oneline_command.setParseAction(lambda x: x[0].lower())
        else:
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
            for (shortcut, expansion) in self.shortcuts:
                if s.lower().startswith(shortcut):
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
        """parse the string with slashed regexes into a valid regex"""
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
