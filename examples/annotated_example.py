#!/usr/bin/env python3
"""Annotated decorator example -- type-hint-driven argument parsing.

Shows how ``@with_annotated`` eliminates boilerplate compared to
``@with_argparser``.  The focus is on features that are unique to
the annotated style -- type inference, auto-completion from types, and
typed function parameters -- while also demonstrating that all of cmd2's
advanced completion features (choices_provider, completer, table_columns,
arg_tokens) remain available via ``Annotated`` metadata.

Compare with ``argparse_completion.py`` which uses ``@with_argparser``
for the same completion features.

Usage::

    python examples/annotated_example.py
"""

import sys
from enum import Enum
from pathlib import Path
from typing import Annotated

import cmd2
from cmd2 import (
    Choices,
    Cmd,
)


class Color(str, Enum):
    red = "red"
    green = "green"
    blue = "blue"
    yellow = "yellow"


class LogLevel(str, Enum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"


class AnnotatedExample(Cmd):
    """Demonstrates @with_annotated strengths over @with_argparser."""

    intro = "Welcome! Try tab-completing the commands below.\n"
    prompt = "annotated> "

    def __init__(self) -> None:
        super().__init__(include_ipy=True)
        self._sports = ['Basketball', 'Football', 'Tennis', 'Hockey']

    # -- Type inference: int, float, bool ------------------------------------
    # With @with_argparser you'd manually set type=int and action='store_true'.
    # Here the decorator infers everything from the annotations.

    @cmd2.with_annotated
    def do_add(self, a: int, b: int = 0, verbose: bool = False) -> None:
        """Add two integers. Types are inferred from annotations.

        Examples:
            add 2 --b 3
            add 10 --b 5 --verbose
        """
        result = a + b
        if verbose:
            self.poutput(f"{a} + {b} = {result}")
        else:
            self.poutput(str(result))

    # -- Enum auto-completion ------------------------------------------------
    # With @with_argparser you'd list every member in choices=[...].
    # Here the Enum type provides choices and validation automatically.

    @cmd2.with_annotated
    def do_paint(
        self,
        item: str,
        color: Annotated[Color, cmd2.Option("--color", "-c", help_text="Color to use")] = Color.blue,
        level: LogLevel = LogLevel.info,
    ) -> None:
        """Paint an item. Enum types auto-complete their member values.

        Try:
            paint wall --color <TAB>
            paint wall --level <TAB>
        """
        self.poutput(f"[{level.value}] Painting {item} {color.value}")

    # -- Path auto-completion ------------------------------------------------
    # With @with_argparser you'd wire completer=Cmd.path_complete on each arg.
    # Here the Path type triggers filesystem completion automatically.

    @cmd2.with_annotated
    def do_copy(self, src: Path, dst: Path) -> None:
        """Copy a file. Path parameters auto-complete filesystem paths.

        Try:
            copy ./<TAB>  /tmp/<TAB>
        """
        self.poutput(f"Copying {src} -> {dst}")

    # -- Bool flags ----------------------------------------------------------
    # With @with_argparser you'd set action='store_true' or 'store_false'.
    # Here bool defaults drive the flag style automatically.
    #   False default -> --flag (store_true)
    #   True default  -> --no-flag (store_false)

    @cmd2.with_annotated
    def do_build(
        self,
        target: str,
        verbose: bool = False,
        color: bool = True,
    ) -> None:
        """Build a target. Bool flags are inferred from defaults.

        ``verbose: bool = False`` becomes ``--verbose`` (store_true).
        ``color: bool = True`` becomes ``--no-color`` (store_false).

        Try:
            build app --verbose --no-color
        """
        parts = [f"Building {target}"]
        if verbose:
            parts.append("(verbose)")
        if not color:
            parts.append("(no color)")
        self.poutput(" ".join(parts))

    # -- List arguments ------------------------------------------------------
    # With @with_argparser you'd set type=float and nargs='+'.
    # Here list[float] does both at once.

    @cmd2.with_annotated
    def do_sum(self, numbers: list[float]) -> None:
        """Sum numbers. ``list[T]`` becomes ``nargs='+'`` automatically.

        Try:
            sum 1.5 2.5 3.0
        """
        self.poutput(f"{' + '.join(str(n) for n in numbers)} = {sum(numbers)}")

    # -- Typed kwargs --------------------------------------------------------
    # With @with_argparser you'd access args.name, args.count on a Namespace.
    # Here each parameter is a typed local variable.

    @cmd2.with_annotated
    def do_greet(self, name: str, count: int = 1, loud: bool = False) -> None:
        """Greet someone. Parameters are typed -- no Namespace unpacking.

        Try:
            greet Alice --count 3 --loud
        """
        for _ in range(count):
            msg = f"Hello {name}!"
            self.poutput(msg.upper() if loud else msg)

    # -- Advanced: choices_provider + arg_tokens -----------------------------
    # These cmd2-specific features still work via Annotated metadata.

    def sport_choices(self) -> Choices:
        """choices_provider using instance data."""
        return Choices.from_values(self._sports)

    def context_choices(self, arg_tokens: dict[str, list[str]]) -> Choices:
        """arg_tokens-aware completion -- choices depend on prior arguments."""
        sport = arg_tokens.get("sport", [""])[0]
        if sport == "Basketball":
            return Choices.from_values(["3-pointer", "dunk", "layup"])
        if sport == "Football":
            return Choices.from_values(["touchdown", "field-goal", "punt"])
        return Choices.from_values(["play"])

    @cmd2.with_annotated
    def do_score(
        self,
        sport: Annotated[
            str,
            cmd2.Argument(
                choices_provider=sport_choices,
                help_text="Sport to score",
            ),
        ],
        play: Annotated[
            str,
            cmd2.Argument(
                choices_provider=context_choices,
                help_text="Type of play (depends on sport)",
            ),
        ],
        points: int = 1,
    ) -> None:
        """Score a play. Demonstrates choices_provider and arg_tokens.

        Try:
            score <TAB>
            score Basketball <TAB>
            score Football <TAB>
        """
        self.poutput(f"{sport}: {play} for {points} point(s)")

    # -- Preserve quotes -----------------------------------------------------

    @cmd2.with_annotated(preserve_quotes=True)
    def do_echo(self, text: str) -> None:
        """Echo text with quotes preserved.

        Try:
            echo "hello world"
        """
        self.poutput(text)


if __name__ == '__main__':
    app = AnnotatedExample()
    sys.exit(app.cmdloop())
