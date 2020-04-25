# coding=utf-8
"""
Defines the CustomParser used with override_parser.py example
"""
import sys

from cmd2 import Cmd2ArgumentParser, ansi, set_default_argument_parser


# First define the parser
class CustomParser(Cmd2ArgumentParser):
    """Overrides error class"""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> None:
        """Custom override that applies custom formatting to the error message"""
        lines = message.split('\n')
        linum = 0
        formatted_message = ''
        for line in lines:
            if linum == 0:
                formatted_message = 'Error: ' + line
            else:
                formatted_message += '\n       ' + line
            linum += 1

        self.print_usage(sys.stderr)
        formatted_message = ansi.style_warning(formatted_message)
        self.exit(2, '{}\n\n'.format(formatted_message))


# Now set the default parser for a cmd2 app
set_default_argument_parser(CustomParser)
