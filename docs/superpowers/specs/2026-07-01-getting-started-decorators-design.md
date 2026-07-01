# Design: Update `getting_started.py` with Argument Parsers

## Purpose
Update `examples/getting_started.py` to demonstrate the recommended best practices for defining command arguments using the `@with_argparser` and `@with_annotated` decorators.

## Current State
The `do_intro` and `do_echo` methods in `examples/getting_started.py` currently accept a single `cmd2.Statement` argument.

## Planned Changes

### 1. `do_intro` (using `@with_annotated`)
Update the `do_intro` method to use the `@cmd2.with_annotated` decorator to automatically derive an argument parser from Python type hints.

*   **Arguments:**
    *   `interactive: bool = False`: A boolean flag (`--interactive` or `--no-interactive`).
    *   `repeat: int = 1`: An integer option (`--repeat`) specifying how many times to display the intro.
*   **Behavior:**
    *   The method will loop `repeat` times, printing the intro banner.
    *   If `interactive` is true, an interactive prompt or a simulated interactive message can be displayed after the intro. For the scope of this example, we will just print an extra line noting the interactive mode is enabled.

### 2. `do_echo` (using `@with_argparser`)
Update the `do_echo` method to use the `@cmd2.with_argparser` decorator with a custom-defined `Cmd2ArgumentParser`.

*   **Parser Definition:**
    ```python
    echo_parser = cmd2.Cmd2ArgumentParser(description="Multiline command that echoes input.")
    echo_parser.add_argument("-u", "--upper", action="store_true", help="uppercase the output")
    echo_parser.add_argument("-r", "--repeat", type=int, default=1, help="output [n] times")
    echo_parser.add_argument("words", nargs="+", help="words to print")
    ```
*   **Arguments received:** `args: argparse.Namespace`
*   **Behavior:**
    *   Join the `args.words` list into a string.
    *   If `args.upper` is true, convert the string to uppercase.
    *   Print the stylized string `args.repeat` times.

### 3. Documentation
*   Update the top-level docstring in `examples/getting_started.py` to include mentioning that the script demonstrates argument parsing with `@with_argparser` and `@with_annotated`.
*   Ensure the docstrings for `do_intro` and `do_echo` clearly explain their usage of the respective decorators.

## Testing Strategy
The changes are in an example script. We will verify the changes by running the script manually and observing the help output and command execution to ensure the decorators are functioning as expected. We will also run `make check` to ensure code style compliance.
