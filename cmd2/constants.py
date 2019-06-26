#
# coding=utf-8
"""Constants and definitions"""

# Used for command parsing, output redirection, tab completion and word
# breaks. Do not change.
QUOTES = ['"', "'"]
REDIRECTION_PIPE = '|'
REDIRECTION_OUTPUT = '>'
REDIRECTION_APPEND = '>>'
REDIRECTION_CHARS = [REDIRECTION_PIPE, REDIRECTION_OUTPUT]
REDIRECTION_TOKENS = [REDIRECTION_PIPE, REDIRECTION_OUTPUT, REDIRECTION_APPEND]
COMMENT_CHAR = '#'
MULTILINE_TERMINATOR = ';'

LINE_FEED = '\n'

DEFAULT_SHORTCUTS = {'?': 'help', '!': 'shell', '@': 'run_script', '@@': '_relative_run_script'}

# Values for cmd2's allow_ansi setting
ANSI_NEVER = 'Never'
ANSI_TERMINAL = 'Terminal'
ANSI_ALWAYS = 'Always'
