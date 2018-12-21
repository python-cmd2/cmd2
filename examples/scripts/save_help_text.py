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
from typing import List

ASTERISKS = "********************************************************"


def get_sub_commands(parser: argparse.ArgumentParser) -> List[str]:
    """Returns a list of sub-commands for an ArgumentParser"""

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


# Make sure we have access to self
if 'self' not in globals():
    print("Run 'set locals_in_py true' and then rerun this script")

# Make sure the user passed in an output file
elif len(sys.argv) != 2:
    print("Usage: {} <output_file>".format(os.path.basename(sys.argv[0])))
else:
    outfile = os.path.expanduser(sys.argv[1])

    # Get a list of all commands and help topics and then filter out duplicates
    to_print = set(self.get_all_commands()) | set(self.get_help_topics())

    # Create a script that will call help on each command and topic and write its output to a file
    with tempfile.NamedTemporaryFile(mode='w+t', delete=False) as temp:

        # First delete any existing output file
        temp.write('!rm -f {}\n'.format(outfile))

        for item in to_print:
            header = '{}\\nCOMMAND: {}\\n{}\\n'.format(ASTERISKS, item, ASTERISKS)
            temp.write('py print("{}") >> {}\n'.format(header, outfile))
            temp.write('help {} >> {}\n'.format(item, outfile))

            # Add any sub-commands
            for subcmd in get_sub_commands(getattr(self.cmd_func(item), 'argparser', None)):
                full_cmd = '{} {}'.format(item, subcmd)
                header = '{}\\nCOMMAND: {}\\n{}\\n'.format(ASTERISKS, full_cmd, ASTERISKS)

                temp.write('py print("{}") >> {}\n'.format(header, outfile))
                temp.write('help {} >> {}\n'.format(full_cmd, outfile))

        # Inform the user where output was written
        temp.write('py print("Output written to {}")\n'.format(outfile))

        # Have the script delete itself as its last step
        temp.write('!rm -f {}\n'.format(temp.name))

        # Tell cmd2 to run the script as its next command
        self.cmdqueue.insert(0, "load '{}'".format(temp.name))
