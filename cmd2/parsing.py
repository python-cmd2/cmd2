#
# -*- coding: utf-8 -*-
"""Statement parsing classes for cmd2"""

import os
import re
import shlex
from typing import Dict, Iterable, List, Optional, Tuple, Union

import attr

from . import constants
from . import utils


def shlex_split(str_to_split: str) -> List[str]:
    """A wrapper around shlex.split() that uses cmd2's preferred arguments.

    This allows other classes to easily call split() the same way StatementParser does
    :param str_to_split: the string being split
    :return: A list of tokens
    """
    return shlex.split(str_to_split, comments=False, posix=False)


@attr.s(frozen=True)
class MacroArg:
    """
    Information used to replace or unescape arguments in a macro value when the macro is resolved
    Normal argument syntax  : {5}
    Escaped argument syntax: {{5}}
    """
    # The starting index of this argument in the macro value
    start_index = attr.ib(validator=attr.validators.instance_of(int))

    # The number string that appears between the braces
    # This is a string instead of an int because we support unicode digits and must be able
    # to reproduce this string later
    number_str = attr.ib(validator=attr.validators.instance_of(str))

    # Tells if this argument is escaped and therefore needs to be unescaped
    is_escaped = attr.ib(validator=attr.validators.instance_of(bool))

    # Pattern used to find normal argument
    # Digits surrounded by exactly 1 brace on a side and 1 or more braces on the opposite side
    # Match strings like: {5}, {{{{{4}, {2}}}}}
    macro_normal_arg_pattern = re.compile(r'(?<!{){\d+}|{\d+}(?!})')

    # Pattern used to find escaped arguments
    # Digits surrounded by 2 or more braces on both sides
    # Match strings like: {{5}}, {{{{{4}}, {{2}}}}}
    macro_escaped_arg_pattern = re.compile(r'{{2}\d+}{2}')

    # Finds a string of digits
    digit_pattern = re.compile(r'\d+')


@attr.s(frozen=True)
class Macro:
    """Defines a cmd2 macro"""

    # Name of the macro
    name = attr.ib(validator=attr.validators.instance_of(str))

    # The string the macro resolves to
    value = attr.ib(validator=attr.validators.instance_of(str))

    # The minimum number of args the user has to pass to this macro
    minimum_arg_count = attr.ib(validator=attr.validators.instance_of(int))

    # Used to fill in argument placeholders in the macro
    arg_list = attr.ib(default=attr.Factory(list), validator=attr.validators.instance_of(list))


