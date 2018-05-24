# coding=utf-8
"""Hijack the ArgComplete's bash completion handler to return AutoCompleter results"""

try:
    # check if argcomplete is installed
    import argcomplete
except ImportError:  # pragma: no cover
    # not installed, skip the rest of the file
    DEFAULT_COMPLETER = None
else:
    # argcomplete is installed

    # Newer versions of argcomplete have FilesCompleter at top level, older versions only have it under completers
    try:
        DEFAULT_COMPLETER = argcomplete.FilesCompleter()
    except AttributeError:
        DEFAULT_COMPLETER = argcomplete.completers.FilesCompleter()

    from cmd2.argparse_completer import ACTION_ARG_CHOICES, ACTION_SUPPRESS_HINT
    from contextlib import redirect_stdout
    import copy
    from io import StringIO
    import os
    import shlex
    import sys

    from . import constants
    from . import utils


    def tokens_for_completion(line, endidx):
        """
        Used by tab completion functions to get all tokens through the one being completed
        :param line: str - the current input line with leading whitespace removed
        :param endidx: int - the ending index of the prefix text
        :return: A 4 item tuple where the items are
                 On Success
                     tokens: list of unquoted tokens
                             this is generally the list needed for tab completion functions
                     raw_tokens: list of tokens with any quotes preserved
                                 this can be used to know if a token was quoted or is missing a closing quote
                     begidx: beginning of last token
                     endidx: cursor position

                     Both lists are guaranteed to have at least 1 item
                     The last item in both lists is the token being tab completed

                 On Failure
                    Both items are None
        """
        unclosed_quote = ''
        quotes_to_try = copy.copy(constants.QUOTES)

        tmp_line = line[:endidx]
        tmp_endidx = endidx

        # Parse the line into tokens
        while True:
            try:
                # Use non-POSIX parsing to keep the quotes around the tokens
                initial_tokens = shlex.split(tmp_line[:tmp_endidx], posix=False)

                # calculate begidx
                if unclosed_quote:
                    begidx = tmp_line[:tmp_endidx].rfind(initial_tokens[-1]) + 1
                else:
                    if tmp_endidx > 0 and tmp_line[tmp_endidx - 1] == ' ':
                        begidx = endidx
                    else:
                        begidx = tmp_line[:tmp_endidx].rfind(initial_tokens[-1])

                # If the cursor is at an empty token outside of a quoted string,
                # then that is the token being completed. Add it to the list.
                if not unclosed_quote and begidx == tmp_endidx:
                    initial_tokens.append('')
                break
            except ValueError:
                # ValueError can be caused by missing closing quote
                if not quotes_to_try:  # pragma: no cover
                    # Since we have no more quotes to try, something else
                    # is causing the parsing error. Return None since
                    # this means the line is malformed.
                    return None, None, None, None

                # Add a closing quote and try to parse again
                unclosed_quote = quotes_to_try[0]
                quotes_to_try = quotes_to_try[1:]

                tmp_line = line[:endidx]
                tmp_line += unclosed_quote
                tmp_endidx = endidx + 1

        raw_tokens = initial_tokens

        # Save the unquoted tokens
        tokens = [utils.strip_quotes(cur_token) for cur_token in raw_tokens]

        # If the token being completed had an unclosed quote, we need
        # to remove the closing quote that was added in order for it
        # to match what was on the command line.
        if unclosed_quote:
            raw_tokens[-1] = raw_tokens[-1][:-1]

        return tokens, raw_tokens, begidx, endidx

    class CompletionFinder(argcomplete.CompletionFinder):
        """Hijack the functor from argcomplete to call AutoCompleter"""

        def __call__(self, argument_parser, completer=None, always_complete_options=True, exit_method=os._exit, output_stream=None,
                     exclude=None, validator=None, print_suppressed=False, append_space=None,
                     default_completer=DEFAULT_COMPLETER):
            """
            :param argument_parser: The argument parser to autocomplete on
            :type argument_parser: :class:`argparse.ArgumentParser`
            :param always_complete_options:
                Controls the autocompletion of option strings if an option string opening character (normally ``-``) has not
                been entered. If ``True`` (default), both short (``-x``) and long (``--x``) option strings will be
                suggested. If ``False``, no option strings will be suggested. If ``long``, long options and short options
                with no long variant will be suggested. If ``short``, short options and long options with no short variant
                will be suggested.
            :type always_complete_options: boolean or string
            :param exit_method:
                Method used to stop the program after printing completions. Defaults to :meth:`os._exit`. If you want to
                perform a normal exit that calls exit handlers, use :meth:`sys.exit`.
            :type exit_method: callable
            :param exclude: List of strings representing options to be omitted from autocompletion
            :type exclude: iterable
            :param validator:
                Function to filter all completions through before returning (called with two string arguments, completion
                and prefix; return value is evaluated as a boolean)
            :type validator: callable
            :param print_suppressed:
                Whether or not to autocomplete options that have the ``help=argparse.SUPPRESS`` keyword argument set.
            :type print_suppressed: boolean
            :param append_space:
                Whether to append a space to unique matches. The default is ``True``.
            :type append_space: boolean

            .. note::
                If you are not subclassing CompletionFinder to override its behaviors,
                use ``argcomplete.autocomplete()`` directly. It has the same signature as this method.

            Produces tab completions for ``argument_parser``. See module docs for more info.

            Argcomplete only executes actions if their class is known not to have side effects. Custom action classes can be
            added to argcomplete.safe_actions, if their values are wanted in the ``parsed_args`` completer argument, or
            their execution is otherwise desirable.
            """
            # Older versions of argcomplete have fewer keyword arguments
            if sys.version_info >= (3, 5):
                self.__init__(argument_parser, always_complete_options=always_complete_options, exclude=exclude,
                            validator=validator, print_suppressed=print_suppressed, append_space=append_space,
                            default_completer=default_completer)
            else:
                self.__init__(argument_parser, always_complete_options=always_complete_options, exclude=exclude,
                            validator=validator, print_suppressed=print_suppressed)

            if "_ARGCOMPLETE" not in os.environ:
                # not an argument completion invocation
                return

            try:
                argcomplete.debug_stream = os.fdopen(9, "w")
            except IOError:
                argcomplete.debug_stream = sys.stderr

            if output_stream is None:
                try:
                    output_stream = os.fdopen(8, "wb")
                except IOError:
                    argcomplete.debug("Unable to open fd 8 for writing, quitting")
                    exit_method(1)

            # print("", stream=debug_stream)
            # for v in "COMP_CWORD COMP_LINE COMP_POINT COMP_TYPE COMP_KEY _ARGCOMPLETE_COMP_WORDBREAKS COMP_WORDS".split():
            #     print(v, os.environ[v], stream=debug_stream)

            ifs = os.environ.get("_ARGCOMPLETE_IFS", "\013")
            if len(ifs) != 1:
                argcomplete.debug("Invalid value for IFS, quitting [{v}]".format(v=ifs))
                exit_method(1)

            comp_line = os.environ["COMP_LINE"]
            comp_point = int(os.environ["COMP_POINT"])

            comp_line = argcomplete.ensure_str(comp_line)

            ##############################
            # SWAPPED FOR AUTOCOMPLETER
            #
            # Replaced with our own tokenizer function
            ##############################

            # cword_prequote, cword_prefix, cword_suffix, comp_words, last_wordbreak_pos = split_line(comp_line, comp_point)
            tokens, _, begidx, endidx = tokens_for_completion(comp_line, comp_point)

            # _ARGCOMPLETE is set by the shell script to tell us where comp_words
            # should start, based on what we're completing.
            # 1: <script> [args]
            # 2: python <script> [args]
            # 3: python -m <module> [args]
            start = int(os.environ["_ARGCOMPLETE"]) - 1
            ##############################
            # SWAPPED FOR AUTOCOMPLETER
            #
            # Applying the same token dropping to our tokens
            ##############################
            # comp_words = comp_words[start:]
            tokens = tokens[start:]

            # debug("\nLINE: {!r}".format(comp_line),
            #       "\nPOINT: {!r}".format(comp_point),
            #       "\nPREQUOTE: {!r}".format(cword_prequote),
            #       "\nPREFIX: {!r}".format(cword_prefix),
            #       "\nSUFFIX: {!r}".format(cword_suffix),
            #       "\nWORDS:", comp_words)

            ##############################
            # SWAPPED FOR AUTOCOMPLETER
            #
            # Replaced with our own completion function and customizing the returned values
            ##############################
            # completions = self._get_completions(comp_words, cword_prefix, cword_prequote, last_wordbreak_pos)

            # capture stdout from the autocompleter
            result = StringIO()
            with redirect_stdout(result):
                completions = completer.complete_command(tokens, tokens[-1], comp_line, begidx, endidx)
            outstr = result.getvalue()

            if completions:
                # If any completion has a space in it, then quote all completions
                # this improves the user experience so they don't nede to go back and add a quote
                if ' ' in ''.join(completions):
                    completions = ['"{}"'.format(entry) for entry in completions]

                argcomplete.debug("\nReturning completions:", completions)

                output_stream.write(ifs.join(completions).encode(argcomplete.sys_encoding))
            elif outstr:
                # if there are no completions, but we got something from stdout, try to print help
                # trick the bash completion into thinking there are 2 completions that are unlikely
                # to ever match.

                comp_type = int(os.environ["COMP_TYPE"])
                if comp_type == 63:  # type is 63 for second tab press
                    print(outstr.rstrip(), file=argcomplete.debug_stream, end='')

                if completions is not None:
                    output_stream.write(ifs.join([ifs, ' ']).encode(argcomplete.sys_encoding))
                else:
                    output_stream.write(ifs.join([]).encode(argcomplete.sys_encoding))
            else:
                # if completions is None we assume we don't know how to handle it so let bash
                # go forward with normal filesystem completion
                output_stream.write(ifs.join([]).encode(argcomplete.sys_encoding))
            output_stream.flush()
            argcomplete.debug_stream.flush()
            exit_method(0)


    def bash_complete(action, show_hint: bool=True):
        """Helper function to configure an argparse action to fall back to bash completion"""
        def complete_none(*args, **kwargs):
            return None
        setattr(action, ACTION_SUPPRESS_HINT, not show_hint)
        setattr(action, ACTION_ARG_CHOICES, (complete_none,))
