#
# coding=utf-8
"""Constants and definitions"""

import re

# Used for command parsing, tab completion and word breaks. Do not change.
QUOTES = ['"', "'"]
REDIRECTION_CHARS = ['|', '>']

# Regular expression to match ANSI escape codes
ANSI_ESCAPE_RE = re.compile(r'\x1b[^m]*m')
