#!/usr/bin/env python
"""A sample application for tagging categories on commands.

It also demonstrates the effects of decorator order when it comes to argparse errors occurring.
"""

import functools

import cmd2
from cmd2 import COMMAND_NAME


def my_decorator(f):
    @functools.wraps(f)
    def wrapper(*args, **kwds):
        print('Calling decorated function')
        return f(*args, **kwds)

    return wrapper


class HelpCategories(cmd2.Cmd):
    """Example cmd2 application."""

    START_TIMES = ('now', 'later', 'sometime', 'whenever')

    # Command categories
    CMD_CAT_CONNECTING = 'Connecting'
    CMD_CAT_APP_MGMT = 'Application Management'
    CMD_CAT_SERVER_INFO = 'Server Information'

    def __init__(self) -> None:
        super().__init__()

        # Set the default category for uncategorized commands
        self.default_category = 'Other'

    def do_connect(self, _) -> None:
        """Connect command."""
        self.poutput('Connect')

    # Tag the above command functions under the category Connecting
    cmd2.categorize(do_connect, CMD_CAT_CONNECTING)

    @cmd2.with_category(CMD_CAT_CONNECTING)
    def do_which(self, _) -> None:
        """Which command."""
        self.poutput('Which')

    def do_list(self, _) -> None:
        """List command."""
        self.poutput('List')

    def do_deploy(self, _) -> None:
        """Deploy command."""
        self.poutput('Deploy')

    start_parser = cmd2.Cmd2ArgumentParser(
        description='Start',
        epilog='my_decorator runs even with argparse errors',
    )
    start_parser.add_argument('when', choices=START_TIMES, help='Specify when to start')

    @my_decorator
    @cmd2.with_argparser(start_parser)
    def do_start(self, _) -> None:
        """Start command."""
        self.poutput('Start')

    def do_sessions(self, _) -> None:
        """Sessions command."""
        self.poutput('Sessions')

    def do_redeploy(self, _) -> None:
        """Redeploy command."""
        self.poutput('Redeploy')

    restart_parser = cmd2.Cmd2ArgumentParser(
        description='Restart',
        epilog='my_decorator does not run when argparse errors',
    )
    restart_parser.add_argument('when', choices=START_TIMES, help='Specify when to restart')

    @cmd2.with_argparser(restart_parser)
    @cmd2.with_category(CMD_CAT_APP_MGMT)
    @my_decorator
    def do_restart(self, _) -> None:
        """Restart command."""
        self.poutput('Restart')

    def do_expire(self, _) -> None:
        """Expire command."""
        self.poutput('Expire')

    def do_undeploy(self, _) -> None:
        """Undeploy command."""
        self.poutput('Undeploy')

    def do_stop(self, _) -> None:
        """Stop command."""
        self.poutput('Stop')

    def do_findleakers(self, _) -> None:
        """Find Leakers command."""
        self.poutput('Find Leakers')

    # Tag the above command functions under the category Application Management
    cmd2.categorize(
        (do_list, do_deploy, do_start, do_sessions, do_redeploy, do_expire, do_undeploy, do_stop, do_findleakers),
        CMD_CAT_APP_MGMT,
    )

    def do_resources(self, _) -> None:
        """Resources command."""
        self.poutput('Resources')

    def do_status(self, _) -> None:
        """Status command."""
        self.poutput('Status')

    def do_serverinfo(self, _) -> None:
        """Server Info command."""
        self.poutput('Server Info')

    def do_thread_dump(self, _) -> None:
        """Thread Dump command."""
        self.poutput('Thread Dump')

    def do_sslconnectorciphers(self, _) -> None:
        """SSL Connector Ciphers command is an example of a command that contains
        multiple lines of help information for the user. Each line of help in a
        contiguous set of lines will be printed and aligned in the verbose output
        provided with 'help --verbose'.

        This is after a blank line and won't de displayed in the verbose help
        """
        self.poutput('SSL Connector Ciphers')

    def do_vminfo(self, _) -> None:
        """VM Info command."""
        self.poutput('VM Info')

    # Tag the above command functions under the category Server Information
    cmd2.categorize(do_resources, CMD_CAT_SERVER_INFO)
    cmd2.categorize(do_status, CMD_CAT_SERVER_INFO)
    cmd2.categorize(do_serverinfo, CMD_CAT_SERVER_INFO)
    cmd2.categorize(do_thread_dump, CMD_CAT_SERVER_INFO)
    cmd2.categorize(do_sslconnectorciphers, CMD_CAT_SERVER_INFO)
    cmd2.categorize(do_vminfo, CMD_CAT_SERVER_INFO)

    # The following command functions don't have the HELP_CATEGORY attribute set
    # and show up in the 'Other' group
    def do_config(self, _) -> None:
        """Config command."""
        self.poutput('Config')

    def do_version(self, _) -> None:
        """Version command."""
        self.poutput(cmd2.__version__)

    @cmd2.with_category("Command Management")
    def do_disable_commands(self, _) -> None:
        """Disable the Application Management commands."""
        message_to_print = f"{COMMAND_NAME} is not available while {self.CMD_CAT_APP_MGMT} commands are disabled"
        self.disable_category(self.CMD_CAT_APP_MGMT, message_to_print)
        self.poutput("The Application Management commands have been disabled")

    @cmd2.with_category("Command Management")
    def do_enable_commands(self, _) -> None:
        """Enable the Application Management commands."""
        self.enable_category(self.CMD_CAT_APP_MGMT)
        self.poutput("The Application Management commands have been enabled")


if __name__ == '__main__':
    import sys

    c = HelpCategories()
    sys.exit(c.cmdloop())
