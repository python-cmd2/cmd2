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
Easy transcript-based testing of applications (see example/example.py)
Bash-style ``select`` available

Note that redirection with > and | will only work if `self.stdout.write()`
is used in place of `print`.  The standard library's `cmd` module is
written to use `self.stdout.write()`,

- Catherine Devlin, Jan 03 2008 - catherinedevlin.blogspot.com

Git repository on GitHub at https://github.com/python-cmd2/cmd2
"""
import cmd
import copy
import datetime
import glob
import optparse
import os
import platform
import re
import shlex
import six
import subprocess
import sys
import tempfile
import traceback
import unittest
from code import InteractiveConsole
from optparse import make_option

import pyparsing

# next(it) gets next item of iterator it. This is a replacement for calling it.next() in Python 2 and next(it) in Py3
from six import next

# Possible types for text data. This is basestring() in Python 2 and str in Python 3.
from six import string_types

# Used for sm.input: raw_input() for Python 2 or input() for Python 3
import six.moves as sm

# itertools.zip() for Python 2 or zip() for Python 3 - produces an iterator in both cases
from six.moves import zip

# Python 2 urllib2.urlopen() or Python3  urllib.request.urlopen()
from six.moves.urllib.request import urlopen

# Python 3 compatability hack due to no built-in file keyword in Python 3
# Due to one occurence of isinstance(<foo>, file) checking to see if something is of file type
try:
    file
except NameError:
    import io
    file = io.TextIOWrapper

# Detect whether IPython is installed to determine if the built-in "ipy" command should be included
ipython_available = True
try:
    from IPython import embed
except ImportError:
    ipython_available = False

__version__ = '0.7.0'

# Pyparsing enablePackrat() can greatly speed up parsing, but problems have been seen in Python 3 in the past
pyparsing.ParserElement.enablePackrat()


# The next 3 variables and associated setter funtions effect how arguments are parsed for commands using @options.
# The defaults are "sane" and maximize backward compatibility with cmd and previous versions of cmd2.
# But depending on your particular application, you may wish to tweak them so you get the desired parsing behavior.

# Use POSIX or Non-POSIX (Windows) rules for splititng a command-line string into a list of arguments via shlex.split()
POSIX_SHLEX = False

# Strip outer quotes for convenience if POSIX_SHLEX = False
STRIP_QUOTES_FOR_NON_POSIX = True

# For option commandsm, pass a list of argument strings instead of a single argument string to the do_* methods
USE_ARG_LIST = False


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
    def exit(self, status=0, msg=None):
        self.values._exit = True
        if msg:
            print(msg)

    def print_help(self, *args, **kwargs):
        try:
            print(self._func.__doc__)
        except AttributeError:
            pass
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
    matchObj = re.search(pattern, opts_plus_args)
    try:
        remaining = opts_plus_args[matchObj.start():]
    except AttributeError:
        # Don't preserve spacing, but at least we don't crash and we do preserve args and their order
        remaining = ' '.join(arg_list)

    return remaining


def _attr_get_(obj, attr):
    '''Returns an attribute's value, or None (no error) if undefined.
       Analagous to .get() for dictionaries.  Useful when checking for
       value of options that may not have been defined on a given
       method.'''
    try:
        return getattr(obj, attr)
    except AttributeError:
        return None


def _which(editor):
    try:
        return subprocess.Popen(['which', editor], stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()[0]
    except OSError:
        return None


def strip_quotes(arg):
    """ Strip outer quotes from a string.

     Applies to both single and doulbe quotes.

    :param arg: str - string to strip outer quotes from
    :return str - same string with potentially outer quotes stripped
    """
    quote_chars = '"' + "'"

    if len(arg) > 1 and arg[0] == arg[-1] and arg[0] in quote_chars:
        arg = arg[1:-1]
    return arg


optparse.Values.get = _attr_get_
options_defined = []  # used to distinguish --options from SQL-style --comments


def options(option_list, arg_desc="arg"):
    '''Used as a decorator and passed a list of optparse-style options,
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
       '''
    if not isinstance(option_list, list):
        option_list = [option_list]
    for opt in option_list:
        options_defined.append(pyparsing.Literal(opt.get_opt_string()))

    def option_setup(func):
        optionParser = OptionParser()
        for opt in option_list:
            optionParser.add_option(opt)
        # Allow reasonable help for commands defined with @options and an empty list of options
        if len(option_list) > 0:
            optionParser.set_usage("%s [options] %s" % (func.__name__[3:], arg_desc))
        else:
            optionParser.set_usage("%s %s" % (func.__name__[3:], arg_desc))
        optionParser._func = func

        def new_func(instance, arg):
            try:
                # Use shlex to split the command line into a list of arguments based on shell rules
                opts, newArgList = optionParser.parse_args(shlex.split(arg, posix=POSIX_SHLEX))

                # If not using POSIX shlex, make sure to strip off outer quotes for convenience
                if not POSIX_SHLEX and STRIP_QUOTES_FOR_NON_POSIX:
                    new_arg_list = []
                    for arg in newArgList:
                        new_arg_list.append(strip_quotes(arg))
                    newArgList = new_arg_list

                    # Also strip off outer quotes on string option values
                    for key, val in opts.__dict__.items():
                        if isinstance(val, str):
                            opts.__dict__[key] = strip_quotes(val)

                # Must find the remaining args in the original argument list, but
                # mustn't include the command itself
                # if hasattr(arg, 'parsed') and newArgList[0] == arg.parsed.command:
                #    newArgList = newArgList[1:]
                if USE_ARG_LIST:
                    arg = newArgList
                else:
                    newArgs = remaining_args(arg, newArgList)
                    if isinstance(arg, ParsedString):
                        arg = arg.with_args_replaced(newArgs)
                    else:
                        arg = newArgs
            except optparse.OptParseError as e:
                print(e)
                optionParser.print_help()
                return
            if hasattr(opts, '_exit'):
                return None
            result = func(instance, arg, opts)
            return result

        new_func.__doc__ = '%s\n%s' % (func.__doc__, optionParser.format_help())
        return new_func

    return option_setup


class PasteBufferError(EnvironmentError):
    if sys.platform[:3] == 'win':
        errmsg = """Redirecting to or from paste buffer requires pywin32
to be installed on operating system.
Download from http://sourceforge.net/projects/pywin32/"""
    elif sys.platform[:3] == 'dar':
        # Use built in pbcopy on Mac OSX
        pass
    else:
        errmsg = """Redirecting to or from paste buffer requires xclip
to be installed on operating system.
On Debian/Ubuntu, 'sudo apt-get install xclip' will install it."""

    def __init__(self):
        Exception.__init__(self, self.errmsg)


pastebufferr = """Redirecting to or from paste buffer requires %s
to be installed on operating system.
%s"""

