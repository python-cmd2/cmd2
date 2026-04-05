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
PRIVATE_ATTR_PREFIX = '_cmd2_'

# Prefix for public attributes injected by cmd2
PUBLIC_ATTR_PREFIX = 'cmd2_'


def cmd2_private_attr_name(name: str) -> str:
    """Build a private attribute name with the _cmd2_ prefix.

    :param name: the name of the attribute
    :return: the prefixed attribute name
    """
    return f'{PRIVATE_ATTR_PREFIX}{name}'


def cmd2_public_attr_name(name: str) -> str:
    """Build a public attribute name with the cmd2_ prefix.

    :param name: the name of the attribute
    :return: the prefixed attribute name
    """
    return f'{PUBLIC_ATTR_PREFIX}{name}'


##################################################################################################
# Private cmd2-specific attributes for internal use
##################################################################################################
CMD_ATTR_HELP_CATEGORY = cmd2_private_attr_name('help_category')
CLASS_ATTR_DEFAULT_HELP_CATEGORY = cmd2_private_attr_name('default_help_category')

# The parser for a command
CMD_ATTR_ARGPARSER = cmd2_private_attr_name('argparser')

# Whether or not tokens are unquoted before sending to argparse
CMD_ATTR_PRESERVE_QUOTES = cmd2_private_attr_name('preserve_quotes')

# Subcommand attributes for the base command name and the subcommand name
SUBCMD_ATTR_COMMAND = cmd2_private_attr_name('parent_command')
SUBCMD_ATTR_NAME = cmd2_private_attr_name('subcommand_name')
SUBCMD_ATTR_ADD_PARSER_KWARGS = cmd2_private_attr_name('subcommand_add_parser_kwargs')

# Attribute added to a parser which uniquely identifies its command set instance
PARSER_ATTR_COMMANDSET_ID = cmd2_private_attr_name('command_set_id')

##################################################################################################
# Public cmd2-specific attributes for use by developers
##################################################################################################

# Namespace attribute: Statement object that was created when parsing the command line
NS_ATTR_STATEMENT = cmd2_public_attr_name('statement')

# Namespace attribute: subcommand handler function or None if one was not set
NS_ATTR_SUBCMD_HANDLER = cmd2_public_attr_name('subcmd_handler')
