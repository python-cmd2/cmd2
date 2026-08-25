#!/usr/bin/env python
"""A sample application for cmd2.

This example relies on the `allow_cli_args` init parameter being `True` by default which allows passing commands on the
command line to execute when the application is invoked.

This can be run like so:
$ python cmd_as_argument.py "speak -p hello there" help

By default, the application will enter the interactive shell mode after executing the commands passed in on the command line.
You can have it exit after executing by providing `quit` as the last command.
Commands and arguments can be grouped together by including in quotes.
"""

import secrets

import cmd2


class CmdLineApp(cmd2.Cmd):
    """Example cmd2 application."""

    MUMBLES = ("like", "...", "um", "er", "hmmm", "ahh")
    MUMBLE_FIRST = ("so", "like", "well")
    MUMBLE_LAST = ("right?",)

    def __init__(self) -> None:
        shortcuts = dict(cmd2.DEFAULT_SHORTCUTS)
        shortcuts.update({"&": "speak"})
        # Set include_ipy to True to enable the "ipy" command which runs an interactive IPython shell
        super().__init__(allow_cli_args=True, include_ipy=True, multiline_commands=["orate"], shortcuts=shortcuts)

        self.self_in_py = True
        self.maxrepeats = 3
        # Make maxrepeats settable at runtime
        self.add_settable(cmd2.Settable("maxrepeats", int, "max repetitions for speak command", self))

        # Create an instance of SystemRandom
        self._secure_generator = secrets.SystemRandom()

    speak_parser = cmd2.Cmd2ArgumentParser()
    speak_parser.add_argument("-p", "--piglatin", action="store_true", help="atinLay")
    speak_parser.add_argument("-s", "--shout", action="store_true", help="N00B EMULATION MODE")
    speak_parser.add_argument("-r", "--repeat", type=int, help="output [n] times")
    speak_parser.add_argument("words", nargs="+", help="words to say")

    @cmd2.with_argparser(speak_parser)
    def do_speak(self, args) -> None:
        """Repeats what you tell me to."""
        words = []
        for w in args.words:
            word = w.strip()
            if args.piglatin:
                word = f"{word[1:]}{word[0]}ay"
            if args.shout:
                word = word.upper()
            words.append(word)
        repetitions = args.repeat or 1
        for _ in range(min(repetitions, self.maxrepeats)):
            # .poutput handles newlines, and accommodates output redirection too
            self.poutput(" ".join(words))

    do_say = do_speak  # now "say" is a synonym for "speak"
    do_orate = do_speak  # another synonym, but this one takes multi-line input

    mumble_parser = cmd2.Cmd2ArgumentParser()
    mumble_parser.add_argument("-r", "--repeat", type=int, help="how many times to repeat")
    mumble_parser.add_argument("words", nargs="+", help="words to say")

    @cmd2.with_argparser(mumble_parser)
    def do_mumble(self, args) -> None:
        """Mumbles what you tell me to."""
        repetitions = args.repeat or 1
        for _ in range(min(repetitions, self.maxrepeats)):
            output = []
            if self._secure_generator.random() < 0.33:
                output.append(secrets.choice(self.MUMBLE_FIRST))
            for word in args.words:
                if self._secure_generator.random() < 0.40:
                    output.append(secrets.choice(self.MUMBLES))
                output.append(word)
            if self._secure_generator.random() < 0.25:
                output.append(secrets.choice(self.MUMBLE_LAST))
            self.poutput(" ".join(output))


if __name__ == "__main__":
    import sys

    app = CmdLineApp()
    sys.exit(app.cmdloop())
