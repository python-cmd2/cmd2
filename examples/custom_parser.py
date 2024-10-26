# coding=utf-8
"""
The standard parser used by cmd2 built-in commands is Cmd2ArgumentParser.
The following code shows how to override it with your own parser class.
"""

import sys
from typing import NoReturn

from cmd2 import (
    Cmd2ArgumentParser,
    ansi,
    cmd2,
    set_default_argument_parser_type,
)


# Since built-in commands rely on customizations made in Cmd2ArgumentParser,
# your custom parser class should inherit from Cmd2ArgumentParser.
class CustomParser(Cmd2ArgumentParser):
    """Overrides error method"""

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> NoReturn:
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

        # Format errors with style_warning()
        formatted_message = ansi.style_warning(formatted_message)
        self.exit(2, '{}\n\n'.format(formatted_message))


if __name__ == '__main__':
    import sys

    # Set the default parser type before instantiating app.
    set_default_argument_parser_type(CustomParser)

    app = cmd2.Cmd(include_ipy=True, persistent_history_file='cmd2_history.dat')
    app.self_in_py = True  # Enable access to "self" within the py command
    app.debug = True  # Show traceback if/when an exception occurs
    sys.exit(app.cmdloop())