@attr.s(frozen=True)
class Statement(str):
    """String subclass with additional attributes to store the results of parsing.

    The cmd module in the standard library passes commands around as a
    string. To retain backwards compatibility, cmd2 does the same. However, we
    need a place to capture the additional output of the command parsing, so we add
    our own attributes to this subclass.

    Instances of this class should not be created by anything other than the
    `StatementParser.parse()` method, nor should any of the attributes be modified
    once the object is created.

    The string portion of the class contains the arguments, but not the command, nor
    the output redirection clauses.

    Here's some suggestions and best practices for how to use the attributes of this
    object:

    command - the name of the command, shortcuts and aliases have already been
              expanded

    args - the arguments to the command, excluding output redirection and command
           terminators. If the user used quotes in their input, they remain here,
           and you will have to handle them on your own.

    arg_list - the arguments to the command, excluding output redirection and
               command terminators. Each argument is represented as an element
               in the list. Quoted arguments remain quoted. If you want to
               remove the quotes, use `cmd2.utils.strip_quotes()` or use
               `argv[1:]`

    command_and_args - join the args and the command together with a space. Output
                       redirection is excluded.

    argv - this is a list of arguments in the style of `sys.argv`. The first element
           of the list is the command. Subsequent elements of the list contain any
           additional arguments, with quotes removed, just like bash would. This
           is very useful if you are going to use `argparse.parse_args()`:
           ```
           def do_mycommand(stmt):
               mycommand_argparser.parse_args(stmt.argv)
               ...
            ```

    raw - if you want full access to exactly what the user typed at the input prompt
          you can get it, but you'll have to parse it on your own, including:
             - shortcuts and aliases
             - quoted commands and arguments
             - output redirection
             - multi-line command terminator handling
          if you use multiline commands, all the input will be passed to you in
          this string, but there will be embedded newlines where
          the user hit return to continue the command on the next line.

    Tips:

    1. `argparse` is your friend for anything complex. `cmd2` has two decorators
       (`with_argparser`, and `with_argparser_and_unknown_args`) which you can use
       to make your command method receive a namespace of parsed arguments, whether
       positional or denoted with switches.

    2. For commands with simple positional arguments, use `args` or `arg_list`

    3. If you don't want to have to worry about quoted arguments, use
       argv[1:], which strips them all off for you.
    """
    # the arguments, but not the command, nor the output redirection clauses.
    args = attr.ib(default='', validator=attr.validators.instance_of(str))

    # string containing exactly what we input by the user
    raw = attr.ib(default='', validator=attr.validators.instance_of(str))

    # the command, i.e. the first whitespace delimited word
    command = attr.ib(default='', validator=attr.validators.instance_of(str))

    # list of arguments to the command, not including any output redirection or terminators; quoted args remain quoted
    arg_list = attr.ib(default=attr.Factory(list), validator=attr.validators.instance_of(list))

    # if the command is a multiline command, the name of the command, otherwise empty
    multiline_command = attr.ib(default='', validator=attr.validators.instance_of(str))

    # the character which terminated the multiline command, if there was one
    terminator = attr.ib(default='', validator=attr.validators.instance_of(str))

    # characters appearing after the terminator but before output redirection, if any
    suffix = attr.ib(default='', validator=attr.validators.instance_of(str))

    # if output was piped to a shell command, the shell command as a list of tokens
    pipe_to = attr.ib(default=attr.Factory(list), validator=attr.validators.instance_of(list))

    # if output was redirected, the redirection token, i.e. '>>'
    output = attr.ib(default='', validator=attr.validators.instance_of(str))

    # if output was redirected, the destination file
    output_to = attr.ib(default='', validator=attr.validators.instance_of(str))

    def __new__(cls, value: object, *pos_args, **kw_args):
        """Create a new instance of Statement.

        We must override __new__ because we are subclassing `str` which is
        immutable and takes a different number of arguments as Statement.

        NOTE:  attrs takes care of initializing other members in the __init__ it
        generates.
        """
        stmt = super().__new__(cls, value)
        return stmt

    @property
    def command_and_args(self) -> str:
        """Combine command and args with a space separating them.

        Quoted arguments remain quoted. Output redirection and piping are
        excluded, as are any multiline command terminators.
        """
        if self.command and self.args:
            rtn = '{} {}'.format(self.command, self.args)
        elif self.command:
            # there were no arguments to the command
            rtn = self.command
        else:
            rtn = ''
        return rtn

    @property
    def expanded_command_line(self) -> str:
        """Contains command_and_args plus any ending terminator, suffix, and redirection chars"""
        rtn = self.command_and_args
        if self.multiline_command:
            rtn += constants.MULTILINE_TERMINATOR
        elif self.terminator:
            rtn += self.terminator

        if self.suffix:
            rtn += ' ' + self.suffix

        if self.pipe_to:
            rtn += ' | ' + ' '.join(self.pipe_to)

        if self.output:
            rtn += ' ' + self.output
            if self.output_to:
                rtn += ' ' + self.output_to

        return rtn

    @property
    def argv(self) -> List[str]:
        """a list of arguments a la sys.argv.

        Quotes, if any, are removed from the elements of the list, and aliases
        and shortcuts are expanded
        """
        if self.command:
            rtn = [utils.strip_quotes(self.command)]
            for cur_token in self.arg_list:
                rtn.append(utils.strip_quotes(cur_token))
        else:
            rtn = []

        return rtn


