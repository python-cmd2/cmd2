# coding=utf-8
# flake8: noqa E302
"""
Test CommandSet
"""

import argparse
from typing import (
    List,
)

import cmd2


@cmd2.with_default_category('Fruits')
class CommandSetA(cmd2.CommandSet):
    def do_apple(self, statement: cmd2.Statement):
        self._cmd.poutput('Apple!')

    def do_banana(self, statement: cmd2.Statement):
        """Banana Command"""
        self._cmd.poutput('Banana!!')

    cranberry_parser = cmd2.Cmd2ArgumentParser()
    cranberry_parser.add_argument('arg1', choices=['lemonade', 'juice', 'sauce'])

    @cmd2.with_argparser(cranberry_parser, with_unknown_args=True)
    def do_cranberry(self, ns: argparse.Namespace, unknown: List[str]):
        self._cmd.poutput('Cranberry {}!!'.format(ns.arg1))
        if unknown and len(unknown):
            self._cmd.poutput('Unknown: ' + ', '.join(['{}'] * len(unknown)).format(*unknown))
        self._cmd.last_result = {'arg1': ns.arg1, 'unknown': unknown}

    def help_cranberry(self):
        self._cmd.stdout.write('This command does diddly squat...\n')

    @cmd2.with_argument_list
    @cmd2.with_category('Also Alone')
    def do_durian(self, args: List[str]):
        """Durian Command"""
        self._cmd.poutput('{} Arguments: '.format(len(args)))
        self._cmd.poutput(', '.join(['{}'] * len(args)).format(*args))

    def complete_durian(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return self._cmd.basic_complete(text, line, begidx, endidx, ['stinks', 'smells', 'disgusting'])

    elderberry_parser = cmd2.Cmd2ArgumentParser()
    elderberry_parser.add_argument('arg1')

    @cmd2.with_category('Alone')
    @cmd2.with_argparser(elderberry_parser)
    def do_elderberry(self, ns: argparse.Namespace):
        self._cmd.poutput('Elderberry {}!!'.format(ns.arg1))
