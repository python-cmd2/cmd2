"""A cmd2 script that saves the help text for every command, subcommand, and topic to a file.
This is meant to be run within a cmd2 session using run_pyscript.
"""

import os
import sys
from typing import TextIO

from cmd2 import Cmd2ArgumentParser

ASTERISKS = "********************************************************"


def get_sub_commands(parser: Cmd2ArgumentParser) -> list[str]:
    """Get a list of subcommands for a Cmd2ArgumentParser."""
    try:
        subparsers_action = parser._get_subparsers_action()
    except ValueError:
        # No subcommands
        return []

    # Prevent redundant traversal of parser aliases
    checked_parsers: set[Cmd2ArgumentParser] = set()

    sub_cmds = []
    for subcmd, subcmd_parser in subparsers_action.choices.items():
        if subcmd_parser in checked_parsers:
            continue
        checked_parsers.add(subcmd_parser)

        sub_cmds.append(subcmd)

        # Look for nested subcommands
        sub_cmds.extend(f'{subcmd} {nested_subcmd}' for nested_subcmd in get_sub_commands(subcmd_parser))

    sub_cmds.sort()
    return sub_cmds


def add_help_to_file(item: str, outfile: TextIO, is_command: bool) -> None:
    """Write help text for commands and topics to the output file

    :param item: what is having its help text saved
    :param outfile: file being written to
    :param is_command: tells if the item is a command and not just a help topic.
    """
    label = "COMMAND" if is_command else "TOPIC"

    header = f'{ASTERISKS}\n{label}: {item}\n{ASTERISKS}\n'
    outfile.write(header)

    result = app(f'help {item}')
    outfile.write(result.stdout)


def main() -> None:
    """Main function of this script."""
    # Make sure we have access to self
    if 'self' not in globals():
        print("Re-run this script from a cmd2 application where self_in_py is True")
        return

    # Make sure the user passed in an output file
    if len(sys.argv) != 2:
        print(f"Usage: {os.path.basename(sys.argv[0])} <output_file>")
        return

    outfile_path = os.path.expanduser(sys.argv[1])
    try:
        with open(outfile_path, 'w') as outfile:
            # Write the help summary
            header = f'{ASTERISKS}\nSUMMARY\n{ASTERISKS}\n'
            outfile.write(header)

            result = app('help -v')
            outfile.write(result.stdout)

            # Get a list of all commands and help topics and then filter out duplicates
            all_commands = set(self.get_all_commands())
            all_topics = set(self.get_help_topics())
            to_save = sorted(all_commands | all_topics)

            for item in to_save:
                is_command = item in all_commands
                add_help_to_file(item, outfile, is_command)

                if not is_command:
                    continue

                cmd_func = self.get_command_func(item)
                parser = self._command_parsers.get(cmd_func)
                if parser is None:
                    continue

                # Add any subcommands
                for subcmd in get_sub_commands(parser):
                    full_cmd = f'{item} {subcmd}'
                    add_help_to_file(full_cmd, outfile, is_command)

            print(f"Output written to {outfile_path}")

    except OSError as ex:
        print(f"Error handling {outfile_path} because: {ex}")


if __name__ == "__main__":
    main()
