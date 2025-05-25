"""Test CommandSet."""

import argparse

import cmd2


@cmd2.with_default_category('Fruits')
class CommandSetA(cmd2.CommandSet):
    def do_apple(self, _statement: cmd2.Statement) -> None:
        self._cmd.poutput('Apple!')

    def do_banana(self, _statement: cmd2.Statement) -> None:
        """Banana Command."""
        self._cmd.poutput('Banana!!')

    cranberry_parser = cmd2.Cmd2ArgumentParser()
    cranberry_parser.add_argument('arg1', choices=['lemonade', 'juice', 'sauce'])

    @cmd2.with_argparser(cranberry_parser, with_unknown_args=True)
    def do_cranberry(self, ns: argparse.Namespace, unknown: list[str]) -> None:
        self._cmd.poutput(f'Cranberry {ns.arg1}!!')
        if unknown and len(unknown):
            self._cmd.poutput('Unknown: ' + ', '.join(['{}'] * len(unknown)).format(*unknown))
        self._cmd.last_result = {'arg1': ns.arg1, 'unknown': unknown}

    def help_cranberry(self) -> None:
        self._cmd.stdout.write('This command does diddly squat...\n')

    @cmd2.with_argument_list
    @cmd2.with_category('Also Alone')
    def do_durian(self, args: list[str]) -> None:
        """Durian Command."""
        self._cmd.poutput(f'{len(args)} Arguments: ')
        self._cmd.poutput(', '.join(['{}'] * len(args)).format(*args))

    def complete_durian(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        return self._cmd.basic_complete(text, line, begidx, endidx, ['stinks', 'smells', 'disgusting'])

    elderberry_parser = cmd2.Cmd2ArgumentParser()
    elderberry_parser.add_argument('arg1')

    @cmd2.with_category('Alone')
    @cmd2.with_argparser(elderberry_parser)
    def do_elderberry(self, ns: argparse.Namespace) -> None:
        self._cmd.poutput(f'Elderberry {ns.arg1}!!')
