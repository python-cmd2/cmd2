#!/usr/bin/env python3
# coding=utf-8
"""An example demonstrating how use one of cmd2's argument parsing decorators"""
import argparse
import os

import cmd2


class ArgparsingApp(cmd2.Cmd):
    def __init__(self):
        super().__init__(use_ipython=True)
        self.intro = 'cmd2 has awesome decorators to make it easy to use Argparse to parse command arguments'

    # do_fsize parser
    fsize_parser = cmd2.Cmd2ArgumentParser(description='Obtain the size of a file')
    fsize_parser.add_argument('-c', '--comma', action='store_true',
                              help='add comma for thousands separator')
    fsize_parser.add_argument('-u', '--unit', choices=['MB', 'KB'], help='unit to display size in')
    fsize_parser.add_argument('file_path', help='path of file',
                              completer_method=cmd2.Cmd.path_complete)

    @cmd2.with_argparser(fsize_parser)
    def do_fsize(self, args: argparse.Namespace) -> None:
        """Obtain the size of a file"""
        expanded_path = os.path.expanduser(args.file_path)

        try:
            size = os.path.getsize(expanded_path)
        except OSError as ex:
            self.perror("Error retrieving size: {}".format(ex))
            return

        if args.unit == 'KB':
            size /= 1024
        elif args.unit == 'MB':
            size /= 1024 * 1024
        else:
            args.unit = 'bytes'
        size = round(size, 2)

        if args.comma:
            size = '{:,}'.format(size)
        self.poutput('{} {}'.format(size, args.unit))

    # do_pow parser
    pow_parser = argparse.ArgumentParser()
    pow_parser.add_argument('base', type=int)
    pow_parser.add_argument('exponent', type=int, choices=range(-5, 6))

    @cmd2.with_argparser(pow_parser)
    def do_pow(self, args: argparse.Namespace) -> None:
        """Raise an integer to a small integer exponent, either positive or negative"""
        self.poutput('{} ** {} == {}'.format(args.base, args.exponent, args.base ** args.exponent))


if __name__ == '__main__':
    app = ArgparsingApp()
    app.cmdloop()
