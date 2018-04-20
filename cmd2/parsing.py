#
# -*- coding: utf-8 -*-
"""Command parsing classes for cmd2"""

import re
import shlex

import cmd2

class Command():
    """Store the results of a parsed command."""
    pass

class CommandParser():
    """Parse raw text into command components."""
    def __init__(
            self,
            quotes=['"', "'"],
            allow_redirection=True,
            redirection_chars=['|', '<', '>'],
            terminators=[';'],
            multilineCommands = [],
        ):
        self.quotes = quotes
        self.allow_redirection = allow_redirection
        self.redirection_chars = redirection_chars
        self.terminators = terminators
        self.multilineCommands = multilineCommands

    def parseString(self, rawinput):
        result = Command()
        result.raw = rawinput
        result.command = None
        result.multilineCommand = None
        result.args = None
        result.terminator = None
        result.suffix = None
        result.pipeTo = None
        result.output = None
        result.outputTo = None

        # strip C-style and C++-style comments
        # shlex will handle the python/shell style comments for us
        def replacer(match):
                s = match.group(0)
                if s.startswith('/'):
                    # treat the removed comment as an empty string
                    return ''
                else:
                    return s
        pattern = re.compile(
            r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
            re.DOTALL | re.MULTILINE
        )
        rawinput = re.sub(pattern, replacer, rawinput)

        s = shlex.shlex(rawinput, posix=False)
        s.whitespace_split = True
        tokens = self.split_on_punctuation(list(s))
        
        # of the valid terminators, find the first one to occur in the input
        terminator_pos = len(tokens)+1
        terminator = None
        for test_terminator in self.terminators:
            try:
                pos = tokens.index(test_terminator)
                if pos < terminator_pos:
                    terminator_pos = pos
                    terminator = test_terminator
            except ValueError:
                # the terminator is not in the tokens
                pass

        if terminator:
            terminator_pos = tokens.index(terminator)
            # everything before the first terminator is the command and the args
            (result.command, result.args) = self._command_and_args(tokens[:terminator_pos])
            result.terminator = tokens[terminator_pos]
            # we will set the suffix later
            # remove all the tokens before and including the terminator
            tokens = tokens[terminator_pos+1:]

        # check for input from file
        try:
            if tokens[0] == '<':
                result.inputFrom = ' '.join(tokens[1:])
                tokens = []
        except IndexError:
            # no input from file
            pass

        # check for output redirect
        try:
            output_pos = tokens.index('>')
            result.output = '>'
            result.outputTo = ' '.join(tokens[output_pos+1:])
            # remove all the tokens after the output redirect
            tokens = tokens[:output_pos]
        except ValueError:
            pass

        # check for paste buffer
        try:
            output_pos = tokens.index('>>')
            result.output = '>>'
            # remove all tokens after the output redirect
            tokens = tokens[:output_pos]
        except ValueError:
            pass

        # check for pipes
        try:
            # find the first pipe if it exists
            pipe_pos = tokens.index('|')
            # set everything after the first pipe to result.pipeTo
            result.pipeTo = ' '.join(tokens[pipe_pos+1:])
            # remove all the tokens after the pipe
            tokens = tokens[:pipe_pos]
        except ValueError:
            # no pipe in the tokens
            pass
        
        if result.terminator:
            # whatever is left is the suffix
            result.suffix = ' '.join(tokens)
        else:
            # no terminator, so whatever is left is the command and the args
            (result.command, result.args) = self._command_and_args(tokens)

        if result.command in self.multilineCommands:
            result.multilineCommand = result.command

        return result
    
    def _command_and_args(self, tokens):
        """given a list of tokens, and return a tuple of the command
        and the args as a string.
        """
        command = None
        args = None

        if tokens:
            command = tokens[0]

        if len(tokens) > 1:
            args = ' '.join(tokens[1:])

        return (command, args)

    def split_on_punctuation(self, initial_tokens):
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
            punctuation.extend(self.redirection_chars)

        punctuated_tokens = []

        for cur_initial_token in initial_tokens:

            # Save tokens up to 1 character in length or quoted tokens. No need to parse these.
            if len(cur_initial_token) <= 1 or cur_initial_token[0] in self.quotes:
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
