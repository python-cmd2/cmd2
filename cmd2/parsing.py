#
# -*- coding: utf-8 -*-
"""Statement parsing classes for cmd2"""

import re
import shlex
from typing import List, Tuple

from . import constants

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
    :type args:             str
    :var terminator:        the charater which terminated the multiline command, if
                            there was one
    :type terminator:       str or None
    :var suffix:            characters appearing after the terminator but before output
                            redirection, if any
    :type suffix:           str or None
    :var pipe_to:           if output was piped to a shell command, the shell command
    :type pipe_to:          str or None
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
        # has to be an empty string for compatibility with standard library cmd
        self.args = ''
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
        return '{} {}'.format('' if self.command is None else self.command, self.args).strip()


class StatementParser():
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

        # aliases have to be a word, so make a regular expression
        # that matches the first word in the line. This regex has two
        # parts, the first parenthesis enclosed group matches one
        # or more non-whitespace characters, and the second group
        # matches either a whitespace character or the end of the
        # string. We use \A and \Z to ensure we always match the
        # beginning and end of a string that may have multiple
        # lines
        self.command_pattern = re.compile(r'\A(\S+)(\s|\Z)')


    def tokenize(self, line: str) -> List[str]:
        """Lex a string into a list of tokens.

        Comments are removed, and shortcuts and aliases are expanded.
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
        """

        # handle the special case/hardcoded terminator of a blank line
        # we have to do this before we tokenize because tokenizing
        # destroys all unquoted whitespace in the input
        terminator = None
        if rawinput[-1:] == LINE_FEED:
            terminator = LINE_FEED

        command = None
        args = ''

        # lex the input into a list of tokens
        tokens = self.tokenize(rawinput)

        # of the valid terminators, find the first one to occur in the input
        terminator_pos = len(tokens)+1
        for test_terminator in self.terminators:
            try:
                pos = tokens.index(test_terminator)
                if pos < terminator_pos:
                    terminator_pos = pos
                    terminator = test_terminator
                    break
            except ValueError:
                # the terminator is not in the tokens
                pass

        if terminator:
            if terminator == LINE_FEED:
                terminator_pos = len(tokens)+1
            else:
                terminator_pos = tokens.index(terminator)
            # everything before the first terminator is the command and the args
            (command, args) = self._command_and_args(tokens[:terminator_pos])
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
                tokens = []

        # check for output redirect
        output = None
        output_to = None
        try:
            output_pos = tokens.index('>')
            output = '>'
            output_to = ' '.join(tokens[output_pos+1:])
            # remove all the tokens after the output redirect
            tokens = tokens[:output_pos]
        except ValueError:
            pass

        try:
            output_pos = tokens.index('>>')
            output = '>>'
            output_to = ' '.join(tokens[output_pos+1:])
            # remove all tokens after the output redirect
            tokens = tokens[:output_pos]
        except ValueError:
            pass

        # check for pipes
        try:
            # find the first pipe if it exists
            pipe_pos = tokens.index('|')
            # save everything after the first pipe
            pipe_to = ' '.join(tokens[pipe_pos+1:])
            # remove all the tokens after the pipe
            tokens = tokens[:pipe_pos]
        except ValueError:
            # no pipe in the tokens
            pipe_to = None

        if terminator:
            # whatever is left is the suffix
            suffix = ' '.join(tokens)
        else:
            # no terminator, so whatever is left is the command and the args
            suffix = None
            if not command:
                # command could already have been set, if so, don't set it again
                (command, args) = self._command_and_args(tokens)

        # set multiline
        if command in self.multiline_commands:
            multiline_command = command
        else:
            multiline_command = None

        # build the statement
        statement = Statement(args)
        statement.raw = rawinput
        statement.command = command
        statement.args = args
        statement.terminator = terminator
        statement.output = output
        statement.output_to = output_to
        statement.pipe_to = pipe_to
        statement.suffix = suffix
        statement.multiline_command = multiline_command
        return statement

    def parse_command_only(self, rawinput: str) -> Statement:
        """Partially parse input into a Statement object. The command is
        identified, and shortcuts and aliases are expanded.
        Terminators, multiline commands, and output redirection are not
        parsed.
        """
        # lex the input into a list of tokens
        tokens = self.tokenize(rawinput)

        # parse out the command and everything else
        (command, args) = self._command_and_args(tokens)

        # build the statement
        statement = Statement(args)
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
                match = self.command_pattern.search(line)
                if match:
                    # we got a match, extract the command
                    command = match.group(1)
                    if command == cur_alias:
                        # rebuild line with the expanded alias
                        line = self.aliases[cur_alias] + match.group(2) + line[match.end(2):]
                        tmp_aliases.remove(cur_alias)
                        keep_expanding = bool(tmp_aliases)
                        break

        # expand shortcuts
        for (shortcut, expansion) in self.shortcuts:
            if  line.startswith(shortcut):
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
        """given a list of tokens, and return a tuple of the command
        and the args as a string.
        """
        command = None
        args = ''

        if tokens:
            command = tokens[0]

        if len(tokens) > 1:
            args = ' '.join(tokens[1:])

        return (command, args)

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

        :param initial_tokens: the tokens as parsed by shlex
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
