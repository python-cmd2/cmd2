#
# -*- coding: utf-8 -*-
"""Statement parsing classes for cmd2"""

import re
import shlex
from typing import List, Tuple

from . import constants
from . import utils

LINE_FEED = '\n'


class Statement(str):
    """String subclass with additional attributes to store the results of parsing.

    The cmd module in the standard library passes commands around as a
    string. To retain backwards compatibility, cmd2 does the same. However, we
    need a place to capture the additional output of the command parsing, so we add
    our own attributes to this subclass.

    The string portion of the class contains the arguments, but not the command, nor
    the output redirection clauses.

    :var raw:               string containing exactly what we input by the user
    :type raw:              str
    :var command:           the command, i.e. the first whitespace delimited word
    :type command:          str or None
    :var multiline_command: if the command is a multiline command, the name of the
                            command, otherwise None
    :type command:          str or None
    :var args:              the arguments to the command, not including any output
                            redirection or terminators. quoted arguments remain
                            quoted.
    :type args:             str or None
    :var: argv:             a list of arguments a la sys.argv. Quotes, if any, are removed
                            from the elements of the list, and aliases and shortcuts
                            are expanded
    :type argv:             list
    :var terminator:        the charater which terminated the multiline command, if
                            there was one
    :type terminator:       str or None
    :var suffix:            characters appearing after the terminator but before output
                            redirection, if any
    :type suffix:           str or None
    :var pipe_to:           if output was piped to a shell command, the shell command
                            as a list of tokens
    :type pipe_to:          list
    :var output:            if output was redirected, the redirection token, i.e. '>>'
    :type output:           str or None
    :var output_to:         if output was redirected, the destination, usually a filename
    :type output_to:        str or None

    """
    def __init__(self, obj):
        super().__init__()
        self.raw = str(obj)
        self.command = None
        self.multiline_command = None
        self.args = None
        self.argv = None
        self.terminator = None
        self.suffix = None
        self.pipe_to = None
        self.output = None
        self.output_to = None

    @property
    def command_and_args(self):
        """Combine command and args with a space separating them.

        Quoted arguments remain quoted.
        """
        if self.command and self.args:
            rtn = '{} {}'.format(self.command, self.args)
        elif self.command:
            # we are trusting that if we get here that self.args is None
            rtn = self.command
        else:
            rtn = None
        return rtn


