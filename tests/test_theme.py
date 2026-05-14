"""Unit testing for cmd2/theme.py module"""

from typing import Any

import pytest
from rich.style import Style

from cmd2 import (
    Cmd2Style,
    Color,
)
from cmd2 import rich_utils as ru
from cmd2.rich_utils import Cmd2HelpFormatter
from cmd2.theme import (
    get_pt_theme,
    get_theme,
    register_pt_mapping,
    register_synchronized_prefix,
    register_synchronized_style,
    reset_theme,
    unregister_pt_mapping,
    unregister_synchronized_prefix,
    unregister_synchronized_style,
    update_theme,
)


def test_reset_theme() -> None:
    # Save values for the initial theme
    orig_cmd2_styles = dict(get_theme().styles)
    orig_rich_argparse_styles = Cmd2HelpFormatter.styles.copy()
    orig_pt_styles = get_pt_theme().style_rules

    # Overwrite values for a cmd2, rich-argparse, rich-specific style,
    # and one that maps to a prompt-toolkit UI element.
    cmd2_style_key = Cmd2Style.ERROR
    argparse_style_key = "argparse.args"
    rich_style_key = "inspect.attr"
    pt_mapped_key = Cmd2Style.COMPLETION_MENU

    new_styles = {
        cmd2_style_key: Style(color=Color.CYAN),
        argparse_style_key: Style(color=Color.AQUAMARINE3, underline=True),
        rich_style_key: Style(color=Color.DARK_GOLDENROD, bold=True),
        pt_mapped_key: Style(color=Color.BLUE),
    }
    update_theme(new_styles)

    # Verify the theme has been updated
    assert orig_cmd2_styles != get_theme().styles
    assert orig_rich_argparse_styles != Cmd2HelpFormatter.styles
    assert orig_pt_styles != get_pt_theme().style_rules

    # Verify that we can reset all values
    reset_theme()

    assert orig_cmd2_styles == get_theme().styles
    assert orig_rich_argparse_styles == Cmd2HelpFormatter.styles
    assert orig_pt_styles == get_pt_theme().style_rules


def test_update_theme() -> None:
    # Update values for a cmd2, rich-argparse, rich-specific style,
    # and one that maps to a prompt-toolkit UI element.
    cmd2_style_key = Cmd2Style.ERROR
    argparse_style_key = "argparse.args"
    rich_style_key = "inspect.attr"
    pt_mapped_key = Cmd2Style.COMPLETION_MENU

    theme = get_theme()
    pt_theme = get_pt_theme()

    # Save the originals
    orig_cmd2_style = theme.styles[cmd2_style_key]
    orig_argparse_style = theme.styles[argparse_style_key]
    orig_rich_argparse_style = ru.Cmd2HelpFormatter.styles[argparse_style_key]
    orig_rich_style = theme.styles[rich_style_key]
    orig_completion_menu = theme.styles[pt_mapped_key]
    orig_pt_completion_menu = pt_theme.get_attrs_for_style_str("class:completion-menu")

    # Overwrite these styles by setting a new theme.
    new_styles = {
        cmd2_style_key: Style(color=Color.CYAN),
        argparse_style_key: Style(color=Color.AQUAMARINE3, underline=True),
        rich_style_key: Style(color=Color.DARK_GOLDENROD, bold=True),
        pt_mapped_key: Style(color=Color.BLUE),
    }
    update_theme(new_styles)

    # Verify theme styles have changed to our custom values.
    assert theme.styles[cmd2_style_key] != orig_cmd2_style
    assert theme.styles[cmd2_style_key] == new_styles[cmd2_style_key]

    assert theme.styles[argparse_style_key] != orig_argparse_style
    assert theme.styles[argparse_style_key] == new_styles[argparse_style_key]
    assert ru.Cmd2HelpFormatter.styles[argparse_style_key] != orig_rich_argparse_style
    assert ru.Cmd2HelpFormatter.styles[argparse_style_key] == new_styles[argparse_style_key]

    assert theme.styles[rich_style_key] != orig_rich_style
    assert theme.styles[rich_style_key] == new_styles[rich_style_key]

    assert theme.styles[pt_mapped_key] != orig_completion_menu
    assert theme.styles[pt_mapped_key] == new_styles[pt_mapped_key]

    # Verify the prompt-toolkit theme was updated
    new_pt_theme = get_pt_theme()
    new_pt_completion_menu = new_pt_theme.get_attrs_for_style_str("class:completion-menu")
    assert orig_pt_completion_menu != new_pt_completion_menu

    for field, value in new_pt_completion_menu._asdict().items():
        if field == "color":
            expected: Any = "ansiblue"
        elif field == "bgcolor":
            expected = "default"
        else:
            expected = False

        assert expected == value

    # Verify incremental update by checking that a previously set custom style is preserved
    update_theme({"custom_style": "bold red"})
    update_theme({"another_style": "blue"})
    assert theme.styles["custom_style"] == Style(color=Color.RED, bold=True)
    assert theme.styles["another_style"] == Style(color="blue")