# Can we access the clipboard?
can_clip = False
if sys.platform == "win32":
    # Running on Windows
    try:
        import win32clipboard

        def get_paste_buffer():
            win32clipboard.OpenClipboard(0)
            try:
                result = win32clipboard.GetClipboardData()
            except TypeError:
                result = ''  # non-text
            win32clipboard.CloseClipboard()
            return result

        def write_to_paste_buffer(txt):
            win32clipboard.OpenClipboard(0)
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(txt)
            win32clipboard.CloseClipboard()

        can_clip = True
    except ImportError:
        def get_paste_buffer(*args):
            raise OSError(pastebufferr % ('pywin32', 'Download from http://sourceforge.net/projects/pywin32/'))

        write_to_paste_buffer = get_paste_buffer
elif sys.platform == 'darwin':
    # Running on Mac OS X
    try:
        # Warning: subprocess.call() and subprocess.check_call() should never be called with stdout=PIPE or stderr=PIPE
        # because the child process will block if it generates enough output to a pipe to fill up the OS pipe buffer.
        # Starting with Python 3.5 there is a newer, safer API based on the run() function.

        # Python 3.3+ supports subprocess.DEVNULL, but that isn't defined for Python 2.7
        with open(os.devnull, 'w') as DEVNULL:
            # test for pbcopy - AFAIK, should always be installed on MacOS
            subprocess.check_call('pbcopy -help', shell=True, stdin=subprocess.PIPE, stdout=DEVNULL, stderr=DEVNULL)
        can_clip = True
    except (subprocess.CalledProcessError, OSError, IOError):
        pass
    if can_clip:
        def get_paste_buffer():
            pbcopyproc = subprocess.Popen('pbcopy -help', shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                                          stderr=subprocess.PIPE)
            return pbcopyproc.stdout.read()

        def write_to_paste_buffer(txt):
            pbcopyproc = subprocess.Popen('pbcopy', shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                                          stderr=subprocess.PIPE)
            pbcopyproc.communicate(txt.encode())
    else:
        def get_paste_buffer(*args):
            raise OSError(
                pastebufferr % ('pbcopy', 'On MacOS X - error should not occur - part of the default installation'))

        write_to_paste_buffer = get_paste_buffer
