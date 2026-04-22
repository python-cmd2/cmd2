#!/usr/bin/env python
"""
Demonstrates using CompletionItem instances as elements in an argparse choices list.

Technical Note:
  Using 'choices' is best for fixed datasets that do not change during the
  application's lifecycle. For dynamic data (e.g., results from a database or
  file system), use a 'choices_provider' instead.

Key strengths of this approach:
  1. Command handlers receive fully-typed domain objects directly in the
     argparse.Namespace, eliminating manual lookups from string keys.
  2. Choices carry tab-completion UI enhancements (display_meta, table_data)
     that are not supported by standard argparse string choices.
  3. Provides a single source of truth for completion UI, input validation,
     and object mapping.

This demo showcases two distinct approaches:
  1. Simple: Using CompletionItems with basic types (ints) to add UI metadata
     (display_meta) while letting argparse handle standard type conversion.
  2. Advanced: Using a custom 'text' alias and a type converter to map a friendly
     string (e.g., 'alice') directly to a complex object (Account).
"""

import argparse
import sys
from typing import (
    ClassVar,
    cast,
)

from cmd2 import (
    Cmd,
    Cmd2ArgumentParser,
    CompletionItem,
    with_argparser,
)

# -----------------------------------------------------------------------------
# Simple Example: Basic types with UI metadata
# -----------------------------------------------------------------------------
# Integers with metadata. No 'text' override or custom type converter needed.
# argparse will handle 'type=int' and validate it against the CompletionItem.value.
id_choices = [
    CompletionItem(101, display_meta="Alice's Account"),
    CompletionItem(202, display_meta="Bob's Account"),
]


# -----------------------------------------------------------------------------
# Advanced Example: Mapping friendly aliases to objects
# -----------------------------------------------------------------------------
class Account:
    """A complex object that we want to select by a friendly name."""

    def __init__(self, account_id: int, owner: str):
        self.account_id = account_id
        self.owner = owner

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Account):
            return self.account_id == other.account_id
        return False

    def __hash__(self) -> int:
        return hash(self.account_id)

    def __repr__(self) -> str:
        return f"Account(id={self.account_id}, owner='{self.owner}')"


# Map friendly 'text' aliases to the actual object 'value'.
# The user types 'alice' or 'bob' (tab-completion), but the parsed value will be the Account object.
accounts = [
    Account(101, "Alice"),
    Account(202, "Bob"),
]
account_choices = [
    CompletionItem(
        acc,
        text=acc.owner.lower(),
        display_meta=f"ID: {acc.account_id}",
    )
    for acc in accounts
]


def account_lookup(name: str) -> Account:
    """Type converter that looks up an Account by its friendly name."""
    for item in account_choices:
        if item.text == name:
            return cast(Account, item.value)
    raise argparse.ArgumentTypeError(f"invalid account: {name}")


# -----------------------------------------------------------------------------
# Demo Application
# -----------------------------------------------------------------------------
class ChoicesDemo(Cmd):
    """Demo cmd2 application."""

    DEFAULT_CATEGORY: ClassVar[str] = "Demo Commands"

    def __init__(self) -> None:
        super().__init__()
        self.intro = (
            "Welcome to the CompletionItem Choices Demo!\n"
            "Try 'simple' followed by [TAB] to see basic metadata.\n"
            "Try 'advanced' followed by [TAB] to see custom string mapping."
        )

    # Simple Command: argparse handles the int conversion, CompletionItem handles the UI
    simple_parser = Cmd2ArgumentParser()
    simple_parser.add_argument(
        "account_id",
        type=int,
        choices=id_choices,
        help="Select an account ID (tab-complete to see metadata)",
    )

    @with_argparser(simple_parser)
    def do_simple(self, args: argparse.Namespace) -> None:
        """Show an account ID selection (Simple Case)."""
        # argparse converted the input to an int, and validated it against the CompletionItem.value
        self.poutput(f"Selected Account ID: {args.account_id} (Type: {type(args.account_id).__name__})")

    # Advanced Command: Custom lookup and custom 'text' mapping
    advanced_parser = Cmd2ArgumentParser()
    advanced_parser.add_argument(
        "account",
        type=account_lookup,
        choices=account_choices,
        help="Select an account by owner name (tab-complete to see friendly names)",
    )

    @with_argparser(advanced_parser)
    def do_advanced(self, args: argparse.Namespace) -> None:
        """Show a custom string selection (Advanced Case)."""
        # args.account is the full Account object
        self.poutput(f"Selected Account: {args.account!r} (Type: {type(args.account).__name__})")


if __name__ == "__main__":
    app = ChoicesDemo()
    sys.exit(app.cmdloop())