class StatementParser:
    """Parse raw text into command components.

    Shortcuts is a list of tuples with each tuple containing the shortcut and the expansion.
    """
    def __init__(
            self,
            allow_redirection=True,
            terminators=None,
            multiline_commands=None,
            aliases=None,
            shortcuts=None,
    ):
        self.allow_redirection = allow_redirection
        if terminators is None:
            self.terminators = [';']
        else:
            self.terminators = terminators
        if multiline_commands is None:
            self.multiline_commands = []
        else:
            self.multiline_commands = multiline_commands
        if aliases is None:
            self.aliases = {}
        else:
            self.aliases = aliases
        if shortcuts is None:
            self.shortcuts = []
        else:
            self.shortcuts = shortcuts

        # this regular expression matches C-style comments and quoted
        # strings, i.e. stuff between single or double quote marks
        # it's used with _comment_replacer() to strip out the C-style
        # comments, while leaving C-style comments that are inside either
        # double or single quotes.
        #
        # this big regular expression can be broken down into 3 regular
        # expressions that are OR'ed together.
        #
        # /\*.*?(\*/|$)          matches C-style comments, with an optional
        #                        closing '*/'. The optional closing '*/' is
        #                        there to retain backward compatibility with
        #                        the pyparsing implementation of cmd2 < 0.9.0
        # \'(?:\\.|[^\\\'])*\'   matches a single quoted string, allowing
        #                        for embedded backslash escaped single quote
        #                        marks
        # "(?:\\.|[^\\"])*"      matches a double quoted string, allowing
        #                        for embedded backslash escaped double quote
        #                        marks
        #
        # by way of reminder the (?:...) regular expression syntax is just
        # a non-capturing version of regular parenthesis. We need the non-
        # capturing syntax because _comment_replacer() looks at match
        # groups
        self.comment_pattern = re.compile(
            r'/\*.*?(\*/|$)|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
            re.DOTALL | re.MULTILINE
        )

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
        invalid_command_chars.extend(terminators)
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
        """Determine whether a word is a valid alias.

        Aliases can not include redirection characters, whitespace,
        or termination characters.

        If word is not a valid command, return False and a comma
        separated string of characters that can not appear in a command.
        This string is suitable for inclusion in an error message of your
        choice:

        valid, invalidchars = statement_parser.is_valid_command('>')
        if not valid:
            errmsg = "Aliases can not contain: {}".format(invalidchars)
        """
        valid = False

        errmsg = 'whitespace, quotes, '
        errchars = []
        errchars.extend(constants.REDIRECTION_CHARS)
        errchars.extend(self.terminators)
        errmsg += ', '.join([shlex.quote(x) for x in errchars])

        match = self._command_pattern.search(word)
        if match:
            if word == match.group(1):
                valid = True
                errmsg = None
        return valid, errmsg

    def tokenize(self, line: str) -> List[str]:
        """Lex a string into a list of tokens.

        Comments are removed, and shortcuts and aliases are expanded.

        Raises ValueError if there are unclosed quotation marks.
        """

        # strip C-style comments
        # shlex will handle the python/shell style comments for us
        line = re.sub(self.comment_pattern, self._comment_replacer, line)

        # expand shortcuts and aliases
        line = self._expand(line)

        # split on whitespace
        lexer = shlex.shlex(line, posix=False)
        lexer.whitespace_split = True

        # custom lexing
        tokens = self._split_on_punctuation(list(lexer))
        return tokens

    def parse(self, rawinput: str) -> Statement:
        """Tokenize the input and parse it into a Statement object, stripping
        comments, expanding aliases and shortcuts, and extracting output
        redirection directives.

        Raises ValueError if there are unclosed quotation marks.
        """

        # handle the special case/hardcoded terminator of a blank line
        # we have to do this before we tokenize because tokenizing
        # destroys all unquoted whitespace in the input
        terminator = None
        if rawinput[-1:] == LINE_FEED:
            terminator = LINE_FEED

        command = None
        args = None
        argv = None

        # lex the input into a list of tokens
        tokens = self.tokenize(rawinput)

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
            if terminator == LINE_FEED:
                terminator_pos = len(tokens)+1

            # everything before the first terminator is the command and the args
            argv = tokens[:terminator_pos]
            (command, args) = self._command_and_args(argv)
            # we will set the suffix later
            # remove all the tokens before and including the terminator
            tokens = tokens[terminator_pos+1:]
        else:
            (testcommand, testargs) = self._command_and_args(tokens)
            if testcommand in self.multiline_commands:
                # no terminator on this line but we have a multiline command
                # everything else on the line is part of the args
                # because redirectors can only be after a terminator
                command = testcommand
                args = testargs
                argv = tokens
                tokens = []

        # check for a pipe to a shell process
        # if there is a pipe, everything after the pipe needs to be passed
        # to the shell, even redirected output
        # this allows '(Cmd) say hello | wc > countit.txt'
        try:
            # find the first pipe if it exists
            pipe_pos = tokens.index(constants.REDIRECTION_PIPE)
            # save everything after the first pipe as tokens
            pipe_to = tokens[pipe_pos+1:]
            # remove all the tokens after the pipe
            tokens = tokens[:pipe_pos]
        except ValueError:
            # no pipe in the tokens
            pipe_to = None

        # check for output redirect
        output = None
        output_to = None
        try:
            output_pos = tokens.index(constants.REDIRECTION_OUTPUT)
            output = constants.REDIRECTION_OUTPUT
            output_to = ' '.join(tokens[output_pos+1:])
            # remove all the tokens after the output redirect
            tokens = tokens[:output_pos]
        except ValueError:
            pass

        try:
            output_pos = tokens.index(constants.REDIRECTION_APPEND)
            output = constants.REDIRECTION_APPEND
            output_to = ' '.join(tokens[output_pos+1:])
            # remove all tokens after the output redirect
            tokens = tokens[:output_pos]
        except ValueError:
            pass

        if terminator:
            # whatever is left is the suffix
            suffix = ' '.join(tokens)
        else:
            # no terminator, so whatever is left is the command and the args
            suffix = None
            if not command:
                # command could already have been set, if so, don't set it again
                argv = tokens
                (command, args) = self._command_and_args(argv)

        # set multiline
        if command in self.multiline_commands:
            multiline_command = command
        else:
            multiline_command = None

        # build the statement
        # string representation of args must be an empty string instead of
        # None for compatibility with standard library cmd
        statement = Statement('' if args is None else args)
        statement.raw = rawinput
        statement.command = command
        # if there are no args we will use None since we don't have to worry
        # about compatibility with standard library cmd
        statement.args = args
        statement.argv = list(map(lambda x: utils.strip_quotes(x), argv))
        statement.terminator = terminator
        statement.output = output
        statement.output_to = output_to
        statement.pipe_to = pipe_to
        statement.suffix = suffix
        statement.multiline_command = multiline_command
        return statement

    def parse_command_only(self, rawinput: str) -> Statement:
        """Partially parse input into a Statement object.

        The command is identified, and shortcuts and aliases are expanded.
        Terminators, multiline commands, and output redirection are not
        parsed.

        This method is used by tab completion code and therefore must not
        generate an exception if there are unclosed quotes.

        The Statement object returned by this method can at most contained
        values in the following attributes:
          - raw
          - command
          - args

        Different from parse(), this method does not remove redundant whitespace
        within statement.args. It does however, ensure args does not have leading
        or trailing whitespace.
        """
        # expand shortcuts and aliases
        line = self._expand(rawinput)

        command = None
        args = None
        match = self._command_pattern.search(line)
        if match:
            # we got a match, extract the command
            command = match.group(1)
            # the match could be an empty string, if so, turn it into none
            if not command:
                command = None
            # the _command_pattern regex is designed to match the spaces
            # between command and args with a second match group. Using
            # the end of the second match group ensures that args has
            # no leading whitespace. The rstrip() makes sure there is
            # no trailing whitespace
            args = line[match.end(2):].rstrip()
            # if the command is none that means the input was either empty
            # or something wierd like '>'. args should be None if we couldn't
            # parse a command
            if not command or not args:
                args = None

        # build the statement
        # string representation of args must be an empty string instead of
        # None for compatibility with standard library cmd
        statement = Statement('' if args is None else args)
        statement.raw = rawinput
        statement.command = command
        statement.args = args
        return statement

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

        The args string will be '' instead of None to retain backwards compatibility
        with cmd in the standard library.
        """
        command = None
        args = None

        if tokens:
            command = tokens[0]

        if len(tokens) > 1:
            args = ' '.join(tokens[1:])

        return command, args

    @staticmethod
    def _comment_replacer(match):
        matched_string = match.group(0)
        if matched_string.startswith('/'):
            # the matched string was a comment, so remove it
            return ''
        # the matched string was a quoted string, return the match
        return matched_string

    def _split_on_punctuation(self, tokens: List[str]) -> List[str]:
        """
        # Further splits tokens from a command line using punctuation characters
        # as word breaks when they are in unquoted strings. Each run of punctuation
        # characters is treated as a single token.

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