class StatementParser:
    """Parse raw text into command components.

    Shortcuts is a list of tuples with each tuple containing the shortcut and
    the expansion.
    """
    def __init__(self,
                 allow_redirection: bool = True,
                 terminators: Optional[Iterable[str]] = None,
                 multiline_commands: Optional[Iterable[str]] = None,
                 aliases: Optional[Dict[str, str]] = None,
                 shortcuts: Optional[Iterable[Tuple[str, str]]] = None) -> None:
        """Initialize an instance of StatementParser.

        The following will get converted to an immutable tuple before storing internally:
        * terminators
        * multiline commands
        * shortcuts

        :param allow_redirection: (optional) should redirection and pipes be allowed?
        :param terminators: (optional) iterable containing strings which should terminate multiline commands
        :param multiline_commands: (optional) iterable containing the names of commands that accept multiline input
        :param aliases: (optional) dictionary contaiing aliases
        :param shortcuts (optional) an iterable of tuples with each tuple containing the shortcut and the expansion
        """
        self.allow_redirection = allow_redirection
        if terminators is None:
            self.terminators = (constants.MULTILINE_TERMINATOR,)
        else:
            self.terminators = tuple(terminators)
        if multiline_commands is None:
            self.multiline_commands = tuple()
        else:
            self.multiline_commands = tuple(multiline_commands)
        if aliases is None:
            self.aliases = dict()
        else:
            self.aliases = aliases
        if shortcuts is None:
            self.shortcuts = tuple()
        else:
            self.shortcuts = tuple(shortcuts)

        # commands have to be a word, so make a regular expression
        # that matches the first word in the line. This regex has three
        # parts:
        #     - the '\A\s*' matches the beginning of the string (even
        #       if contains multiple lines) and gobbles up any leading
        #       whitespace
        #     - the first parenthesis enclosed group matches one
        #       or more non-whitespace characters with a non-greedy match
        #       (that's what the '+?' part does). The non-greedy match
        #       ensures that this first group doesn't include anything
        #       matched by the second group
        #     - the second parenthesis group must be dynamically created
        #       because it needs to match either whitespace, something in
        #       REDIRECTION_CHARS, one of the terminators, or the end of
        #       the string (\Z matches the end of the string even if it
        #       contains multiple lines)
        #
        invalid_command_chars = []
        invalid_command_chars.extend(constants.QUOTES)
        invalid_command_chars.extend(constants.REDIRECTION_CHARS)
        invalid_command_chars.extend(self.terminators)
        # escape each item so it will for sure get treated as a literal
        second_group_items = [re.escape(x) for x in invalid_command_chars]
        # add the whitespace and end of string, not escaped because they
        # are not literals
        second_group_items.extend([r'\s', r'\Z'])
        # join them up with a pipe
        second_group = '|'.join(second_group_items)
        # build the regular expression
        expr = r'\A\s*(\S*?)({})'.format(second_group)
        self._command_pattern = re.compile(expr)

    def is_valid_command(self, word: str) -> Tuple[bool, str]:
        """Determine whether a word is a valid name for a command.

        Commands can not include redirection characters, whitespace,
        or termination characters. They also cannot start with a
        shortcut.

        If word is not a valid command, return False and error text
        This string is suitable for inclusion in an error message of your
        choice:

        valid, errmsg = statement_parser.is_valid_command('>')
        if not valid:
            errmsg = "Alias {}".format(errmsg)
        """
        valid = False

        if not word:
            return False, 'cannot be an empty string'

        if word.startswith(constants.COMMENT_CHAR):
            return False, 'cannot start with the comment character'

        for (shortcut, _) in self.shortcuts:
            if word.startswith(shortcut):
                # Build an error string with all shortcuts listed
                errmsg = 'cannot start with a shortcut: '
                errmsg += ', '.join(shortcut for (shortcut, _) in self.shortcuts)
                return False, errmsg

        errmsg = 'cannot contain: whitespace, quotes, '
        errchars = []
        errchars.extend(constants.REDIRECTION_CHARS)
        errchars.extend(self.terminators)
        errmsg += ', '.join([shlex.quote(x) for x in errchars])

        match = self._command_pattern.search(word)
        if match:
            if word == match.group(1):
                valid = True
                errmsg = ''
        return valid, errmsg

    def tokenize(self, line: str, expand: bool = True) -> List[str]:
        """
        Lex a string into a list of tokens. Shortcuts and aliases are expanded and comments are removed

        :param line: the command line being lexed
        :param expand: If True, then aliases and shortcuts will be expanded.
                       Set this to False if no expansion should occur because the command name is already known.
                       Otherwise the command could be expanded if it matched an alias name. This is for cases where
                       a do_* method was called manually (e.g do_help('alias').
        :return: A list of tokens
        :raises ValueError if there are unclosed quotation marks.
        """

        # expand shortcuts and aliases
        if expand:
            line = self._expand(line)

        # check if this line is a comment
        if line.lstrip().startswith(constants.COMMENT_CHAR):
            return []

        # split on whitespace
        tokens = shlex_split(line)

        # custom lexing
        tokens = self._split_on_punctuation(tokens)
        return tokens

    def parse(self, line: str, expand: bool = True) -> Statement:
        """
        Tokenize the input and parse it into a Statement object, stripping
        comments, expanding aliases and shortcuts, and extracting output
        redirection directives.

        :param line: the command line being parsed
        :param expand: If True, then aliases and shortcuts will be expanded.
                       Set this to False if no expansion should occur because the command name is already known.
                       Otherwise the command could be expanded if it matched an alias name. This is for cases where
                       a do_* method was called manually (e.g do_help('alias').
        :return: A parsed Statement
        :raises ValueError if there are unclosed quotation marks
        """

        # handle the special case/hardcoded terminator of a blank line
        # we have to do this before we tokenize because tokenizing
        # destroys all unquoted whitespace in the input
        terminator = ''
        if line[-1:] == constants.LINE_FEED:
            terminator = constants.LINE_FEED

        command = ''
        args = ''
        arg_list = []

        # lex the input into a list of tokens
        tokens = self.tokenize(line, expand)

        # of the valid terminators, find the first one to occur in the input
        terminator_pos = len(tokens) + 1
        for pos, cur_token in enumerate(tokens):
            for test_terminator in self.terminators:
                if cur_token.startswith(test_terminator):
                    terminator_pos = pos
                    terminator = test_terminator
                    # break the inner loop, and we want to break the
                    # outer loop too
                    break
            else:
                # this else clause is only run if the inner loop
                # didn't execute a break. If it didn't, then
                # continue to the next iteration of the outer loop
                continue
            # inner loop was broken, break the outer
            break

        if terminator:
            if terminator == constants.LINE_FEED:
                terminator_pos = len(tokens) + 1

            # everything before the first terminator is the command and the args
            (command, args) = self._command_and_args(tokens[:terminator_pos])
            arg_list = tokens[1:terminator_pos]
            # we will set the suffix later
            # remove all the tokens before and including the terminator
            tokens = tokens[terminator_pos + 1:]
        else:
            (testcommand, testargs) = self._command_and_args(tokens)
            if testcommand in self.multiline_commands:
                # no terminator on this line but we have a multiline command
                # everything else on the line is part of the args
                # because redirectors can only be after a terminator
                command = testcommand
                args = testargs
                arg_list = tokens[1:]
                tokens = []

        # check for a pipe to a shell process
        # if there is a pipe, everything after the pipe needs to be passed
        # to the shell, even redirected output
        # this allows '(Cmd) say hello | wc > countit.txt'
        try:
            # find the first pipe if it exists
            pipe_pos = tokens.index(constants.REDIRECTION_PIPE)
            # save everything after the first pipe as tokens
            pipe_to = tokens[pipe_pos + 1:]

            for pos, cur_token in enumerate(pipe_to):
                unquoted_token = utils.strip_quotes(cur_token)
                pipe_to[pos] = os.path.expanduser(unquoted_token)

            # remove all the tokens after the pipe
            tokens = tokens[:pipe_pos]
        except ValueError:
            # no pipe in the tokens
            pipe_to = []

        # check for output redirect
        output = ''
        output_to = ''
        try:
            output_pos = tokens.index(constants.REDIRECTION_OUTPUT)
            output = constants.REDIRECTION_OUTPUT

            # Check if we are redirecting to a file
            if len(tokens) > output_pos + 1:
                unquoted_path = utils.strip_quotes(tokens[output_pos + 1])
                output_to = os.path.expanduser(unquoted_path)

            # remove all the tokens after the output redirect
            tokens = tokens[:output_pos]
        except ValueError:
            pass

        try:
            output_pos = tokens.index(constants.REDIRECTION_APPEND)
            output = constants.REDIRECTION_APPEND

            # Check if we are redirecting to a file
            if len(tokens) > output_pos + 1:
                unquoted_path = utils.strip_quotes(tokens[output_pos + 1])
                output_to = os.path.expanduser(unquoted_path)

            # remove all tokens after the output redirect
            tokens = tokens[:output_pos]
        except ValueError:
            pass

        if terminator:
            # whatever is left is the suffix
            suffix = ' '.join(tokens)
        else:
            # no terminator, so whatever is left is the command and the args
            suffix = ''
            if not command:
                # command could already have been set, if so, don't set it again
                (command, args) = self._command_and_args(tokens)
                arg_list = tokens[1:]

        # set multiline
        if command in self.multiline_commands:
            multiline_command = command
        else:
            multiline_command = ''

        # build the statement
        statement = Statement(args,
                              raw=line,
                              command=command,
                              arg_list=arg_list,
                              multiline_command=multiline_command,
                              terminator=terminator,
                              suffix=suffix,
                              pipe_to=pipe_to,
                              output=output,
                              output_to=output_to,
                              )
        return statement

    def parse_command_only(self, rawinput: str) -> Statement:
        """Partially parse input into a Statement object.

        The command is identified, and shortcuts and aliases are expanded.
        Multiline commands are identified, but terminators and output
        redirection are not parsed.

        This method is used by tab completion code and therefore must not
        generate an exception if there are unclosed quotes.

        The `Statement` object returned by this method can at most contain values
        in the following attributes:
          - args
          - raw
          - command
          - multiline_command

        `Statement.args` includes all output redirection clauses and command
        terminators.

        Different from parse(), this method does not remove redundant whitespace
        within args. However, it does ensure args has no leading or trailing
        whitespace.
        """
        # expand shortcuts and aliases
        line = self._expand(rawinput)

        command = ''
        args = ''
        match = self._command_pattern.search(line)
        if match:
            # we got a match, extract the command
            command = match.group(1)

            # take everything from the end of the first match group to
            # the end of the line as the arguments (stripping leading
            # and trailing spaces)
            args = line[match.end(1):].strip()
            # if the command is empty that means the input was either empty
            # or something weird like '>'. args should be empty if we couldn't
            # parse a command
            if not command or not args:
                args = ''

        # set multiline
        if command in self.multiline_commands:
            multiline_command = command
        else:
            multiline_command = ''

        # build the statement
        statement = Statement(args,
                              raw=rawinput,
                              command=command,
                              multiline_command=multiline_command,
                              )
        return statement

    def get_command_arg_list(self, command_name: str, to_parse: Union[Statement, str],
                             preserve_quotes: bool) -> Tuple[Statement, List[str]]:
        """
        Called by the argument_list and argparse wrappers to retrieve just the arguments being
        passed to their do_* methods as a list.

        :param command_name: name of the command being run
        :param to_parse: what is being passed to the do_* method. It can be one of two types:
                         1. An already parsed Statement
                         2. An argument string in cases where a do_* method is explicitly called
                            e.g.: Calling do_help('alias create') would cause to_parse to be 'alias create'

                            In this case, the string will be converted to a Statement and returned along
                            with the argument list.

        :param preserve_quotes: if True, then quotes will not be stripped from the arguments
        :return: A tuple containing:
                    The Statement used to retrieve the arguments
                    The argument list
        """
        # Check if to_parse needs to be converted to a Statement
        if not isinstance(to_parse, Statement):
            to_parse = self.parse(command_name + ' ' + to_parse, expand=False)

        if preserve_quotes:
            return to_parse, to_parse.arg_list
        else:
            return to_parse, to_parse.argv[1:]

    def _expand(self, line: str) -> str:
        """Expand shortcuts and aliases"""

        # expand aliases
        # make a copy of aliases so we can edit it
        tmp_aliases = list(self.aliases.keys())
        keep_expanding = bool(tmp_aliases)
        while keep_expanding:
            for cur_alias in tmp_aliases:
                keep_expanding = False
                # apply our regex to line
                match = self._command_pattern.search(line)
                if match:
                    # we got a match, extract the command
                    command = match.group(1)
                    if command and command == cur_alias:
                        # rebuild line with the expanded alias
                        line = self.aliases[cur_alias] + match.group(2) + line[match.end(2):]
                        tmp_aliases.remove(cur_alias)
                        keep_expanding = bool(tmp_aliases)
                        break

        # expand shortcuts
        for (shortcut, expansion) in self.shortcuts:
            if line.startswith(shortcut):
                # If the next character after the shortcut isn't a space, then insert one
                shortcut_len = len(shortcut)
                if len(line) == shortcut_len or line[shortcut_len] != ' ':
                    expansion += ' '

                # Expand the shortcut
                line = line.replace(shortcut, expansion, 1)
                break
        return line

    @staticmethod
    def _command_and_args(tokens: List[str]) -> Tuple[str, str]:
        """Given a list of tokens, return a tuple of the command
        and the args as a string.
        """
        command = ''
        args = ''

        if tokens:
            command = tokens[0]

        if len(tokens) > 1:
            args = ' '.join(tokens[1:])

        return command, args

    def _split_on_punctuation(self, tokens: List[str]) -> List[str]:
        """Further splits tokens from a command line using punctuation characters

        Punctuation characters are treated as word breaks when they are in
        unquoted strings. Each run of punctuation characters is treated as a
        single token.

        :param tokens: the tokens as parsed by shlex
        :return: the punctuated tokens
        """
        punctuation = []
        punctuation.extend(self.terminators)
        if self.allow_redirection:
            punctuation.extend(constants.REDIRECTION_CHARS)

        punctuated_tokens = []

        for cur_initial_token in tokens:

            # Save tokens up to 1 character in length or quoted tokens. No need to parse these.
            if len(cur_initial_token) <= 1 or cur_initial_token[0] in constants.QUOTES:
                punctuated_tokens.append(cur_initial_token)
                continue

            # Iterate over each character in this token
            cur_index = 0
            cur_char = cur_initial_token[cur_index]

            # Keep track of the token we are building
            new_token = ''

            while True:
                if cur_char not in punctuation:

                    # Keep appending to new_token until we hit a punctuation char
                    while cur_char not in punctuation:
                        new_token += cur_char
                        cur_index += 1
                        if cur_index < len(cur_initial_token):
                            cur_char = cur_initial_token[cur_index]
                        else:
                            break

                else:
                    cur_punc = cur_char

                    # Keep appending to new_token until we hit something other than cur_punc
                    while cur_char == cur_punc:
                        new_token += cur_char
                        cur_index += 1
                        if cur_index < len(cur_initial_token):
                            cur_char = cur_initial_token[cur_index]
                        else:
                            break

                # Save the new token
                punctuated_tokens.append(new_token)
                new_token = ''

                # Check if we've viewed all characters
                if cur_index >= len(cur_initial_token):
                    break

        return punctuated_tokens
