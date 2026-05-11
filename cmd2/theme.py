"""Provides a centralized theming system for cmd2.

This module manages the global theme used for both Rich terminal output and
prompt-toolkit interactive components. It ensures that styling is consistent
and synchronized across the entire application when the theme is updated using
the following strategy.

1. Rich consoles use a persistent Theme object that is updated in-place.
2. prompt-toolkit integration in cmd2 uses a DynamicStyle wrapper around a
   callable that returns the current prompt-toolkit theme.

To prevent Rich's built-in styles (like 'bold', or 'italic') from
polluting the prompt-toolkit namespace or colliding with its own internal
names, only styles starting with registered prefixes (e.g., 'cmd2.') or
those explicitly mapped to UI elements are synchronized to the
prompt-toolkit theme.
"""

from collections.abc import Mapping
from typing import cast

from prompt_toolkit.styles import Style as PtStyle
from rich.style import StyleType
from rich.theme import Theme

from .pt_utils import rich_to_pt_style
from .rich_utils import Cmd2HelpFormatter
from .styles import (
    DEFAULT_ARGPARSE_STYLES,
    DEFAULT_CMD2_STYLES,
    Cmd2Style,
)

# The application-wide theme, defined using Rich's styling system.
# Use get_theme() to access it and set_theme() to modify it.
_THEME: Theme | None = None

# The prompt-toolkit version of the theme, synchronized from the Rich theme.
# Use get_pt_theme() to access it. This object is automatically updated whenever
# set_theme() is called.
_PT_THEME: PtStyle | None = None

# Maps style names to internal UI component names used by prompt-toolkit.
# This allows developers to use application-specific style names in set_theme()
# while ensuring the underlying prompt-toolkit UI is styled correctly.
# Use register_pt_mapping() to modify it.
_PT_UI_MAP: dict[str, list[str]] = {
    Cmd2Style.COMPLETION_MENU: ["completion-menu"],
    Cmd2Style.COMPLETION_MENU_COMPLETION: ["completion-menu.completion"],
    Cmd2Style.COMPLETION_MENU_CURRENT: ["completion-menu.completion.current"],
    Cmd2Style.COMPLETION_MENU_META: ["completion-menu.meta.completion"],
    Cmd2Style.COMPLETION_MENU_META_CURRENT: [
        "completion-menu.meta.completion.current",
        "completion-menu.multi-column-meta",
    ],
}

# Only Rich styles starting with one of these prefixes are synchronized to
# the prompt-toolkit theme. Use register_synchronized_prefix() to modify it.
_SYNCHRONIZED_PREFIXES: set[str] = {"cmd2."}


def get_theme() -> Theme:
    """Get the application-wide Rich theme. Initializes it on the first call."""
    if _THEME is None:
        set_theme()
    return cast(Theme, _THEME)


def get_pt_theme() -> PtStyle:
    """Get the application-wide prompt-toolkit style. Initializes it on the first call."""
    if _PT_THEME is None:
        set_theme()
    return cast(PtStyle, _PT_THEME)


def set_theme(styles: Mapping[str, StyleType] | None = None) -> None:
    """Set the application-wide theme.

    This function performs an in-place update of the existing Rich theme's
    styles. This ensures that any Console objects already using the theme
    will reflect the changes immediately without needing to be recreated.

    It also automatically synchronizes the prompt-toolkit theme for any
    styles with registered prefixes or mapped UI components.

    Call set_theme() with no arguments to reset to the default theme.
    This will clear any custom styles that were previously applied.

    :param styles: optional mapping of style names to styles
    """
    global _THEME  # noqa: PLW0603
    if _THEME is None:
        _THEME = Theme()

    # Start with a fresh copy of the default styles.
    unparsed_styles: dict[str, StyleType] = {}
    unparsed_styles.update(_create_default_theme().styles)

    # Add the custom styles, which may contain unparsed strings
    if styles is not None:
        unparsed_styles.update(styles)

    # Use Rich's Theme class to perform the parsing
    parsed_styles = Theme(unparsed_styles).styles

    # Perform the in-place update with the results
    _THEME.styles.clear()
    _THEME.styles.update(parsed_styles)

    # Synchronize rich-argparse styles with the main application theme.
    for name in Cmd2HelpFormatter.styles.keys() & _THEME.styles.keys():
        Cmd2HelpFormatter.styles[name] = _THEME.styles[name]

    # Synchronize the prompt-toolkit theme
    _sync_pt_theme()


def _sync_pt_theme() -> None:
    """Build a new global PT style object based on the current Rich theme."""
    theme = get_theme()
    style_rules: list[tuple[str, str]] = []

    for name, rich_style in theme.styles.items():
        # Only synchronize if it has a registered prefix or mapped UI component.
        is_framework_style = any(name.startswith(p) for p in _SYNCHRONIZED_PREFIXES)
        is_mapped_style = name in _PT_UI_MAP

        if is_framework_style or is_mapped_style:
            pt_style_str = rich_to_pt_style(rich_style)

            # Register the style name as a prompt-toolkit class (accessible via 'class:name')
            style_rules.append((name, pt_style_str))

            # Add any prompt-toolkit UI component aliases from the map (e.g., 'completion-menu')
            if is_mapped_style:
                style_rules.extend((pt_name, pt_style_str) for pt_name in _PT_UI_MAP[name])

    global _PT_THEME  # noqa: PLW0603
    _PT_THEME = PtStyle(style_rules)


def _create_default_theme() -> Theme:
    """Create a default theme for the application.

    This theme combines the default styles from cmd2, rich-argparse, and Rich.
    """
    app_styles = DEFAULT_CMD2_STYLES.copy()
    app_styles.update(DEFAULT_ARGPARSE_STYLES)
    return Theme(app_styles, inherit=True)


def register_pt_mapping(style_name: str, pt_ui_names: str | list[str]) -> None:
    """Map a Rich theme style name to one or more prompt-toolkit UI components.

    This enables styling of prompt-toolkit's internal elements (such as the
    completion menu ) using styles in the application's Rich theme.

    :param style_name: The style name used in the Rich theme.
    :param pt_ui_names: One or more prompt-toolkit UI component names (e.g., 'completion-menu').
    """
    if isinstance(pt_ui_names, str):
        pt_ui_names = [pt_ui_names]

    # Filter out UI names identical to the style name to avoid redundant registration.
    unique_names = [n for n in pt_ui_names if n != style_name]
    _PT_UI_MAP[style_name] = unique_names

    # Trigger a re-sync if the theme is already initialized
    if _PT_THEME is not None:
        _sync_pt_theme()


def register_synchronized_prefix(prefix: str) -> None:
    """Register a prefix whose styles will be synchronized to the prompt-toolkit theme.

    The prefix must include any desired delimiters (e.g., 'myapp.' or 'plugin-').

    :param prefix: The prefix string. Must be at least 1 character.
    :raises ValueError: If the prefix is empty.
    """
    if not prefix:
        raise ValueError("Prefix cannot be empty.")

    _SYNCHRONIZED_PREFIXES.add(prefix)

    # Trigger a re-sync if the theme is already initialized
    if _PT_THEME is not None:
        _sync_pt_theme()
