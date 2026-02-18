"""A simple example demonstrating a loadable command set."""

from cmd2 import (
    CommandSet,
    CompletionError,
    Statement,
    with_category,
    with_default_category,
)


@with_default_category('Basic Completion')
class BasicCompletionCommandSet(CommandSet):
    # This data is used to demonstrate delimiter_complete
    file_strs = (
        '/home/user/file.db',
        '/home/user/file space.db',
        '/home/user/another.db',
        '/home/other user/maps.db',
        '/home/other user/tests.db',
    )

    def do_delimiter_complete(self, statement: Statement) -> None:
        """Tab completes files from a list using delimiter_complete."""
        self._cmd.poutput(f"Args: {statement.args}")

    def complete_delimiter_complete(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        return self._cmd.delimiter_complete(text, line, begidx, endidx, match_against=self.file_strs, delimiter='/')

    def do_raise_error(self, statement: Statement) -> None:
        """Demonstrates effect of raising CompletionError."""
        self._cmd.poutput(f"Args: {statement.args}")

    def complete_raise_error(self, _text: str, _line: str, _begidx: int, _endidx: int) -> list[str]:
        """CompletionErrors can be raised if an error occurs while tab completing.

        Example use cases
            - Reading a database to retrieve a tab completion data set failed
            - A previous command line argument that determines the data set being completed is invalid
        """
        raise CompletionError("This is how a CompletionError behaves")

    @with_category('Not Basic Completion')
    def do_custom_category(self, _statement: Statement) -> None:
        self._cmd.poutput('Demonstrates a command that bypasses the default category')
