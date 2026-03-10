#!/usr/bin/env python
"""A simple example demonstrating the various ways to call cmd2.Cmd.read_input() and cmd2.Cmd.read_secret().

These methods can be used to read input from stdin with optional history, tab completion, or password masking.
It also demonstrates how to use the cmd2.Cmd.select method.
"""

import contextlib

import cmd2

EXAMPLE_COMMANDS = "Example Commands"


class ReadInputApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.prompt = "\n" + self.prompt
        self.custom_history = ['history 1', 'history 2']

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_basic(self, _) -> None:
        """Call read_input with no history or tab completion."""
        self.poutput("Tab completion and up-arrow history is off")
        with contextlib.suppress(EOFError):
            self.read_input("> ")

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_basic_with_history(self, _) -> None:
        """Call read_input with custom history and no tab completion."""
        self.poutput("Tab completion is off but using custom history")
        try:
            input_str = self.read_input("> ", history=self.custom_history)
        except EOFError:
            pass
        else:
            self.custom_history.append(input_str)

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_custom_choices(self, _) -> None:
        """Call read_input to use custom history and choices."""
        self.poutput("Tab completing with static choices list and using custom history")
        try:
            input_str = self.read_input(
                "> ",
                history=self.custom_history,
                choices=['choice_1', 'choice_2', 'choice_3'],
            )
        except EOFError:
            pass
        else:
            self.custom_history.append(input_str)

    def choices_provider(self) -> cmd2.Choices:
        """Example choices provider function."""
        return cmd2.Choices.from_values(["from_provider_1", "from_provider_2", "from_provider_3"])

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_custom_choices_provider(self, _) -> None:
        """Call read_input to use custom history and choices provider function."""
        self.poutput("Tab completing with choices from provider function and using custom history")
        try:
            input_str = self.read_input(
                "> ",
                history=self.custom_history,
                choices_provider=ReadInputApp.choices_provider,
            )
        except EOFError:
            pass
        else:
            self.custom_history.append(input_str)

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_custom_completer(self, _) -> None:
        """Call read_input to use custom history and completer function."""
        self.poutput("Tab completing paths and using custom history")
        try:
            input_str = self.read_input("> ", history=self.custom_history, completer=cmd2.Cmd.path_complete)
            self.custom_history.append(input_str)
        except EOFError:
            pass

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_custom_parser(self, _) -> None:
        """Call read_input to use a custom history and an argument parser."""
        parser = cmd2.Cmd2ArgumentParser(prog='', description="An example parser")
        parser.add_argument('-o', '--option', help="an optional arg")
        parser.add_argument('arg_1', help="a choice for this arg", metavar='arg_1', choices=['my_choice', 'your_choice'])
        parser.add_argument('arg_2', help="path of something", completer=cmd2.Cmd.path_complete)

        self.poutput("Tab completing with argument parser and using custom history")
        self.poutput(parser.format_usage())

        try:
            input_str = self.read_input("> ", history=self.custom_history, parser=parser)
        except EOFError:
            pass
        else:
            self.custom_history.append(input_str)

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_read_password(self, _) -> None:
        """Call read_secret to read a password without displaying it while being typed.

        WARNING: Password will be displayed for verification after it is typed.
        """
        self.poutput("The input will not be displayed on the screen")
        try:
            password = self.read_secret("Password: ")
            self.poutput(f"You entered: {password}")
        except EOFError:
            pass

    def do_eat(self, arg):
        """Example of using the select method for reading multiple choice input.

        Usage: eat wheatties
        """
        sauce = self.select('sweet salty', 'Sauce? ')
        result = '{food} with {sauce} sauce, yum!'
        result = result.format(food=arg, sauce=sauce)
        self.stdout.write(result + '\n')


if __name__ == '__main__':
    import sys

    app = ReadInputApp()
    sys.exit(app.cmdloop())