else:
    # Running on Linux
    try:
        with open(os.devnull, 'w') as DEVNULL:
            subprocess.check_call('xclip -o -sel clip', shell=True, stdin=subprocess.PIPE, stdout=DEVNULL, stderr=DEVNULL)
        can_clip = True
    except Exception:
        pass  # something went wrong with xclip and we cannot use it
    if can_clip:
        def get_paste_buffer():
            xclipproc = subprocess.Popen('xclip -o -sel clip', shell=True, stdout=subprocess.PIPE,
                                         stdin=subprocess.PIPE)
            return xclipproc.stdout.read()

        def write_to_paste_buffer(txt):
            xclipproc = subprocess.Popen('xclip -sel clip', shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
            xclipproc.stdin.write(txt.encode())
            xclipproc.stdin.close()
            # but we want it in both the "primary" and "mouse" clipboards
            xclipproc = subprocess.Popen('xclip', shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
            xclipproc.stdin.write(txt.encode())
            xclipproc.stdin.close()
    else:
        def get_paste_buffer(*args):
            raise OSError(pastebufferr % ('xclip', 'On Debian/Ubuntu, install with "sudo apt-get install xclip"'))

        write_to_paste_buffer = get_paste_buffer

pyparsing.ParserElement.setDefaultWhitespaceChars(' \t')


class ParsedString(str):
    def full_parsed_statement(self):
        new = ParsedString('%s %s' % (self.parsed.command, self.parsed.args))
        new.parsed = self.parsed
        new.parser = self.parser
        return new

    def with_args_replaced(self, newargs):
        new = ParsedString(newargs)
        new.parsed = self.parsed
        new.parser = self.parser
        new.parsed['args'] = newargs
        new.parsed.statement['args'] = newargs
        return new


class StubbornDict(dict):
    """ Dictionary that tolerates many input formats.

    Create it with the stubbornDict(arg) factory function.
    """
    def update(self, arg):
        dict.update(self, StubbornDict.to_dict(arg))

    append = update

    def __iadd__(self, arg):
        self.update(arg)
        return self

    def __add__(self, arg):
        selfcopy = copy.copy(self)
        selfcopy.update(stubbornDict(arg))
        return selfcopy

    def __radd__(self, arg):
        selfcopy = copy.copy(self)
        selfcopy.update(stubbornDict(arg))
        return selfcopy

    @classmethod
    def to_dict(cls, arg):
        'Generates dictionary from string or list of strings'
        if hasattr(arg, 'splitlines'):
            arg = arg.splitlines()
        if hasattr(arg, '__reversed__'):
            result = {}
            for a in arg:
                a = a.strip()
                if a:
                    key_val = a.split(None, 1)
                    key = key_val[0]
                    if len(key_val) > 1:
                        val = key_val[1]
                    else:
                        val = ''
                    result[key] = val
        else:
            result = arg
        return result


def stubbornDict(*arg, **kwarg):
    """ Factory function which creates instances of the StubornDict class.

    :param arg: an argument which could be used to construct a built-in dict dictionary
    :param kwarg: a variable number of key/value pairs
    :return: StubbornDict - a StubbornDict containing everything in both arg and kwarg
    """
    result = {}
    for a in arg:
        result.update(StubbornDict.to_dict(a))
    result.update(kwarg)
    return StubbornDict(result)


def replace_with_file_contents(fname):
    if fname:
        try:
            result = open(os.path.expanduser(fname[0])).read()
        except IOError:
            result = '< %s' % fname[0]  # wasn't a file after all
    else:
        result = get_paste_buffer()
    return result


class EmbeddedConsoleExit(SystemExit):
    pass


class EmptyStatement(Exception):
    pass


class Cmd(cmd.Cmd):
    """An easy but powerful framework for writing line-oriented command interpreters.

    Extends the Python Standard Library’s cmd package by adding a lot of useful features
    to the out of the box configuration.

    Line-oriented command interpreters are often useful for test harnesses, internal tools, and rapid prototypes.
    """
    #  TODO: Move all instance member initializations inside __init__()

    # Attributes which are NOT dynamically settable at runtime
    _STOP_AND_EXIT = True  # distinguish end of script file from actual exit
    _STOP_SCRIPT_NO_EXIT = -999
    allow_cli_args = True       # Should arguments passed on the command-line be processed as commands?
    allow_redirection = True    # Should output redirection and pipes be allowed
    blankLinesAllowed = False
    colorcodes = {'bold': {True: '\x1b[1m', False: '\x1b[22m'},
                  'cyan': {True: '\x1b[36m', False: '\x1b[39m'},
                  'blue': {True: '\x1b[34m', False: '\x1b[39m'},
                  'red': {True: '\x1b[31m', False: '\x1b[39m'},
                  'magenta': {True: '\x1b[35m', False: '\x1b[39m'},
                  'green': {True: '\x1b[32m', False: '\x1b[39m'},
                  'underline': {True: '\x1b[4m', False: '\x1b[24m'},
                  'yellow': {True: '\x1b[33m', False: '\x1b[39m'},
                  }
    commentGrammars = pyparsing.Or([pyparsing.pythonStyleComment, pyparsing.cStyleComment])
    commentGrammars.addParseAction(lambda x: '')
    commentInProgress = pyparsing.Literal('/*') + pyparsing.SkipTo(pyparsing.stringEnd ^ '*/')
    current_script_dir = None
    default_to_shell = False
    defaultExtension = 'txt'  # For ``save``, ``load``, etc.
    excludeFromHistory = '''run r list l history hi ed edit li eof'''.split()
    kept_state = None
    # make sure your terminators are not in legalChars!
    legalChars = u'!#$%.:?@_' + pyparsing.alphanums + pyparsing.alphas8bit
    multilineCommands = []
    noSpecialParse = 'set ed edit exit'.split()
    prefixParser = pyparsing.Empty()
    redirector = '>'  # for sending output to file
    reserved_words = []
    shortcuts = {'?': 'help', '!': 'shell', '@': 'load', '@@': '_relative_load'}
    terminators = [';']
    urlre = re.compile('(https?://[-\\w\\./]+)')

    # Attributes which ARE dynamicaly settable at runtime
    abbrev = True  # Abbreviated commands recognized
    autorun_on_edit = True  # Should files automatically run after editing (doesn't apply to commands)
    case_insensitive = True  # Commands recognized regardless of case
    colors = (platform.system() != 'Windows')
    continuation_prompt = '> '
    debug = False
    default_file_name = 'command.txt'  # For ``save``, ``load``, etc.
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
    feedback_to_output = False  # Do include nonessentials in >, | output
    locals_in_py = True
    quiet = False  # Do not suppress nonessential output
    timing = False  # Prints elapsed time for each command

    # To make an attribute settable with the "do_set" command, add it to this ...
    settable = stubbornDict('''
        abbrev                Accept abbreviated commands
        autorun_on_edit       Automatically run files after editing
        case_insensitive      upper- and lower-case both OK
        colors                Colorized output (*nix only)
        continuation_prompt   On 2nd+ line of input
        debug                 Show full error stack on error
        default_file_name     for ``save``, ``load``, etc.
        echo                  Echo command issued into output
        editor                Program used by ``edit``
        feedback_to_output    include nonessentials in `|`, `>` results
        locals_in_py          Allow access to your application in py via self
        prompt                The prompt issued to solicit input
        quiet                 Don't print nonessential feedback
        timing                Report execution times
        ''')

    def __init__(self, completekey='tab', stdin=None, stdout=None, use_ipython=False):
        """An easy but powerful framework for writing line-oriented command interpreters, extends Python's cmd package.

        :param completekey: str - (optional) readline name of a completion key, default to Tab
        :param stdin: (optional) alternate input file object, if not specified, sys.stdin is used
        :param stdout: (optional) alternate output file object, if not specified, sys.stdout is used
        :param use_ipython: (optional) should the "ipy" command be included for an embedded IPython shell
        """
        # If use_ipython is False, make sure the do_ipy() method doesn't exit
        if not use_ipython:
            try:
                del Cmd.do_ipy
            except Exception:
                pass

        # Call super class constructor.  Need to do it in this way for Python 2 and 3 compatibility
        cmd.Cmd.__init__(self, completekey=completekey, stdin=stdin, stdout=stdout)

        self.initial_stdout = sys.stdout
        self.history = History()
        self.pystate = {}
        self.shortcuts = sorted(self.shortcuts.items(), reverse=True)
        self.keywords = self.reserved_words + [fname[3:] for fname in dir(self)
                                               if fname.startswith('do_')]
        self._init_parser()
        self._temp_filename = None

    def poutput(self, msg):
        """Convenient shortcut for self.stdout.write(); adds newline if necessary."""
        if msg:
            self.stdout.write(msg)
            if msg[-1] != '\n':
                self.stdout.write('\n')

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
            err = "EXCEPTION of type '{}' occured with message: '{}'\n".format(exception_type, errmsg)
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
                print(msg)

    def colorize(self, val, color):
        """Given a string (``val``), returns that string wrapped in UNIX-style
           special characters that turn on (and then off) text color and style.
           If the ``colors`` environment paramter is ``False``, or the application
           is running on Windows, will return ``val`` unchanged.
           ``color`` should be one of the supported strings (or styles):
           red/blue/green/cyan/magenta, bold, underline"""
        if self.colors and (self.stdout == self.initial_stdout):
            return self.colorcodes[color][True] + val + self.colorcodes[color][False]
        return val

    def do_cmdenvironment(self, args):
        """Summary report of interactive parameters."""
        self.stdout.write("""
        Commands are case-sensitive: {}
        Commands may be terminated with: {}
        Command-line arguments allowed: {}
        Output redirection and pipes allowed: {}
        Settable parameters: {}\n""".format(not self.case_insensitive, str(self.terminators), self.allow_cli_args,
                                            self.allow_redirection, ' '.join(self.settable)))

    def do_help(self, arg):
        """List available commands with "help" or detailed help with "help cmd"."""
        if arg:
            funcname = self.func_named(arg)
            if funcname:
                fn = getattr(self, funcname)
                try:
                    fn.optionParser.print_help(file=self.stdout)
                except AttributeError:
                    cmd.Cmd.do_help(self, funcname[3:])
        else:
            cmd.Cmd.do_help(self, arg)

    def do_shortcuts(self, args):
        """Lists single-key shortcuts available."""
        result = "\n".join('%s: %s' % (sc[0], sc[1]) for sc in sorted(self.shortcuts))
        self.stdout.write("Single-key shortcuts for other commands:\n{}\n".format(result))

    def _init_parser(self):
        """ Initializes everything related to pyparsing. """
        # outputParser = (pyparsing.Literal('>>') | (pyparsing.WordStart() + '>') | pyparsing.Regex('[^=]>'))('output')
        outputParser = (pyparsing.Literal(self.redirector * 2) |
                        (pyparsing.WordStart() + self.redirector) |
                        pyparsing.Regex('[^=]' + self.redirector))('output')

        terminatorParser = pyparsing.Or(
            [(hasattr(t, 'parseString') and t) or pyparsing.Literal(t) for t in self.terminators])('terminator')
        stringEnd = pyparsing.stringEnd ^ '\nEOF'
        self.multilineCommand = pyparsing.Or(
            [pyparsing.Keyword(c, caseless=self.case_insensitive) for c in self.multilineCommands])('multilineCommand')
        oneLineCommand = (~self.multilineCommand + pyparsing.Word(self.legalChars))('command')
        pipe = pyparsing.Keyword('|', identChars='|')
        self.commentGrammars.ignore(pyparsing.quotedString).setParseAction(lambda x: '')
        doNotParse = self.commentGrammars | self.commentInProgress | pyparsing.quotedString
        afterElements = \
            pyparsing.Optional(pipe + pyparsing.SkipTo(outputParser ^ stringEnd, ignore=doNotParse)('pipeTo')) + \
            pyparsing.Optional(
                outputParser + pyparsing.SkipTo(stringEnd, ignore=doNotParse).setParseAction(lambda x: x[0].strip())(
                    'outputTo'))
        if self.case_insensitive:
            self.multilineCommand.setParseAction(lambda x: x[0].lower())
            oneLineCommand.setParseAction(lambda x: x[0].lower())
        if self.blankLinesAllowed:
            self.blankLineTerminationParser = pyparsing.NoMatch
        else:
            self.blankLineTerminator = (pyparsing.lineEnd + pyparsing.lineEnd)('terminator')
            self.blankLineTerminator.setResultsName('terminator')
            self.blankLineTerminationParser = ((self.multilineCommand ^ oneLineCommand) +
                                               pyparsing.SkipTo(self.blankLineTerminator, ignore=doNotParse).setParseAction(
                                                   lambda x: x[0].strip())('args') + self.blankLineTerminator)('statement')
        self.multilineParser = (((self.multilineCommand ^ oneLineCommand) + pyparsing.SkipTo(terminatorParser,
                                                                                             ignore=doNotParse).setParseAction(
            lambda x: x[0].strip())('args') + terminatorParser)('statement') +
                                pyparsing.SkipTo(outputParser ^ pipe ^ stringEnd, ignore=doNotParse).setParseAction(
                                    lambda x: x[0].strip())('suffix') + afterElements)
        self.multilineParser.ignore(self.commentInProgress)
        self.singleLineParser = ((oneLineCommand + pyparsing.SkipTo(terminatorParser ^ stringEnd ^ pipe ^ outputParser,
                                                                    ignore=doNotParse).setParseAction(
            lambda x: x[0].strip())('args'))('statement') +
                                 pyparsing.Optional(terminatorParser) + afterElements)
        # self.multilineParser = self.multilineParser.setResultsName('multilineParser')
        # self.singleLineParser = self.singleLineParser.setResultsName('singleLineParser')
        self.blankLineTerminationParser = self.blankLineTerminationParser.setResultsName('statement')
        self.parser = self.prefixParser + (
            stringEnd |
            self.multilineParser |
            self.singleLineParser |
            self.blankLineTerminationParser |
            self.multilineCommand + pyparsing.SkipTo(stringEnd, ignore=doNotParse)
        )
        self.parser.ignore(self.commentGrammars)

        inputMark = pyparsing.Literal('<')
        inputMark.setParseAction(lambda x: '')
        fileName = pyparsing.Word(self.legalChars + '/\\')
        inputFrom = fileName('inputFrom')
        inputFrom.setParseAction(replace_with_file_contents)
        # a not-entirely-satisfactory way of distinguishing < as in "import from" from <
        # as in "lesser than"
        self.inputParser = inputMark + pyparsing.Optional(inputFrom) + pyparsing.Optional('>') + \
            pyparsing.Optional(fileName) + (pyparsing.stringEnd | '|')
        self.inputParser.ignore(self.commentInProgress)

    def preparse(self, raw, **kwargs):
        return raw

    def postparse(self, parseResult):
        return parseResult

    def parsed(self, raw, **kwargs):
        if isinstance(raw, ParsedString):
            p = raw
        else:
            # preparse is an overridable hook; default makes no changes
            s = self.preparse(raw, **kwargs)
            s = self.inputParser.transformString(s.lstrip())
            s = self.commentGrammars.transformString(s)
            for (shortcut, expansion) in self.shortcuts:
                if s.lower().startswith(shortcut):
                    s = s.replace(shortcut, expansion + ' ', 1)
                    break
            try:
                result = self.parser.parseString(s)
            except pyparsing.ParseException:
                # If we have a parsing failure, treat it is an empty command and move to next prompt
                result = self.parser.parseString('')
            result['raw'] = raw
            result['command'] = result.multilineCommand or result.command
            result = self.postparse(result)
            p = ParsedString(result.args)
            p.parsed = result
            p.parser = self.parsed
        for (key, val) in kwargs.items():
            p.parsed[key] = val
        return p

    def postparsing_precmd(self, statement):
        """This runs after parsing the command-line, but before anything else; even before adding cmd to history.

        NOTE: This runs before precmd() and prior to any potential output redirection or piping.

        If you wish to fatally fail this command and exit the application entirely, set stop = True.

        If you wish to just fail this command you can do so by raising an exception:
            raise EmptyStatement - will silently fail and do nothing
            raise <AnyOtherException> - will fail and print an error message

        :param statement: - the parsed command-line statement
        :return: (bool, statement) - (stop, statement) containing a potentially modified version of the statement
        """
        stop = False
        return stop, statement

    def postparsing_postcmd(self, stop):
        """This runs after everything else, including after postcmd().

        It even runs when an empty line is entered.  Thus, if you need to do something like update the prompt due
        to notifications from a background thread, then this is the method you want to override to do it.

        :param stop: bool - True implies the entire application should exit.
        :return: bool - True implies the entire application should exit.
        """
        return stop

    def func_named(self, arg):
        result = None
        target = 'do_' + arg
        if target in dir(self):
            result = target
        else:
            if self.abbrev:  # accept shortened versions of commands
                funcs = [fname for fname in self.keywords if fname.startswith(arg)]
                if len(funcs) == 1:
                    result = 'do_' + funcs[0]
        return result

    def onecmd_plus_hooks(self, line):
        """

        :param line:
        :return:
        """
        # The outermost level of try/finally nesting can be condensed once
        # Python 2.4 support can be dropped.
        stop = 0
        try:
            statement = ''
            try:
                statement = self.complete_statement(line)
                (stop, statement) = self.postparsing_precmd(statement)
                if stop:
                    return self.postparsing_postcmd(stop)
                if statement.parsed.command not in self.excludeFromHistory:
                    self.history.append(statement.parsed.raw)
                try:
                    if self.allow_redirection:
                        self.redirect_output(statement)
                    timestart = datetime.datetime.now()
                    statement = self.precmd(statement)
                    stop = self.onecmd(statement)
                    stop = self.postcmd(stop, statement)
                    if self.timing:
                        self.pfeedback('Elapsed: %s' % str(datetime.datetime.now() - timestart))
                finally:
                    if self.allow_redirection:
                        self.restore_output(statement)
            except EmptyStatement:
                pass
            except ValueError as ex:
                # If shlex.split failed on syntax, let user know whats going on
                self.perror("Invalid syntax: {}".format(ex), traceback_war=False)
            except Exception as ex:
                self.perror(ex, type(ex).__name__)
        finally:
            return self.postparsing_postcmd(stop)

    def complete_statement(self, line):
        """Keep accepting lines of input until the command is complete."""
        if not line or (not pyparsing.Or(self.commentGrammars).setParseAction(lambda x: '').transformString(line)):
            raise EmptyStatement()
        statement = self.parsed(line)
        while statement.parsed.multilineCommand and (statement.parsed.terminator == ''):
            statement = '%s\n%s' % (statement.parsed.raw,
                                    self.pseudo_raw_input(self.continuation_prompt))
            statement = self.parsed(statement)
        if not statement.parsed.command:
            raise EmptyStatement()
        return statement

    def redirect_output(self, statement):
        if statement.parsed.pipeTo:
            self.kept_state = Statekeeper(self, ('stdout',))
            self.kept_sys = Statekeeper(sys, ('stdout',))
            sys.stdout = self.stdout
            # Redirect stdout to a temporary file
            _, self._temp_filename = tempfile.mkstemp()
            self.stdout = open(self._temp_filename, 'w')
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
                    self.stdout.write(get_paste_buffer())

    def restore_output(self, statement):
        if self.kept_state:
            try:
                if statement.parsed.output:
                    if not statement.parsed.outputTo:
                        self.stdout.seek(0)
                        write_to_paste_buffer(self.stdout.read())
            finally:
                self.stdout.close()
                self.kept_state.restore()
                self.kept_sys.restore()
                self.kept_state = None

                if statement.parsed.pipeTo:
                    # Pipe output from the command to the shell command via echo
                    command_line = r'cat {} | {}'.format(self._temp_filename, statement.parsed.pipeTo)
                    result = subprocess.check_output(command_line, shell=True)
                    if six.PY3:
                        self.stdout.write(result.decode())
                    else:
                        self.stdout.write(result)
                    os.remove(self._temp_filename)
                    self._temp_filename = None

    def onecmd(self, line):
        """Interpret the argument as though it had been typed in response
        to the prompt.

        This may be overridden, but should not normally need to be;
        see the precmd() and postcmd() methods for useful execution hooks.
        The return value is a flag indicating whether interpretation of
        commands by the interpreter should stop.

        This (`cmd2`) version of `onecmd` already override's `cmd`'s `onecmd`.

        """
        statement = self.parsed(line)
        self.lastcmd = statement.parsed.raw
        funcname = self.func_named(statement.parsed.command)
        if not funcname:
            return self._default(statement)
        try:
            func = getattr(self, funcname)
        except AttributeError:
            return self._default(statement)
        stop = func(statement)
        return stop

    def _default(self, statement):
        arg = statement.full_parsed_statement()
        if self.default_to_shell:
            result = os.system(arg)
            if not result:
                return self.postparsing_postcmd(None)
        return self.postparsing_postcmd(self.default(arg))

    def pseudo_raw_input(self, prompt):
        """copied from cmd's cmdloop; like raw_input, but accounts for changed stdin, stdout"""

        if self.use_rawinput:
            try:
                line = sm.input(prompt)
            except EOFError:
                line = 'EOF'
        else:
            self.stdout.write(prompt)
            self.stdout.flush()
            line = self.stdin.readline()
            if not len(line):
                line = 'EOF'
            else:
                if line[-1] == '\n':  # this was always true in Cmd
                    line = line[:-1]
        return line

    def _cmdloop(self):
        """Repeatedly issue a prompt, accept input, parse an initial prefix
        off the received input, and dispatch to action methods, passing them
        the remainder of the line as argument.
        """
        # An almost perfect copy from Cmd; however, the pseudo_raw_input portion
        # has been split out so that it can be called separately
        if self.use_rawinput and self.completekey:
            try:
                import readline
                self.old_completer = readline.get_completer()
                readline.set_completer(self.complete)
                readline.parse_and_bind(self.completekey + ": complete")
            except ImportError:
                pass
        stop = None
        try:
            while not stop:
                if self.cmdqueue:
                    line = self.cmdqueue.pop(0)
                else:
                    line = self.pseudo_raw_input(self.prompt)
                if self.echo and isinstance(self.stdin, file):
                    self.stdout.write(line + '\n')
                stop = self.onecmd_plus_hooks(line)
        finally:
            if self.use_rawinput and self.completekey:
                try:
                    import readline
                    readline.set_completer(self.old_completer)
                except ImportError:
                    pass
            return stop

    def do_eof(self, arg):
        """Automatically called at end of loading a script."""
        return self._STOP_SCRIPT_NO_EXIT  # End of script; should not exit app

    def do_quit(self, arg):
        """Exits this application."""
        return self._STOP_AND_EXIT

    def select(self, options, prompt='Your choice? '):
        """Presents a numbered menu to the user.  Modelled after
           the bash shell's SELECT.  Returns the item chosen.

           Argument ``options`` can be:

             | a single string -> will be split into one-word options
             | a list of strings -> will be offered as options
             | a list of tuples -> interpreted as (value, text), so
                                   that the return value can differ from
                                   the text advertised to the user """
        local_opts = options
        if isinstance(options, string_types):
            local_opts = list(zip(options.split(), options.split()))
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
                self.stdout.write("{!r} isn't a valid choice. Pick a number "
                                  "between 1 and {}:\n".format(
                                      response, len(fulloptions)))
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
                    self.poutput('%s # %s' % (result[p].ljust(maxlen), self.settable[p]))
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
            statement, paramName, val = arg.parsed.raw.split(None, 2)
            val = val.strip()
            paramName = paramName.strip().lower()
            if paramName not in self.settable:
                hits = [p for p in self.settable if p.startswith(paramName)]
                if len(hits) == 1:
                    paramName = hits[0]
                else:
                    return self.do_show(paramName)
            currentVal = getattr(self, paramName)
            if (val[0] == val[-1]) and val[0] in ("'", '"'):
                val = val[1:-1]
            else:
                val = cast(currentVal, val)
            setattr(self, paramName, val)
            self.stdout.write('%s - was: %s\nnow: %s\n' % (paramName, currentVal, val))
            if currentVal != val:
                try:
                    onchange_hook = getattr(self, '_onchange_%s' % paramName)
                    onchange_hook(old=currentVal, new=val)
                except AttributeError:
                    pass
        except (ValueError, AttributeError, NotSettableError):
            self.do_show(arg)

    def do_pause(self, text):
        """Displays the specified text then waits for the user to press <Enter>.

        Usage:  pause [text]

        :param text: str - Text to display to the user (default: blank line)
        """
        sm.input(text + '\n')

    def help_pause(self):
        """Print help for do_pause()."""
        help_str = """Displays the specified text then waits for the user to press <Enter>.

    Usage:  pause [text]"""
        self.stdout.write("{}\n".format(help_str))

    def do_shell(self, command):
        """Execute a command as if at the OS prompt.

        Usage:  shell command

        :param command: str - shell command to execute
        """
        os.system(command)

    def help_shell(self):
        """Print help for do_shell()."""
        help_str = """Execute a command as if at the OS prompt.

    Usage:  shell cmd"""
        self.stdout.write("{}\n".format(help_str))

    def do_py(self, arg):
        '''
        py <command>: Executes a Python command.
        py: Enters interactive Python mode.
        End with ``Ctrl-D`` (Unix) / ``Ctrl-Z`` (Windows), ``quit()``, '`exit()``.
        Non-python commands can be issued with ``cmd("your command")``.
        Run python code from external files with ``run("filename.py")``
        '''
        self.pystate['self'] = self
        arg = arg.parsed.raw[2:].strip()

        # Support the run command even if called prior to invoking an interactive interpreter
        def run(arg):
            try:
                with open(arg) as f:
                    interp.runcode(f.read())
            except IOError as e:
                self.perror(e)
        self.pystate['run'] = run

        localvars = (self.locals_in_py and self.pystate) or {}
        interp = InteractiveConsole(locals=localvars)
        interp.runcode('import sys, os;sys.path.insert(0, os.getcwd())')

        if arg.strip():
            interp.runcode(arg)
        else:
            def quit():
                raise EmbeddedConsoleExit

            def onecmd_plus_hooks(arg):
                return self.onecmd_plus_hooks(arg + '\n')

            self.pystate['quit'] = quit
            self.pystate['exit'] = quit
            self.pystate['cmd'] = onecmd_plus_hooks
            keepstate = None
            try:
                cprt = 'Type "help", "copyright", "credits" or "license" for more information.'
                keepstate = Statekeeper(sys, ('stdin', 'stdout'))
                sys.stdout = self.stdout
                sys.stdin = self.stdin
                interp.interact(banner="Python %s on %s\n%s\n(%s)\n%s" %
                                       (sys.version, sys.platform, cprt, self.__class__.__name__, self.do_py.__doc__))
            except EmbeddedConsoleExit:
                pass
            if keepstate is not None:
                keepstate.restore()

    # Only include the do_ipy() method if IPython is available on the system
    if ipython_available:
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
        | arg is string:  string search
        | arg is /enclosed in forward-slashes/: regular expression search
        """
        # If arguments are being passed as a list instead of as a string
        if USE_ARG_LIST:
            if arg:
                arg = arg[0]
            else:
                arg = ''

        if arg:
            history = self.history.get(arg)
        else:
            history = self.history
        for hi in history:
            if opts.script:
                self.poutput(hi)
            else:
                self.stdout.write(hi.pr())

    def last_matching(self, arg):
        try:
            if arg:
                return self.history.get(arg)[-1]
            else:
                return self.history[-1]
        except IndexError:
            return None

    def do_list(self, arg):
        """list [arg]: lists command(s) from history in a flexible/searchable way.

        :param arg: str - behavior varies as follows:

        * no arg -> list most recent command
        * arg is integer -> list one history item, by index
        * a..b, a:b, a:, ..b -> list spans from a (or start) to b (or end)
        * arg is string -> list all commands matching string search
        * arg is /enclosed in forward-slashes/ -> regular expression search
        """
        try:
            history = self.history.span(arg or '-1')
        except IndexError:
            history = self.history.search(arg)
        for hi in history:
            self.poutput(hi.pr())

    def help_list(self):
        """Print help for do_list()."""
        help_str = """Lists command(s) from history in a flexible/searchable way.

    Usage:  list [arg]

    Where arg is:
    no arg                               -> list most recent command
    arg is integer                       -> list one history item, by index
    a..b, a:b, a:, ..b                   -> list spans from a (or start) to b (or end)
    arg is string                        -> list all commands matching string search
    arg is /enclosed in forward-slashes/ -> regular expression search"""
        self.stdout.write("{}\n".format(help_str))

    def do_edit(self, arg):
        """Edit a file or command in a text editor.

        Usage:  edit [N]|[file_path]

        :param arg: str - [N]|[file_path]

        * **N** - Number of command (from history), or `*` for all commands in history (default: most recent command)
        * **file_path** - path to a file to open in editor

        The editor used is determined by the ``editor`` settable parameter.
        "set editor (program-name)" to change or set the EDITOR environment variable.

        The optional arguments are mutually exclusive.  Either a command number OR a file name can be supplied.
        If neither is supplied, the most recent command in the history is edited.

        Edited commands are always run after the editor is closed.

        Edited files are run on close if the ``autorun_on_edit`` settable parameter is True.
        """
        if not self.editor:
            raise EnvironmentError("Please use 'set editor' to specify your text editing program of choice.")
        filename = self.default_file_name
        if arg:
            try:
                buffer = self.last_matching(int(arg))
            except ValueError:
                filename = arg
                buffer = ''
        else:
            buffer = self.history[-1]

        if buffer:
            f = open(os.path.expanduser(filename), 'w')
            f.write(buffer or '')
            f.close()

        os.system('%s %s' % (self.editor, filename))

        if self.autorun_on_edit or buffer:
            self.do_load(filename)

    def help_edit(self):
        """Print help for do_edit()."""
        help_str = """Edit a file or command in a text editor.

    Usage:  edit [N]|[file_path]

    optional arguments:
    N           Number of command (from history), or `*` for all commands in history (default: most recent command)
    file_path   path to a file to open in editor

The editor used is determined by the `editor` settable parameter.
"set editor (program-name" to change or set the EDITOR environment variable.

The optional arguments are mutually exclusive.  Either a command number OR a file name can be supplied.
If neither is supplied, the most recent command in the history is edited.

Edited commands are always run after the editor is closed.

Edited files are run on close if the `autorun_on_edit` settable parameter is True."""
        self.stdout.write("{}\n".format(help_str))

    saveparser = (pyparsing.Optional(pyparsing.Word(pyparsing.nums) ^ '*')("idx") +
                  pyparsing.Optional(pyparsing.Word(legalChars + '/\\'))("fname") +
                  pyparsing.stringEnd)

    def do_save(self, arg):
        """Saves command(s) from history to file.

        Usage:  save [N] [file_path]

        :param arg: str - [N] [filepath]

        * **N** - Number of command (from history), or `*` for all commands in history (default: most recent command)
        * **file_path** - location to save script of command(s) to (default: value stored in ``default_file_name``)
        """
        try:
            args = self.saveparser.parseString(arg)
        except pyparsing.ParseException:
            self.perror('Could not understand save target %s' % arg)
            raise SyntaxError(self.do_save.__doc__)
        fname = args.fname or self.default_file_name
        if args.idx == '*':
            saveme = '\n\n'.join(self.history[:])
        elif args.idx:
            saveme = self.history[int(args.idx) - 1]
        else:
            # Since this save command has already been added to history, need to go one more back for previous
            saveme = self.history[-2]
        try:
            f = open(os.path.expanduser(fname), 'w')
            f.write(saveme)
            f.close()
            self.pfeedback('Saved to {}'.format(fname))
        except Exception:
            self.perror('Error saving {}'.format(fname))
            raise

    def help_save(self):
        """Print help for do_save()."""
        help_str = """Saves command(s) from history to file.

    Usage:  save [N] [file_path]

    optional arguments:
    N           - Number of command (from history), or `*` for all commands in history (default: most recent command)
    file_path   - location to save script of command(s) to (default: value stored in `default_file_name` parameter)"""
        self.stdout.write("{}\n".format(help_str))

    def read_file_or_url(self, fname):
        # TODO: not working on localhost
        if os.path.isfile(fname):
            result = open(fname, 'r')
        else:
            match = self.urlre.match(fname)
            if match:
                result = urlopen(match.group(1))
            else:
                fname = os.path.expanduser(fname)
                try:
                    result = open(os.path.expanduser(fname), 'r')
                except IOError:
                    result = open('%s.%s' % (os.path.expanduser(fname),
                                             self.defaultExtension), 'r')
        return result

    def do__relative_load(self, arg=None):
        """Runs commands in script at file or URL.

    Usage:  load [file_path]

    optional argument:
    file_path   a file path or URL pointing to a script
                default: value stored in `default_file_name` settable param

Script should contain one command per line, just like command would be typed in console.

If this is called from within an already-running script, the filename will be interpreted
relative to the already-running script's directory.
        """
        if arg:
            arg = arg.split(None, 1)
            targetname, args = arg[0], (arg[1:] or [''])[0]
            targetname = os.path.join(self.current_script_dir or '', targetname)
            self.do_load('%s %s' % (targetname, args))

    def do_load(self, file_path=None):
        """Runs commands in script at file or URL.

        Usage:  load [file_path]

        :param file_path: str - a file path or URL pointing to a script (default: value stored in ``default_file_name``)
        :return: bool - True implies application should stop, False to continue like normal

        Script should contain one command per line, just like command would be typed in console.
        """
        # If arg is None or arg is an empty string, use the default filename
        if not file_path:
            targetname = self.default_file_name
        else:
            file_path = file_path.split(None, 1)
            targetname, args = file_path[0], (file_path[1:] or [''])[0].strip()
        try:
            target = self.read_file_or_url(targetname)
        except IOError as e:
            self.perror('Problem accessing script from %s: \n%s' % (targetname, e))
            return
        keepstate = Statekeeper(self, ('stdin', 'use_rawinput', 'prompt',
                                       'continuation_prompt', 'current_script_dir'))
        self.stdin = target
        self.use_rawinput = False
        self.prompt = self.continuation_prompt = ''
        self.current_script_dir = os.path.split(targetname)[0]
        stop = self._cmdloop()
        self.stdin.close()
        keepstate.restore()
        self.lastcmd = ''
        return stop and (stop != self._STOP_SCRIPT_NO_EXIT)

    def help_load(self):
        """Print help for do_load()."""
        help_str = """Runs commands in script at file or URL.

    Usage:  load [file_path]

    optional argument:
    file_path   -   a file path or URL pointing to a script (default: value stored in `default_file_name` parameter)

Script should contain one command per line, just like command would be typed in console."""
        self.stdout.write("{}\n".format(help_str))

    def do_run(self, arg):
        """run [arg]: re-runs an earlier command

        :param arg: str - determines which command is re-run, as follows:

        * no arg -> run most recent command
        * arg is integer -> run one history item, by index
        * arg is string -> run most recent command by string search
        * arg is /enclosed in forward-slashes/ -> run most recent by regex
        """
        runme = self.last_matching(arg)
        self.pfeedback(runme)
        if runme:
            stop = self.onecmd_plus_hooks(runme)

    def help_run(self):
        """Print help for do_run()."""
        help_str = """run [arg]: re-runs an earlier command

    no arg                               -> run most recent command
    arg is integer                       -> run one history item, by index
    arg is string                        -> run most recent command by string search
    arg is /enclosed in forward-slashes/ -> run most recent by regex"""
        self.stdout.write("{}\n".format(help_str))

    def runTranscriptTests(self, callargs):
        class TestMyAppCase(Cmd2TestCase):
            CmdApp = self.__class__

        self.__class__.testfiles = callargs
        sys.argv = [sys.argv[0]]  # the --test argument upsets unittest.main()
        testcase = TestMyAppCase()
        runner = unittest.TextTestRunner()
        result = runner.run(testcase)
        result.printErrors()

    def run_commands_at_invocation(self, callargs):
        for initial_command in callargs:
            if self.onecmd_plus_hooks(initial_command + '\n'):
                return self._STOP_AND_EXIT

    def cmdloop(self, intro=None):
        parser = optparse.OptionParser()
        parser.add_option('-t', '--test', dest='test',
                          action="store_true",
                          help='Test against transcript(s) in FILE (wildcards OK)')
        (callopts, callargs) = parser.parse_args()
        if callopts.test:
            self.runTranscriptTests(callargs)
        else:
            # Always run the preloop first
            self.preloop()

            # If an intro was supplied in the method call, allow it to override the default
            if intro is not None:
                self.intro = intro

            # Print the intro, if there is one, right after the preloop
            if self.intro is not None:
                self.stdout.write(str(self.intro) + "\n")

            stop = False
            # If allowed, process any commands present as arguments on the command-line, if allowed
            if self.allow_cli_args:
                stop = self.run_commands_at_invocation(callargs)

            # And then call _cmdloop() if there wasn't something in those causing us to quit
            if not stop:
                self._cmdloop()

            # Run the postloop() no matter what
            self.postloop()


class HistoryItem(str):
    listformat = '-------------------------[%d]\n%s\n'

    def __init__(self, instr):
        str.__init__(self)
        self.lowercase = self.lower()
        self.idx = None

    def pr(self):
        return self.listformat % (self.idx, str(self))


class History(list):
    """ A list of HistoryItems that knows how to respond to user requests. """
    def zero_based_index(self, onebased):
        result = onebased
        if result > 0:
            result -= 1
        return result

    def to_index(self, raw):
        if raw:
            result = self.zero_based_index(int(raw))
        else:
            result = None
        return result

    def search(self, target):
        target = target.strip()
        if target[0] == target[-1] == '/' and len(target) > 1:
            target = target[1:-1]
        else:
            target = re.escape(target)
        pattern = re.compile(target, re.IGNORECASE)
        return [s for s in self if pattern.search(s)]

    spanpattern = re.compile(r'^\s*(?P<start>\-?\d+)?\s*(?P<separator>:|(\.{2,}))?\s*(?P<end>\-?\d+)?\s*$')

    def span(self, raw):
        if raw.lower() in ('*', '-', 'all'):
            raw = ':'
        results = self.spanpattern.search(raw)
        if not results:
            raise IndexError
        if not results.group('separator'):
            return [self[self.to_index(results.group('start'))]]
        start = self.to_index(results.group('start'))
        end = self.to_index(results.group('end'))
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

    rangePattern = re.compile(r'^\s*(?P<start>[\d]+)?\s*\-\s*(?P<end>[\d]+)?\s*$')

    def append(self, new):
        new = HistoryItem(new)
        list.append(self, new)
        new.idx = len(self)

    def extend(self, new):
        for n in new:
            self.append(n)

    def get(self, getme=None, fromEnd=False):
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
            rangeResult = self.rangePattern.search(getme)
            if rangeResult:
                start = rangeResult.group('start') or None
                end = rangeResult.group('start') or None
                if start:
                    start = int(start) - 1
                if end:
                    end = int(end)
                return self[start:end]

            getme = getme.strip()

            if getme.startswith(r'/') and getme.endswith(r'/'):
                finder = re.compile(getme[1:-1], re.DOTALL | re.MULTILINE | re.IGNORECASE)

                def isin(hi):
                    return finder.search(hi)
            else:
                def isin(hi):
                    return getme.lower() in hi.lowercase
            return [itm for itm in self if isin(itm)]


class NotSettableError(Exception):
    pass


def cast(current, new):
    """Tries to force a new value into the same type as the current."""
    typ = type(current)
    if typ == bool:
        try:
            return bool(int(new))
        except (ValueError, TypeError):
            pass
        try:
            new = new.lower()
        except:
            pass
        if (new == 'on') or (new[0] in ('y', 't')):
            return True
        if (new == 'off') or (new[0] in ('n', 'f')):
            return False
    else:
        try:
            return typ(new)
        except:
            pass
    print("Problem setting parameter (now %s) to %s; incorrect type?" % (current, new))
    return current


class Statekeeper(object):
    def __init__(self, obj, attribs):
        self.obj = obj
        self.attribs = attribs
        if self.obj:
            self.save()

    def save(self):
        for attrib in self.attribs:
            setattr(self, attrib, getattr(self.obj, attrib))

    def restore(self):
        if self.obj:
            for attrib in self.attribs:
                setattr(self.obj, attrib, getattr(self, attrib))


class Borg(object):
    '''All instances of any Borg subclass will share state.
    from Python Cookbook, 2nd Ed., recipe 6.16'''
    _shared_state = {}

    def __new__(cls, *a, **k):
        obj = object.__new__(cls, *a, **k)
        obj.__dict__ = cls._shared_state
        return obj


class OutputTrap(Borg):
    '''Instantiate  an OutputTrap to divert/capture ALL stdout output.  For use in unit testing.
    Call `tearDown()` to return to normal output.'''

    def __init__(self):
        self.contents = ''
        self.old_stdout = sys.stdout
        sys.stdout = self

    def write(self, txt):
        self.contents += txt

    def read(self):
        result = self.contents
        self.contents = ''
        return result

    def tearDown(self):
        sys.stdout = self.old_stdout
        self.contents = ''


class Cmd2TestCase(unittest.TestCase):
    '''Subclass this, setting CmdApp, to make a unittest.TestCase class
       that will execute the commands in a transcript file and expect the results shown.
       See example.py'''
    CmdApp = None

    def fetchTranscripts(self):
        self.transcripts = {}
        for fileset in self.CmdApp.testfiles:
            for fname in glob.glob(fileset):
                tfile = open(fname)
                self.transcripts[fname] = iter(tfile.readlines())
                tfile.close()
        if not len(self.transcripts):
            raise Exception("No test files found - nothing to test.")

    def setUp(self):
        if self.CmdApp:
            self.outputTrap = OutputTrap()
            self.cmdapp = self.CmdApp()
            self.fetchTranscripts()

    def runTest(self):  # was testall
        if self.CmdApp:
            its = sorted(self.transcripts.items())
            for (fname, transcript) in its:
                self._test_transcript(fname, transcript)

    regexPattern = pyparsing.QuotedString(quoteChar=r'/', escChar='\\', multiline=True, unquoteResults=True)
    regexPattern.ignore(pyparsing.cStyleComment)
    notRegexPattern = pyparsing.Word(pyparsing.printables)
    notRegexPattern.setParseAction(lambda t: re.escape(t[0]))
    expectationParser = regexPattern | notRegexPattern
    anyWhitespace = re.compile(r'\s', re.DOTALL | re.MULTILINE)

    def _test_transcript(self, fname, transcript):
        lineNum = 0
        finished = False
        line = next(transcript)
        lineNum += 1
        while not finished:
            # Scroll forward to where actual commands begin
            while not line.startswith(self.cmdapp.prompt):
                try:
                    line = next(transcript)
                except StopIteration:
                    finished = True
                    break
                lineNum += 1
            command = [line[len(self.cmdapp.prompt):]]
            line = next(transcript)
            # Read the entirety of a multi-line command
            while line.startswith(self.cmdapp.continuation_prompt):
                command.append(line[len(self.cmdapp.continuation_prompt):])
                try:
                    line = next(transcript)
                except StopIteration:
                    raise (StopIteration,
                           'Transcript broke off while reading command beginning at line {} with\n{}'.format(lineNum,
                                                                                                             command[0])
                           )
                lineNum += 1
            command = ''.join(command)
            # Send the command into the application and capture the resulting output
            stop = self.cmdapp.onecmd_plus_hooks(command)
            # TODO: should act on ``stop``
            result = self.outputTrap.read()
            # Read the expected result from transcript
            if line.startswith(self.cmdapp.prompt):
                message = '\nFile %s, line %d\nCommand was:\n%r\nExpected: (nothing)\nGot:\n%r\n' % \
                          (fname, lineNum, command, result)
                self.assert_(not (result.strip()), message)
                continue
            expected = []
            while not line.startswith(self.cmdapp.prompt):
                expected.append(line)
                try:
                    line = next(transcript)
                except StopIteration:
                    finished = True
                    break
                lineNum += 1
            expected = ''.join(expected)
            # Compare actual result to expected
            message = '\nFile %s, line %d\nCommand was:\n%s\nExpected:\n%s\nGot:\n%s\n' % \
                      (fname, lineNum, command, expected, result)
            expected = self.expectationParser.transformString(expected)
            # checking whitespace is a pain - let's skip it
            expected = self.anyWhitespace.sub('', expected)
            result = self.anyWhitespace.sub('', result)
            self.assertTrue(re.match(expected, result, re.MULTILINE | re.DOTALL), message)

    def tearDown(self):
        if self.CmdApp:
            self.outputTrap.tearDown()


if __name__ == '__main__':
    # If run as the main application, simply start a bare-bones cmd2 application with only built-in functionality.
    app = Cmd()
    app.cmdloop()
