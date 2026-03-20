#!/usr/bin/env python3
"""A small example demonstrating Typer integration with cmd2.

Shows how to use ``@cmd2.with_typer`` to define commands with
type-safe arguments, options, and tab completion — all powered
by Typer/Click instead of argparse.

Requires the ``typer`` extra::

    pip install cmd2[typer]
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

import typer

import cmd2

# ---------------------------------------------------------------------------
# Enums for built-in choice completion
# ---------------------------------------------------------------------------


class Color(str, Enum):
    """Typer auto-completes enum members as choices."""

    red = "red"
    green = "green"
    blue = "blue"
    yellow = "yellow"


class Priority(str, Enum):
    """Priority levels for tasks."""

    high = "high"
    medium = "medium"
    low = "low"


# ---------------------------------------------------------------------------
# Custom autocompletion callback
# ---------------------------------------------------------------------------

TEAM_MEMBERS = ["Alice", "Bob", "Charlie", "Diana", "Eve"]


def _member_complete(incomplete: str) -> list[str]:
    """Custom completer — returns matching team member names."""
    return [m for m in TEAM_MEMBERS if m.lower().startswith(incomplete.lower())]


# ---------------------------------------------------------------------------
# Application — all features in one class
# ---------------------------------------------------------------------------


class TyperExampleApp(cmd2.Cmd):
    """A cmd2 application showcasing every Typer integration feature."""

    intro = "Welcome! Type 'help' to list commands. Try tab-completion!\n"
    prompt = "typer-demo> "

    # 1. Simple positional argument + option with default
    @cmd2.with_typer
    def do_greet(
        self,
        name: Annotated[str, typer.Argument(help="Person to greet")],
        greeting: Annotated[str, typer.Option("--greeting", "-g", help="Greeting word")] = "Hello",
        shout: Annotated[bool, typer.Option("--shout", help="SHOUT the greeting")] = False,
    ) -> None:
        """Greet someone by name.

        Examples:
            greet World
            greet Alice --greeting Hi --shout
        """
        msg = f"{greeting}, {name}!"
        self.poutput(msg.upper() if shout else msg)

    # 2. Enum-based choices — Typer auto-generates completions from members
    @cmd2.with_typer
    def do_paint(
        self,
        item: Annotated[str, typer.Argument(help="What to paint")],
        color: Annotated[Color, typer.Option("--color", "-c", help="Color to use")] = Color.blue,
    ) -> None:
        """Paint an item with a color (tab-complete the --color values!).

        Examples:
            paint wall --color red
            paint fence
        """
        self.poutput(f"Painting {item} {color.value}.")

    # 3. Custom autocompletion callback
    @cmd2.with_typer
    def do_assign(
        self,
        task: Annotated[str, typer.Argument(help="Task description")],
        member: Annotated[
            str,
            typer.Option("--to", help="Team member to assign to", autocompletion=_member_complete),
        ] = "unassigned",
    ) -> None:
        """Assign a task to a team member (tab-complete the --to values!).

        Examples:
            assign "Fix login bug" --to Alice
            assign "Write docs"
        """
        self.poutput(f"Assigned '{task}' to {member}.")

    # 4. Variadic list argument
    @cmd2.with_typer
    def do_sum(
        self,
        numbers: Annotated[list[float], typer.Argument(help="Numbers to add up")],
    ) -> None:
        """Sum a list of numbers.

        Examples:
            sum 1 2 3
            sum 10.5 20.3
        """
        self.poutput(f"{' + '.join(str(n) for n in numbers)} = {sum(numbers)}")

    # 5. preserve_quotes — raw string handling
    @cmd2.with_typer(preserve_quotes=True)
    def do_raw(
        self,
        text: Annotated[str, typer.Argument(help="Text echoed verbatim (quotes preserved)")],
    ) -> None:
        """Echo text exactly as typed, preserving quotes.

        Examples:
            raw "hello world"
            raw 'single quotes'
        """
        self.poutput(f"raw: {text}")

    # 6. Subcommands via an explicit Typer app
    project_app = typer.Typer(help="Manage projects and tasks")
    task_app = typer.Typer(help="Manage tasks within a project")

    @project_app.command("list")
    def _project_list(self) -> None:
        """List all projects."""
        self.poutput("  1. Website Redesign")
        self.poutput("  2. Mobile App")
        self.poutput("  3. API Gateway")

    @project_app.command("create")
    def _project_create(
        self,
        name: Annotated[str, typer.Argument(help="Project name")],
        priority: Annotated[Priority, typer.Option("--priority", "-p", help="Priority level")] = Priority.medium,
    ) -> None:
        """Create a new project (tab-complete --priority from the enum!)."""
        self.poutput(f"Created project '{name}' with {priority.value.upper()} priority.")

    @task_app.command("add")
    def _task_add(
        self,
        title: Annotated[str, typer.Argument(help="Task title")],
        assignee: Annotated[
            str,
            typer.Option("--assignee", "-a", help="Who to assign", autocompletion=_member_complete),
        ] = "unassigned",
    ) -> None:
        """Add a task (tab-complete --assignee!)."""
        self.poutput(f"Added task '{title}' assigned to {assignee}.")

    @task_app.command("done")
    def _task_done(
        self,
        task_id: Annotated[int, typer.Argument(help="Task ID to mark done")],
    ) -> None:
        """Mark a task as done."""
        self.poutput(f"Task #{task_id} marked as done.")

    project_app.add_typer(task_app, name="task")

    @cmd2.with_typer(project_app)
    def do_project(self) -> None:
        """Manage projects and tasks (try: project <TAB>, project task <TAB>)."""


if __name__ == "__main__":
    app = TyperExampleApp()
    app.cmdloop()
