"""Constants used throughout ``cmd2``."""

# Unless documented in https://cmd2.readthedocs.io/en/latest/api/index.html
# nothing here should be considered part of the public API of this module

INFINITY = float('inf')

# Used for command parsing, output redirection, completion, and word breaks. Do not change.
QUOTES = ['"', "'"]
REDIRECTION_PIPE = '|'
REDIRECTION_OVERWRITE = '>'
REDIRECTION_APPEND = '>>'
REDIRECTION_CHARS = [REDIRECTION_PIPE, REDIRECTION_OVERWRITE]
REDIRECTION_TOKENS = [REDIRECTION_PIPE, REDIRECTION_OVERWRITE, REDIRECTION_APPEND]
COMMENT_CHAR = '#'
MULTILINE_TERMINATOR = ';'

LINE_FEED = '\n'

DEFAULT_SHORTCUTS = {'?': 'help', '!': 'shell', '@': 'run_script', '@@': '_relative_run_script'}

# Used as the command name placeholder in disabled command messages.
COMMAND_NAME = "<COMMAND_NAME>"

# All command functions start with this
COMMAND_FUNC_PREFIX = 'do_'

# All help functions start with this
HELP_FUNC_PREFIX = 'help_'

# All command completer functions start with this
COMPLETER_FUNC_PREFIX = 'complete_'

# Prefix for private attributes injected by cmd2
CMD2_ATTR_PREFIX = '_cmd2_'


def cmd2_attr_name(name: str) -> str:
    """Build an attribute name with the cmd2 prefix.

    :param name: the name of the attribute
    :return: the prefixed attribute name
    """
    return f'{CMD2_ATTR_PREFIX}{name}'


# The custom help category a command belongs to
CMD_ATTR_HELP_CATEGORY = cmd2_attr_name('help_category')
CLASS_ATTR_DEFAULT_HELP_CATEGORY = cmd2_attr_name('default_help_category')

# The argparse parser for the command
CMD_ATTR_ARGPARSER = cmd2_attr_name('argparser')

# Whether or not tokens are unquoted before sending to argparse
CMD_ATTR_PRESERVE_QUOTES = cmd2_attr_name('preserve_quotes')

# subcommand attributes for the base command name and the subcommand name
SUBCMD_ATTR_COMMAND = cmd2_attr_name('parent_command')
SUBCMD_ATTR_NAME = cmd2_attr_name('subcommand_name')
SUBCMD_ATTR_ADD_PARSER_KWARGS = cmd2_attr_name('subcommand_add_parser_kwargs')

# argparse attribute uniquely identifying the command set instance
PARSER_ATTR_COMMANDSET_ID = cmd2_attr_name('command_set_id')

# custom attributes added to argparse Namespaces
NS_ATTR_SUBCMD_HANDLER = cmd2_attr_name('subcmd_handler')
