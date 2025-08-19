"""
The standard parser used by cmd2 built-in commands is Cmd2ArgumentParser.
The following code shows how to override it with your own parser class.
"""

import sys
from typing import NoReturn

from cmd2 import (
    Cmd2ArgumentParser,
    cmd2,
    set_default_argument_parser_type,
    styles,
    stylize,
)


# Since built-in commands rely on customizations made in Cmd2ArgumentParser,
# your custom parser class should inherit from Cmd2ArgumentParser.
class CustomParser(Cmd2ArgumentParser):
    """Overrides error method."""

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> NoReturn:
        """Custom override that applies custom formatting to the error message."""
        lines = message.split('\n')
        formatted_message = ''
        for linum, line in enumerate(lines):
            if linum == 0:
                formatted_message = 'Error: ' + line
            else:
                formatted_message += '\n       ' + line

        self.print_usage(sys.stderr)

        # Format errors with warning style
        formatted_message = stylize(
            formatted_message,
            style=styles.WARNING,
        )
        self.exit(2, f'{formatted_message}\n\n')


if __name__ == '__main__':
    import sys

    # Set the default parser type before instantiating app.
    set_default_argument_parser_type(CustomParser)

    app = cmd2.Cmd(include_ipy=True, persistent_history_file='cmd2_history.dat')
    app.self_in_py = True  # Enable access to "self" within the py command
    app.debug = True  # Show traceback if/when an exception occurs
    sys.exit(app.cmdloop())
