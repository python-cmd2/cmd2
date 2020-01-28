# coding=utf-8
# flake8: noqa F821
"""
A cmd2 script that saves the help text for every command, subcommand, and topic to a file.
This is meant to be run within a cmd2 session using run_pyscript.
"""

import argparse
import os
import sys
from typing import List, TextIO

ASTERISKS = "********************************************************"


def get_sub_commands(parser: argparse.ArgumentParser) -> List[str]:
    """Get a list of subcommands for an ArgumentParser"""
    sub_cmds = []

    # Check if this is parser has subcommands
    if parser is not None and parser._subparsers is not None:

        # Find the _SubParsersAction for the subcommands of this parser
        for action in parser._subparsers._actions:
            if isinstance(action, argparse._SubParsersAction):
                for sub_cmd, sub_cmd_parser in action.choices.items():
                    sub_cmds.append(sub_cmd)

                    # Look for nested subcommands
                    for nested_sub_cmd in get_sub_commands(sub_cmd_parser):
                        sub_cmds.append('{} {}'.format(sub_cmd, nested_sub_cmd))

                break

    sub_cmds.sort()
    return sub_cmds


def add_help_to_file(item: str, outfile: TextIO, is_command: bool) -> None:
    """
    Write help text for commands and topics to the output file
    :param item: what is having its help text saved
    :param outfile: file being written to
    :param is_command: tells if the item is a command and not just a help topic
    """
    if is_command:
        label = "COMMAND"
    else:
        label = "TOPIC"

    header = '{}\n{}: {}\n{}\n'.format(ASTERISKS, label, item, ASTERISKS)
    outfile.write(header)

    result = app('help {}'.format(item))
    outfile.write(result.stdout)


def main() -> None:
    """Main function of this script"""

    # Make sure we have access to self
    if 'self' not in globals():
        print("Re-run this script from a cmd2 application where self_in_py is True")
        return

    # Make sure the user passed in an output file
    if len(sys.argv) != 2:
        print("Usage: {} <output_file>".format(os.path.basename(sys.argv[0])))
        return

    # Open the output file
    outfile_path = os.path.expanduser(sys.argv[1])
    try:
        outfile = open(outfile_path, 'w')
    except OSError as e:
        print("Error opening {} because: {}".format(outfile_path, e))
        return

    # Write the help summary
    header = '{0}\nSUMMARY\n{0}\n'.format(ASTERISKS)
    outfile.write(header)

    result = app('help -v')
    outfile.write(result.stdout)

    # Get a list of all commands and help topics and then filter out duplicates
    all_commands = set(self.get_all_commands())
    all_topics = set(self.get_help_topics())
    to_save = list(all_commands | all_topics)
    to_save.sort()

    for item in to_save:
        is_command = item in all_commands
        add_help_to_file(item, outfile, is_command)

        if is_command:
            # Add any subcommands
            for subcmd in get_sub_commands(getattr(self.cmd_func(item), 'argparser', None)):
                full_cmd = '{} {}'.format(item, subcmd)
                add_help_to_file(full_cmd, outfile, is_command)

    outfile.close()
    print("Output written to {}".format(outfile_path))


# Run main function
main()
