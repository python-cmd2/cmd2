#
# -*- coding: utf-8 -*-
"""Statement parsing classes for cmd2"""

import re
import shlex

import cmd2

BLANK_LINE = '\n'

class Statement(str):
    """String subclass with additional attributes to store the results of parsing.
    
    The cmd module in the standard library passes commands around as a
    string. To retain backwards compatibility, cmd2 does the same. However, we
    need a place to capture the additional output of the command parsing, so we add
    our own attributes to this subclass.

    The string portion of the class contains the arguments, but not the command, nor
    the output redirection clauses.
    """
    def __init__(self, object):
        self.raw = str(object)
        self.command = None
        self.multilineCommand = None
        # has to be an empty string for compatibility with standard library cmd
        self.args = ''
        self.terminator = None
        self.suffix = None
        self.pipeTo = None
        self.output = None
        self.outputTo = None

class StatementParser():
    """Parse raw text into command components.
    
    Shortcuts is a list of tuples with each tuple containing the shortcut and the expansion.
    """
    def __init__(
            self,
            quotes=['"', "'"],
            allow_redirection=True,
            redirection_chars=['|', '<', '>'],
            terminators=[';'],
            multilineCommands = [],
            aliases = {},
            shortcuts = [],
        ):
        self.quotes = quotes
        self.allow_redirection = allow_redirection
        self.redirection_chars = redirection_chars
        self.terminators = terminators
        self.multilineCommands = multilineCommands
        self.aliases = aliases
        self.shortcuts = shortcuts

    def parse(self, rawinput):
        # strip C-style comments
        # shlex will handle the python/shell style comments for us
        def replacer(match):
                s = match.group(0)
                if s.startswith('/'):
                    # treat the removed comment as an empty string
                    return ''
                else:
                    return s
        pattern = re.compile(
            #r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
            r'/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
            re.DOTALL | re.MULTILINE
        )
        rawinput = re.sub(pattern, replacer, rawinput)
        line = rawinput

        # expand shortcuts, have to do this first because
        # a shortcut can expand into multiple tokens, ie '!ls' becomes
        # 'shell ls'
        for (shortcut, expansion) in self.shortcuts:
            if  line.startswith(shortcut):
                # If the next character after the shortcut isn't a space, then insert one
                shortcut_len = len(shortcut)
                if len(line) == shortcut_len or line[shortcut_len] != ' ':
                    expansion += ' '

                # Expand the shortcut
                line = line.replace(shortcut, expansion, 1)
                break

        # handle the special case/hardcoded terminator of a blank line
        # we have to do this before we shlex on whitespace because it
        # destroys all unquoted whitespace in the input
        terminator = None
        if line[-1:] == BLANK_LINE:
            terminator = BLANK_LINE

        s = shlex.shlex(line, posix=False)
        s.whitespace_split = True
        tokens = self.split_on_punctuation(list(s))
        
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
            if terminator == BLANK_LINE:
                terminator_pos = len(tokens)+1
            else:
                terminator_pos = tokens.index(terminator)
            # everything before the first terminator is the command and the args
            (command, args) = self._command_and_args(tokens[:terminator_pos])
            #terminator = tokens[terminator_pos]
            # we will set the suffix later
            # remove all the tokens before and including the terminator
            tokens = tokens[terminator_pos+1:]

        # check for input from file
        inputFrom = None
        try:
            input_pos = tokens.index('<')
            inputFrom = ' '.join(tokens[input_pos+1:])
            tokens = tokens[:input_pos]
        except ValueError:
            pass


        # check for output redirect
        output = None
        outputTo = None
        try:
            output_pos = tokens.index('>')
            output = '>'
            outputTo = ' '.join(tokens[output_pos+1:])
            # remove all the tokens after the output redirect
            tokens = tokens[:output_pos]
        except ValueError:
            pass

        try:
            output_pos = tokens.index('>>')
            output = '>>'
            outputTo = ' '.join(tokens[output_pos+1:])
            # remove all tokens after the output redirect
            tokens = tokens[:output_pos]
        except ValueError:
            pass

        # check for pipes
        try:
            # find the first pipe if it exists
            pipe_pos = tokens.index('|')
            # set everything after the first pipe to result.pipeTo
            pipeTo = ' '.join(tokens[pipe_pos+1:])
            # remove all the tokens after the pipe
            tokens = tokens[:pipe_pos]
        except ValueError:
            # no pipe in the tokens
            pipeTo = None
        
        if terminator:
            # whatever is left is the suffix
            suffix = ' '.join(tokens)
        else:
            # no terminator, so whatever is left is the command and the args
            suffix = None
            (command, args) = self._command_and_args(tokens)

        # expand aliases
        # make a copy of aliases so we can edit it
        tmp_aliases = list(self.aliases.keys())
        keep_expanding = len(tmp_aliases) > 0

        while keep_expanding:
            for cur_alias in tmp_aliases:
                keep_expanding = False
                if command == cur_alias:
                    command = self.aliases[cur_alias]
                    tmp_aliases.remove(cur_alias)
                    keep_expanding = len(tmp_aliases) > 0
                    break

        # set multiline
        if command in self.multilineCommands:
            multilineCommand = command
            # return no arguments if this is a "partial" command,
            # i.e. we have a multiline command but no terminator yet
            if not terminator:
                args = ''
        else:
            multilineCommand = None

        # build Statement object
        result = Statement(args)
        result.raw = rawinput
        result.command = command
        result.args = args
        result.terminator = terminator
        result.inputFrom = inputFrom
        result.output = output
        result.outputTo = outputTo
        result.pipeTo = pipeTo
        result.suffix = suffix
        result.multilineCommand = multilineCommand
        return result
    
    def _command_and_args(self, tokens):
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
