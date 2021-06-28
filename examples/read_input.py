#!/usr/bin/env python
# coding=utf-8
"""
A simple example demonstrating the various ways to call cmd2.Cmd.read_input() for input history and tab completion
"""
from typing import (
    List,
)

import cmd2

EXAMPLE_COMMANDS = "Example Commands"


class ReadInputApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.prompt = "\n" + self.prompt
        self.custom_history = ['history 1', 'history 2']

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_basic(self, _) -> None:
        """Call read_input with no history or tab completion"""
        self.poutput("Tab completion and up-arrow history is off")
        try:
            self.read_input("> ")
        except EOFError:
            pass

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_basic_with_history(self, _) -> None:
        """Call read_input with custom history and no tab completion"""
        self.poutput("Tab completion is off but using custom history")
        try:
            input_str = self.read_input("> ", history=self.custom_history)
        except EOFError:
            pass
        else:
            self.custom_history.append(input_str)

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_commands(self, _) -> None:
        """Call read_input the same way cmd2 prompt does to read commands"""
        self.poutput("Tab completing and up-arrow history configured for commands")
        try:
            self.read_input("> ", completion_mode=cmd2.CompletionMode.COMMANDS)
        except EOFError:
            pass

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_custom_choices(self, _) -> None:
        """Call read_input to use custom history and choices"""
        self.poutput("Tab completing with static choices list and using custom history")
        try:
            input_str = self.read_input(
                "> ",
                history=self.custom_history,
                completion_mode=cmd2.CompletionMode.CUSTOM,
                choices=['choice_1', 'choice_2', 'choice_3'],
            )
        except EOFError:
            pass
        else:
            self.custom_history.append(input_str)

    # noinspection PyMethodMayBeStatic
    def choices_provider(self) -> List[str]:
        """Example choices provider function"""
        return ["from_provider_1", "from_provider_2", "from_provider_3"]

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_custom_choices_provider(self, _) -> None:
        """Call read_input to use custom history and choices provider function"""
        self.poutput("Tab completing with choices from provider function and using custom history")
        try:
            input_str = self.read_input(
                "> ",
                history=self.custom_history,
                completion_mode=cmd2.CompletionMode.CUSTOM,
                choices_provider=ReadInputApp.choices_provider,
            )
        except EOFError:
            pass
        else:
            self.custom_history.append(input_str)

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_custom_completer(self, _) -> None:
        """Call read_input to use custom history and completer function"""
        self.poutput("Tab completing paths and using custom history")
        try:
            input_str = self.read_input(
                "> ", history=self.custom_history, completion_mode=cmd2.CompletionMode.CUSTOM, completer=cmd2.Cmd.path_complete
            )
            self.custom_history.append(input_str)
        except EOFError:
            pass

    @cmd2.with_category(EXAMPLE_COMMANDS)
    def do_custom_parser(self, _) -> None:
        """Call read_input to use a custom history and an argument parser"""
        parser = cmd2.Cmd2ArgumentParser(prog='', description="An example parser")
        parser.add_argument('-o', '--option', help="an optional arg")
        parser.add_argument('arg_1', help="a choice for this arg", metavar='arg_1', choices=['my_choice', 'your_choice'])
        parser.add_argument('arg_2', help="path of something", completer=cmd2.Cmd.path_complete)

        self.poutput("Tab completing with argument parser and using custom history")
        self.poutput(parser.format_usage())

        try:
            input_str = self.read_input(
                "> ", history=self.custom_history, completion_mode=cmd2.CompletionMode.CUSTOM, parser=parser
            )
        except EOFError:
            pass
        else:
            self.custom_history.append(input_str)


if __name__ == '__main__':
    import sys

    app = ReadInputApp()
    sys.exit(app.cmdloop())
