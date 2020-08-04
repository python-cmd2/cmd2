# coding=utf-8
# flake8: noqa E302
"""
Test CommandSet
"""

import argparse
from typing import List

import cmd2
from cmd2 import utils


@cmd2.with_default_category('Fruits')
class CommandSetA(cmd2.CommandSet):
    def do_apple(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        cmd.poutput('Apple!')

    def do_banana(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        """Banana Command"""
        cmd.poutput('Banana!!')

    cranberry_parser = cmd2.Cmd2ArgumentParser('cranberry')
    cranberry_parser.add_argument('arg1', choices=['lemonade', 'juice', 'sauce'])

    @cmd2.with_argparser(cranberry_parser, with_unknown_args=True)
    def do_cranberry(self, cmd: cmd2.Cmd, ns: argparse.Namespace, unknown: List[str]):
        cmd.poutput('Cranberry {}!!'.format(ns.arg1))
        if unknown and len(unknown):
            cmd.poutput('Unknown: ' + ', '.join(['{}']*len(unknown)).format(*unknown))
        cmd.last_result = {'arg1': ns.arg1,
                           'unknown': unknown}

    def help_cranberry(self, cmd: cmd2.Cmd):
        cmd.stdout.write('This command does diddly squat...\n')

    @cmd2.with_argument_list
    @cmd2.with_category('Also Alone')
    def do_durian(self, cmd: cmd2.Cmd, args: List[str]):
        """Durian Command"""
        cmd.poutput('{} Arguments: '.format(len(args)))
        cmd.poutput(', '.join(['{}']*len(args)).format(*args))

    def complete_durian(self, cmd: cmd2.Cmd, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return utils.basic_complete(text, line, begidx, endidx, ['stinks', 'smells', 'disgusting'])

    elderberry_parser = cmd2.Cmd2ArgumentParser('elderberry')
    elderberry_parser.add_argument('arg1')

    @cmd2.with_category('Alone')
    @cmd2.with_argparser(elderberry_parser)
    def do_elderberry(self, cmd: cmd2.Cmd, ns: argparse.Namespace):
        cmd.poutput('Elderberry {}!!'.format(ns.arg1))
