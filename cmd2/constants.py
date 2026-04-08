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
# Attribute Injection Constants
#
# cmd2 attaches custom attributes to various objects (functions, classes, and parsers) to
# track metadata and manage command state.
#
# Private attributes (_cmd2_ prefix) are for internal framework logic.
# Public attributes (cmd2_ prefix) are available for developer use, typically within
# argparse Namespaces.
##################################################################################################

# --- Private Internal Attributes ---

# Attached to a command function; defines its argument parser
CMD_ATTR_ARGPARSER = cmd2_private_attr_name('argparser')

# Attached to a command function; defines its help section category
CMD_ATTR_HELP_CATEGORY = cmd2_private_attr_name('help_category')

# Attached to a command function; defines whether tokens are unquoted before reaching argparse
CMD_ATTR_PRESERVE_QUOTES = cmd2_private_attr_name('preserve_quotes')

# Attached to a subcommand function; defines the full command path to the parent (e.g., "foo" or "foo bar")
SUBCMD_ATTR_COMMAND = cmd2_private_attr_name('parent_command')

# Attached to a subcommand function; defines the name of this specific subcommand (e.g., "bar")
SUBCMD_ATTR_NAME = cmd2_private_attr_name('subcommand_name')

# Attached to a subcommand function; specifies kwargs passed to add_parser()
SUBCMD_ATTR_ADD_PARSER_KWARGS = cmd2_private_attr_name('subcommand_add_parser_kwargs')

# Attached to an argparse parser; identifies the CommandSet instance it belongs to
PARSER_ATTR_COMMANDSET_ID = cmd2_private_attr_name('command_set_id')


# --- Public Developer Attributes ---

# Attached to an argparse Namespace; contains the Statement object created during parsing
NS_ATTR_STATEMENT = cmd2_public_attr_name('statement')

# Attached to an argparse Namespace; the function to handle the subcommand (or None)
NS_ATTR_SUBCMD_HANDLER = cmd2_public_attr_name('subcmd_handler')