def test_theme_is_none() -> None:
    """Test that get_theme() creates the theme when it's None."""
    from cmd2 import theme

    theme._THEME = None

    assert get_theme() is not None


def test_pt_theme_is_none() -> None:
    """Test that get_pt_theme() creates the pt theme when it's None."""
    from cmd2 import theme

    theme._PT_THEME = None

    assert get_pt_theme() is not None


def test_register_pt_mapping() -> None:
    """Test style registration with UI mapping."""
    style_name = "my_custom_scrollbar"
    ui_name = "scrollbar"

    register_pt_mapping(style_name, ui_name)

    update_theme({style_name: Style(color=Color.BLUE)})

    pt_theme = get_pt_theme()

    # Check that both the main style name and the UI name are mapped
    attrs_main = pt_theme.get_attrs_for_style_str(f"class:{style_name}")
    attrs_ui = pt_theme.get_attrs_for_style_str(f"class:{ui_name}")

    assert attrs_main.color == "ansiblue"
    assert attrs_ui.color == "ansiblue"


def test_register_pt_mapping_redundant() -> None:
    """Test that redundant mappings are filtered out."""
    from cmd2 import theme

    style_name = "redundant"
    register_pt_mapping(style_name, [style_name, "other"])

    assert style_name not in theme._PT_UI_MAP[style_name]
    assert "other" in theme._PT_UI_MAP[style_name]


def test_register_pt_mapping_existing_style() -> None:
    """Test calling register_pt_mapping with an existing style name."""
    style_name = "existing_style"
    ui_name = "ui_component"

    # First registration
    register_pt_mapping(style_name, ui_name)

    # Second registration with the same name
    register_pt_mapping(style_name, ui_name)

    # Verify contents of _PT_UI_MAP
    from cmd2 import theme

    assert style_name in theme._PT_UI_MAP
    assert ui_name in theme._PT_UI_MAP[style_name]


def test_unregister_pt_mapping() -> None:
    """Test unregistering UI mappings from styles."""
    from prompt_toolkit.styles import DEFAULT_ATTRS

    style_name = "custom_scroll"
    ui_names = ["scroll1", "scroll2"]

    register_pt_mapping(style_name, ui_names)
    update_theme({style_name: Style(color=Color.RED)})

    pt_theme = get_pt_theme()
    assert pt_theme.get_attrs_for_style_str("class:scroll1").color == "ansired"
    assert pt_theme.get_attrs_for_style_str("class:scroll2").color == "ansired"

    # Unregister one UI component
    unregister_pt_mapping(style_name, "scroll1")
    pt_theme = get_pt_theme()
    assert pt_theme.get_attrs_for_style_str("class:scroll1") == DEFAULT_ATTRS
    assert pt_theme.get_attrs_for_style_str("class:scroll2").color == "ansired"

    # Unregister the other UI component
    unregister_pt_mapping(style_name, "scroll2")
    pt_theme = get_pt_theme()
    assert pt_theme.get_attrs_for_style_str("class:scroll2") == DEFAULT_ATTRS


