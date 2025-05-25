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
    # List of strings used with completion functions
    food_item_strs = ('Pizza', 'Ham', 'Ham Sandwich', 'Potato')
    sport_item_strs = ('Bat', 'Basket', 'Basketball', 'Football', 'Space Ball')

    # This data is used to demonstrate delimiter_complete
    file_strs = (
        '/home/user/file.db',
        '/home/user/file space.db',
        '/home/user/another.db',
        '/home/other user/maps.db',
        '/home/other user/tests.db',
    )

    def do_flag_based(self, statement: Statement) -> None:
        """Tab completes arguments based on a preceding flag using flag_based_complete
        -f, --food [completes food items]
        -s, --sport [completes sports]
        -p, --path [completes local file system paths].
        """
        self._cmd.poutput(f"Args: {statement.args}")

    def complete_flag_based(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        """Completion function for do_flag_based."""
        flag_dict = {
            # Tab complete food items after -f and --food flags in command line
            '-f': self.food_item_strs,
            '--food': self.food_item_strs,
            # Tab complete sport items after -s and --sport flags in command line
            '-s': self.sport_item_strs,
            '--sport': self.sport_item_strs,
            # Tab complete using path_complete function after -p and --path flags in command line
            '-p': self._cmd.path_complete,
            '--path': self._cmd.path_complete,
        }

        return self._cmd.flag_based_complete(text, line, begidx, endidx, flag_dict=flag_dict)

    def do_index_based(self, statement: Statement) -> None:
        """Tab completes first 3 arguments using index_based_complete."""
        self._cmd.poutput(f"Args: {statement.args}")

    def complete_index_based(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        """Completion function for do_index_based."""
        index_dict = {
            1: self.food_item_strs,  # Tab complete food items at index 1 in command line
            2: self.sport_item_strs,  # Tab complete sport items at index 2 in command line
            3: self._cmd.path_complete,  # Tab complete using path_complete function at index 3 in command line
        }

        return self._cmd.index_based_complete(text, line, begidx, endidx, index_dict=index_dict)

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
