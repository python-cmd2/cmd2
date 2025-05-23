#!/usr/bin/env python
"""A sample application for cmd2 demonstrating how to use hooks.

This application shows how to use postparsing hooks to allow case insensitive
command names, abbreviated commands, as well as allowing numeric arguments to
follow a command without any intervening whitespace.

"""

import re

import cmd2


class CmdLineApp(cmd2.Cmd):
    """Example cmd2 application demonstrating the use of hooks.

    This simple application has one command, `list` which generates a list
    of 10 numbers. This command takes one optional argument, which is the
    number to start on.

    We have three postparsing hooks, which allow the user to enter:

        (Cmd) list 5
        (Cmd) L 5
        (Cmd) l 5
        (Cmd) L5
        (Cmd) LI5

    and have them all treated as valid input which prints a list of 10 numbers
    starting with the number 5.

    We also add a postcommand hook, which updates the shell prompt to show the
    raw contents of the Statement after the postparsing hooks are finished. To
    use this hook, run `(Cmd) set debug True`. All of the above variations of
    the list command should produce the same raw content.

    """

    # Setting this true makes it run a shell command if a cmd2/cmd command doesn't exist
    # default_to_shell = True  # noqa: ERA001
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # register four hooks
        self.register_postparsing_hook(self.add_whitespace_hook)
        self.register_postparsing_hook(self.downcase_hook)
        self.register_postparsing_hook(self.abbrev_hook)
        self.register_postcmd_hook(self.proof_hook)

    def add_whitespace_hook(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """A hook to split alphabetic command names immediately followed by a number.

        l24 -> l 24
        list24 -> list 24
        list 24 -> list 24

        """
        command = data.statement.command
        # regular expression with looks for:
        #  ^ - the beginning of the string
        # ([^\s\d]+) - one or more non-whitespace non-digit characters, set as capture group 1
        # (\d+) - one or more digit characters, set as capture group 2
        command_pattern = re.compile(r'^([^\s\d]+)(\d+)')
        match = command_pattern.search(command)
        if match:
            command = match.group(1)
            first_arg = match.group(2)
            rest_args = data.statement.args
            post_command = data.statement.post_command
            data.statement = self.statement_parser.parse(f'{command} {first_arg} {rest_args} {post_command}')
        return data

    def downcase_hook(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """A hook to make uppercase commands lowercase."""
        command = data.statement.command.lower()
        args = data.statement.args
        post_command = data.statement.post_command
        data.statement = self.statement_parser.parse(f'{command} {args} {post_command}')
        return data

    def abbrev_hook(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """Accept unique abbreviated commands."""
        func = self.cmd_func(data.statement.command)
        if func is None:
            # check if the entered command might be an abbreviation
            possible_cmds = [cmd for cmd in self.get_all_commands() if cmd.startswith(data.statement.command)]
            if len(possible_cmds) == 1:
                raw = data.statement.raw.replace(data.statement.command, possible_cmds[0], 1)
                data.statement = self.statement_parser.parse(raw)
        return data

    def proof_hook(self, data: cmd2.plugin.PostcommandData) -> cmd2.plugin.PostcommandData:
        """Update the shell prompt with the new raw statement after postparsing hooks are finished."""
        if self.debug:
            self.prompt = f'({data.statement.raw})'
        return data

    @cmd2.with_argument_list
    def do_list(self, arglist: list[str]) -> None:
        """Generate a list of 10 numbers."""
        if arglist:
            first = arglist[0]
            try:
                first = int(first)
            except ValueError:
                first = 1
        else:
            first = 1
        last = first + 10

        for x in range(first, last):
            self.poutput(str(x))


if __name__ == '__main__':
    import sys

    c = CmdLineApp()
    sys.exit(c.cmdloop())