def test_unregister_pt_mapping_nonexistent() -> None:
    """Test unregistering a style that doesn't exist."""
    unregister_pt_mapping("nonexistent_style", "some_ui")


def test_unregister_pt_mapping_preserves_key() -> None:
    """Test that unregistering UI components preserves the style key for synchronization."""
    style_name = "preserved_style"
    ui_name = "some_ui"
    register_pt_mapping(style_name, ui_name)

    from cmd2 import theme

    assert style_name in theme._PT_UI_MAP
    assert ui_name in theme._PT_UI_MAP[style_name]

    # Unregister just the UI component
    unregister_pt_mapping(style_name, ui_name)

    # The style key should still be in the map to trigger synchronization
    assert style_name in theme._PT_UI_MAP
    assert not theme._PT_UI_MAP[style_name]


def test_register_synchronized_style() -> None:
    """Test that simple registration (no UI mapping) synchronizes to PT."""
    style_name = "simple_style"
    register_synchronized_style(style_name)

    update_theme({style_name: Style(color=Color.RED)})

    # It should be available as a class:name
    pt_theme = get_pt_theme()
    attrs = pt_theme.get_attrs_for_style_str(f"class:{style_name}")
    assert attrs.color == "ansired"


def test_unregister_synchronized_style() -> None:
    """Test that unregistering removes the style entirely."""
    style_name = "removal_style"
    ui_name = "removal_ui"
    register_pt_mapping(style_name, ui_name)

    from cmd2 import theme

    assert style_name in theme._PT_UI_MAP
    unregister_synchronized_style(style_name)
    assert style_name not in theme._PT_UI_MAP


def test_register_synchronized_prefix() -> None:
    """Test registering a custom synchronized prefix."""
    from prompt_toolkit.styles import DEFAULT_ATTRS

    prefix = "myapp."
    style_name = f"{prefix}prompt"
    update_theme({style_name: Style(color=Color.GREEN)})

    # Initially the style is only in the Rich theme
    rich_theme = get_theme()
    orig_pt_theme = get_pt_theme()

    assert style_name in rich_theme.styles
    assert orig_pt_theme.get_attrs_for_style_str(f"class:{style_name}") == DEFAULT_ATTRS

    # Register the prefix and make sure the style has been synced to the pt theme
    register_synchronized_prefix(prefix)
    new_pt_theme = get_pt_theme()
    style_attrs = new_pt_theme.get_attrs_for_style_str(f"class:{style_name}")
    assert style_attrs.color == "ansigreen"


def test_register_synchronized_prefix_empty() -> None:
    """Test that an empty prefix raises a ValueError."""
    with pytest.raises(ValueError, match="Prefix cannot be empty"):
        register_synchronized_prefix("")


def test_unregister_synchronized_prefix() -> None:
    """Test unregistering a custom synchronized prefix."""
    from prompt_toolkit.styles import DEFAULT_ATTRS

    prefix = "unregister."
    style_name = f"{prefix}prompt"
    update_theme({style_name: Style(color=Color.GREEN)})

    # Register the prefix and make sure the style has been synced to the pt theme
    register_synchronized_prefix(prefix)
    pt_theme = get_pt_theme()
    assert pt_theme.get_attrs_for_style_str(f"class:{style_name}").color == "ansigreen"

    # Unregister the prefix and make sure the style is no longer synced
    unregister_synchronized_prefix(prefix)
    new_pt_theme = get_pt_theme()
    assert new_pt_theme.get_attrs_for_style_str(f"class:{style_name}") == DEFAULT_ATTRS


def test_unregister_synchronized_prefix_nonexistent() -> None:
    """Test unregistering a prefix that doesn't exist."""
    unregister_synchronized_prefix("nonexistent_prefix.")
