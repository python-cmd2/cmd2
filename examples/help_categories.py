#!/usr/bin/env python
# coding=utf-8
"""
A sample application for tagging categories on commands.
"""

from cmd2 import Cmd, HELP_CATEGORY, __version__


class HelpCategories(Cmd):
    """ Example cmd2 application. """

    # Command categories
    CMD_CAT_CONNECTING = 'Connecting'
    CMD_CAT_APP_MGMT = 'Application Management'
    CMD_CAT_SERVER_INFO = 'Server Information'

    def __init__(self):
        # Set use_ipython to True to enable the "ipy" command which embeds and interactive IPython shell
        Cmd.__init__(self, use_ipython=False)

    def do_connect(self, _):
        """Connect command"""
        self.poutput('Connect')

    def do_which(self, _):
        """Which command"""
        self.poutput('Which')

    # Tag the above command functions under the category Connecting
    setattr(do_connect, HELP_CATEGORY, CMD_CAT_CONNECTING)
    setattr(do_which, HELP_CATEGORY, CMD_CAT_CONNECTING)

    def do_list(self, _):
        """List command"""
        self.poutput('List')

    def do_deploy(self, _):
        """Deploy command"""
        self.poutput('Which')

    def do_start(self, _):
        """Start command"""
        self.poutput('Start')

    def do_sessions(self, _):
        """Sessions command"""
        self.poutput('Sessions')

    def do_redeploy(self, _):
        """Redeploy command"""
        self.poutput('Redeploy')

    def do_restart(self, _):
        """Restart command"""
        self.poutput('Restart')

    def do_expire(self, _):
        """Expire command"""
        self.poutput('Expire')

    def do_undeploy(self, _):
        """Undeploy command"""
        self.poutput('Undeploy')

    def do_stop(self, _):
        """Stop command"""
        self.poutput('Stop')

    def do_findleakers(self, _):
        """Find Leakers command"""
        self.poutput('Find Leakers')

    # Tag the above command functions under the category Application Management
    setattr(do_list, HELP_CATEGORY, CMD_CAT_APP_MGMT)
    setattr(do_deploy, HELP_CATEGORY, CMD_CAT_APP_MGMT)
    setattr(do_start, HELP_CATEGORY, CMD_CAT_APP_MGMT)
    setattr(do_sessions, HELP_CATEGORY, CMD_CAT_APP_MGMT)
    setattr(do_redeploy, HELP_CATEGORY, CMD_CAT_APP_MGMT)
    setattr(do_restart, HELP_CATEGORY, CMD_CAT_APP_MGMT)
    setattr(do_expire, HELP_CATEGORY, CMD_CAT_APP_MGMT)
    setattr(do_undeploy, HELP_CATEGORY, CMD_CAT_APP_MGMT)
    setattr(do_stop, HELP_CATEGORY, CMD_CAT_APP_MGMT)
    setattr(do_findleakers, HELP_CATEGORY, CMD_CAT_APP_MGMT)

    def do_resources(self, _):
        """Resources command"""
        self.poutput('Resources')

    def do_status(self, _):
        """Status command"""
        self.poutput('Status')

    def do_serverinfo(self, _):
        """Server Info command"""
        self.poutput('Server Info')

    def do_thread_dump(self, _):
        """Thread Dump command"""
        self.poutput('Thread Dump')

    def do_sslconnectorciphers(self, _):
        """SSL Connector Ciphers command"""
        self.poutput('SSL Connector Ciphers')

    def do_vminfo(self, _):
        """VM Info command"""
        self.poutput('VM Info')

    # Tag the above command functions under the category Server Information
    setattr(do_resources, HELP_CATEGORY, CMD_CAT_SERVER_INFO)
    setattr(do_status, HELP_CATEGORY, CMD_CAT_SERVER_INFO)
    setattr(do_serverinfo, HELP_CATEGORY, CMD_CAT_SERVER_INFO)
    setattr(do_thread_dump, HELP_CATEGORY, CMD_CAT_SERVER_INFO)
    setattr(do_sslconnectorciphers, HELP_CATEGORY, CMD_CAT_SERVER_INFO)
    setattr(do_vminfo, HELP_CATEGORY, CMD_CAT_SERVER_INFO)

    # The following command functions don't have the HELP_CATEGORY attribute set
    # and show up in the 'Other' group
    def do_config(self, _):
        """Config command"""
        self.poutput('Config')

    def do_version(self, _):
        """Version command"""
        self.poutput(__version__)


if __name__ == '__main__':
    c = HelpCategories()
    c.cmdloop()
