"""Defines the CustomParser used with override_parser.py example."""

import sys

from cmd2 import (
    Cmd2ArgumentParser,
    ansi,
    set_default_argument_parser_type,
)


# First define the parser
class CustomParser(Cmd2ArgumentParser):
    """Overrides error class."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> None:
        """Custom override that applies custom formatting to the error message."""
        lines = message.split('\n')
        formatted_message = ''
        for linum, line in enumerate(lines):
            if linum == 0:
                formatted_message = 'Error: ' + line
            else:
                formatted_message += '\n       ' + line

        self.print_usage(sys.stderr)

        # Format errors with style_warning()
        formatted_message = ansi.style_warning(formatted_message)
        self.exit(2, f'{formatted_message}\n\n')


# Now set the default parser for a cmd2 app
set_default_argument_parser_type(CustomParser)
