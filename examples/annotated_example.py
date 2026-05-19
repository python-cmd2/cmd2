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
from argparse import Namespace
from collections.abc import Callable
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Literal,
)

import cmd2
from cmd2 import (
    Choices,
    Cmd,
)
from cmd2.annotated import (
    Argument,
    Group,
    Option,
    with_annotated,
)


class Color(StrEnum):
    red = "red"
    green = "green"
    blue = "blue"
    yellow = "yellow"


class LogLevel(StrEnum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"


class VerbatimHelpFormatter(cmd2.RawDescriptionCmd2HelpFormatter):
    """Custom help formatter: keeps the description's line breaks verbatim."""


class StrictArgumentParser(cmd2.Cmd2ArgumentParser):
    """Custom parser class: disables ``--opt`` prefix abbreviation."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)


ANNOTATED_CATEGORY = "Annotated Commands"


class AnnotatedExample(Cmd):
    """Demonstrates @with_annotated strengths over @with_argparser."""

    intro = "Welcome! Try tab-completing the commands below.\n"
    prompt = "annotated> "

    def __init__(self) -> None:
        super().__init__(include_ipy=True)
        self._sports = ["Basketball", "Football", "Tennis", "Hockey"]
        self._default_region = "staging"

    # -- Type inference: int, float, bool ------------------------------------
    # With @with_argparser you'd manually set type=int and action='store_true'.
    # Here the decorator infers everything from the annotations.

    @with_annotated
    @cmd2.with_category(ANNOTATED_CATEGORY)
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

    @with_annotated
    @cmd2.with_category(ANNOTATED_CATEGORY)
    def do_paint(
        self,
        item: str,
        color: Annotated[Color, Option("--color", "-c", help_text="Color to use")] = Color.blue,
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

    @with_annotated
    @cmd2.with_category(ANNOTATED_CATEGORY)
    def do_copy(self, src: Path, dst: Path) -> None:
        """Copy a file. Path parameters auto-complete filesystem paths.

        Try:
            copy ./<TAB>  /tmp/<TAB>
        """
        self.poutput(f"Copying {src} -> {dst}")

    # -- Bool flags ----------------------------------------------------------
    # With @with_argparser you'd spell out the action.
    # Here bool defaults drive the generated boolean option.

    @with_annotated
    @cmd2.with_category(ANNOTATED_CATEGORY)
    def do_build(
        self,
        target: str,
        verbose: bool = False,
        color: bool = True,
    ) -> None:
        """Build a target. Bool flags are inferred from defaults.

        ``verbose: bool = False`` becomes a boolean optional flag.
        ``color: bool = True`` becomes a ``--color`` / ``--no-color`` style option.

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

    @with_annotated
    @cmd2.with_category(ANNOTATED_CATEGORY)
    def do_sum(self, numbers: list[float]) -> None:
        """Sum numbers. ``list[T]`` becomes ``nargs='+'`` automatically.

        Try:
            sum 1.5 2.5 3.0
        """
        self.poutput(f"{' + '.join(str(n) for n in numbers)} = {sum(numbers)}")

    # -- Literal + Decimal ---------------------------------------------------
    # Literal values become validated choices. Decimal values preserve precision.

    @with_annotated
    @cmd2.with_category(ANNOTATED_CATEGORY)
    def do_deploy(
        self,
        service: str,
        mode: Literal["safe", "fast"] = "safe",
        budget: Decimal = Decimal("1.50"),
    ) -> None:
        """Deploy using Literal choices and Decimal parsing.

        Try:
            deploy api --mode <TAB>
            deploy api --mode fast --budget 2.75
        """
        self.poutput(f"Deploying {service} in {mode} mode with budget {budget}")

    # -- Typed kwargs --------------------------------------------------------
    # With @with_argparser you'd access args.name, args.count on a Namespace.
    # Here each parameter is a typed local variable.

    @with_annotated
    @cmd2.with_category(ANNOTATED_CATEGORY)
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

    @with_annotated
    @cmd2.with_category(ANNOTATED_CATEGORY)
    def do_score(
        self,
        sport: Annotated[
            str,
            Argument(
                choices_provider=sport_choices,
                help_text="Sport to score",
            ),
        ],
        play: Annotated[
            str,
            Argument(
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

    # -- Namespace provider --------------------------------------------------
    # This mirrors one of @with_argparser's advanced features.

    def default_namespace(self) -> Namespace:
        return Namespace(region=self._default_region)

    @with_annotated(ns_provider=default_namespace)
    @cmd2.with_category(ANNOTATED_CATEGORY)
    def do_ship(self, package: str, region: str = "local") -> None:
        """Use ns_provider to prepopulate parser defaults at runtime.

        Try:
            ship parcel
            ship parcel --region remote
        """
        self.poutput(f"Shipping {package} to {region}")

    # -- Unknown args --------------------------------------------------------

    @with_annotated(with_unknown_args=True)
    @cmd2.with_category(ANNOTATED_CATEGORY)
    def do_flex(self, name: str, _unknown: list[str] | None = None) -> None:
        """Capture unknown arguments instead of failing parse.

        Try:
            flex alice --future-flag value
        """
        self.poutput(f"name={name}")
        if _unknown:
            self.poutput(f"unknown={_unknown}")

    # -- Subcommands ---------------------------------------------------------
    # @with_annotated also supports typed subcommand trees.

    @with_annotated(base_command=True)
    @cmd2.with_category(ANNOTATED_CATEGORY)
    def do_manage(self, verbose: bool = False, *, cmd2_handler: Callable[[], Any] | None = None) -> None:
        """Base command for annotated subcommands.

        Try:
            help manage
            manage project add demo
        """
        if verbose:
            self.poutput("verbose mode")
        if cmd2_handler:
            cmd2_handler()

    @with_annotated(subcommand_to="manage", base_command=True, help="manage projects")
    def manage_project(self, *, cmd2_handler: Callable[[], Any] | None = None) -> None:
        if cmd2_handler:
            cmd2_handler()

    @with_annotated(subcommand_to="manage project", help="add a project")
    def manage_project_add(self, name: str) -> None:
        self.poutput(f"project added: {name}")

    @with_annotated(subcommand_to="manage project", help="list projects")
    def manage_project_list(self) -> None:
        self.poutput("project list: demo")

    # -- Parser customization ------------------------------------------------
    # The generated parser's help text and argument grouping are configurable
    # without dropping down to a hand-built parser.

    @with_annotated(
        description="Open a network connection.",
        epilog="Example: connect example.com --port 2222",
        groups=(Group("host", "port", title="connection", description="where to connect"),),
    )
    @cmd2.with_category(ANNOTATED_CATEGORY)
    def do_connect(self, host: str, port: int = 22, verbose: bool = False) -> None:
        """Connect to a host.

        Try:
            help connect
            connect example.com --port 2222 --verbose
        """
        msg = f"Connecting to {host}:{port}"
        self.poutput(f"{msg} (verbose)" if verbose else msg)

    # -- Mutually exclusive groups -------------------------------------------
    # Group instances passed to mutually_exclusive_groups make argparse reject
    # combinations (title/description are ignored here).

    @with_annotated(
        description="Export data in exactly one format.",
        mutually_exclusive_groups=(Group("json", "csv"),),
    )
    @cmd2.with_category(ANNOTATED_CATEGORY)
    def do_export(self, name: str, json: bool = False, csv: bool = False) -> None:
        """Export a dataset; --json and --csv are mutually exclusive.

        Try:
            export sales --json
            export sales --json --csv   # rejected: not allowed together
        """
        fmt = "json" if json else "csv" if csv else "text"
        self.poutput(f"Exporting {name} as {fmt}")

    # -- Custom formatter and parser classes ---------------------------------
    # A custom help formatter or Cmd2ArgumentParser subclass can be supplied.

    @with_annotated(
        description="Generate a report.\n  - line breaks here are preserved\n  - thanks to the custom formatter",
        formatter_class=VerbatimHelpFormatter,
        parser_class=StrictArgumentParser,
    )
    @cmd2.with_category(ANNOTATED_CATEGORY)
    def do_report(self, source: str, level: int = 1, verbose: bool = False) -> None:
        """Generate a report.

        ``help report`` shows the description with its line breaks intact
        (VerbatimHelpFormatter), and StrictArgumentParser rejects abbreviated flags.

        Try:
            help report
            report db --level 2 --verbose
            report db --lev 2          # rejected: abbreviation disabled
        """
        msg = f"Report for {source} at level {level}"
        self.poutput(f"{msg} (verbose)" if verbose else msg)

    # -- Preserve quotes -----------------------------------------------------

    @with_annotated(preserve_quotes=True)
    @cmd2.with_category(ANNOTATED_CATEGORY)
    def do_echo(self, text: str) -> None:
        """Echo text with quotes preserved.

        Try:
            echo "hello world"
        """
        self.poutput(text)


if __name__ == "__main__":
    app = AnnotatedExample()
    sys.exit(app.cmdloop())
