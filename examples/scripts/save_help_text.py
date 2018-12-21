# coding=utf-8
# flake8: noqa F821
"""
A cmd2 script that saves the help text for every command and sub-commands to a file
This is meant to be run with pyscript within a cmd2 session.
"""

import argparse
import os
import sys
import tempfile
from typing import List, TextIO

ASTERISKS = "********************************************************"


def get_sub_commands(parser: argparse.ArgumentParser) -> List[str]:
    """Get a list of sub-commands for an ArgumentParser"""
    sub_cmds = []

    # Check if this is parser has sub-commands
    if parser is not None and parser._subparsers is not None:

        # Find the _SubParsersAction for the sub-commands of this parser
        for action in parser._subparsers._actions:
            if isinstance(action, argparse._SubParsersAction):
                for sub_cmd, sub_cmd_parser in action.choices.items():
                    sub_cmds.append(sub_cmd)

                    # Look for nested sub-commands
                    for nested_sub_cmd in get_sub_commands(sub_cmd_parser):
                        sub_cmds.append('{} {}'.format(sub_cmd, nested_sub_cmd))

                break

    return sub_cmds


def add_command_to_script(command: str, temp_file: TextIO, outfile_path: str) -> None:
    """
    Write to the script the commands necessary to write both a
    header and help text for a command to the output file
    """
    header = '{}\\nCOMMAND: {}\\n{}\\n'.format(ASTERISKS, command, ASTERISKS)
    temp_file.write('py print("{}") >> {}\n'.format(header, outfile_path))
    temp_file.write('help {} >> {}\n'.format(command, outfile_path))


def main():
    """Main function of this script"""

    # Make sure we have access to self
    if 'self' not in globals():
        print("Run 'set locals_in_py true' and then rerun this script")
        return

    # Make sure the user passed in an output file
    if len(sys.argv) != 2:
        print("Usage: {} <output_file>".format(os.path.basename(sys.argv[0])))
        return

    # Get output file path
    outfile = os.path.expanduser(sys.argv[1])

    # Create a script that will call help on each command and topic and write its output to a file
    with tempfile.NamedTemporaryFile(mode='w+t', delete=False) as temp_file:

        # First delete any existing output file
        temp_file.write('py if os.path.exists("{0}"): os.remove("{0}")\n'.format(outfile))

        # Get a list of all commands and help topics and then filter out duplicates
        to_save = set(self.get_all_commands()) | set(self.get_help_topics())

        for item in to_save:
            add_command_to_script(item, temp_file, outfile)

            # Add any sub-commands
            for subcmd in get_sub_commands(getattr(self.cmd_func(item), 'argparser', None)):
                full_cmd = '{} {}'.format(item, subcmd)
                add_command_to_script(full_cmd, temp_file, outfile)

        # Inform the user where output was written
        temp_file.write('py print("Output written to {}")\n'.format(outfile))

        # Have the script delete itself as its last step
        temp_file.write('py os.remove("{}")\n'.format(temp_file.name))

        # Tell cmd2 to run the script as its next command
        self.cmdqueue.insert(0, 'load "{}"'.format(temp_file.name))


# Run main function
main()
