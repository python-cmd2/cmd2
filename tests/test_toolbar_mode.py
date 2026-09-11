"""Tests for choosing between reserved and legacy toolbar rendering.

Selection is deliberately conservative and deliberately loud. ``auto`` falls back to legacy
rendering for anything it has not qualified, because a wrong guess corrupts the user's screen
rather than merely rendering poorly; ``reserved`` refuses to start rather than silently giving
the caller the legacy behaviour they asked it not to use.
"""

import io

import pytest
from prompt_toolkit.data_structures import Size
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.output.vt100 import Vt100_Output

import cmd2
from cmd2.toolbar_mode import (
    QUALIFIED_PROMPT_TOOLKIT_VERSIONS,
    ToolbarMode,
    _dependency_capability,
    _select_toolbar_mode,
    _validate_toolbar_mode,
)


def qualified_output() -> Vt100_Output:
    """Build a backend the reservation is qualified for."""
    return Vt100_Output(io.StringIO(), lambda: Size(rows=24, columns=80))


class TestValidation:
    @pytest.mark.parametrize("mode", list(ToolbarMode))
    def test_every_mode_is_accepted(self, mode: ToolbarMode) -> None:
        assert _validate_toolbar_mode(mode) is mode

    @pytest.mark.parametrize("mode", [member.value for member in ToolbarMode])
    def test_the_plain_string_is_accepted_too(self, mode: str) -> None:
        """The members are strings, so a caller who writes one gets the member back."""
        assert _validate_toolbar_mode(mode) is ToolbarMode(mode)

    def test_an_unknown_mode_names_the_ones_that_exist(self) -> None:
        with pytest.raises(ValueError, match=r"auto.*legacy.*reserved"):
            _validate_toolbar_mode("pinned")

    def test_the_modes_are_the_three_the_design_names(self) -> None:
        assert {member.value for member in ToolbarMode} == {"auto", "reserved", "legacy"}

    def test_a_mode_is_its_own_string(self) -> None:
        """Nothing that compared these to strings before has to change."""
        assert ToolbarMode.RESERVED == "reserved"


class TestDependencyQualification:
    def test_the_installed_prompt_toolkit_is_the_qualified_one(self) -> None:
        """A dependency upgrade must fail here rather than quietly rendering differently."""
        supported, reason = _dependency_capability()
        assert supported is True, reason

    def test_only_exactly_qualified_versions_count(self) -> None:
        """The package requirement stays a range; qualification does not follow it."""
        assert frozenset({"3.0.53"}) == QUALIFIED_PROMPT_TOOLKIT_VERSIONS

    def test_an_unqualified_version_is_reported_with_its_number(self) -> None:
        supported, reason = _dependency_capability("3.0.99")
        assert supported is False
        assert "3.0.99" in reason


class TestAutomaticSelection:
    def test_a_qualified_terminal_selects_reserved(self) -> None:
        mode, reason = _select_toolbar_mode("auto", qualified_output(), toolbar_enabled=True, interactive=True)
        assert mode is ToolbarMode.RESERVED
        assert reason == ""

    def test_an_unqualified_backend_falls_back(self) -> None:
        mode, reason = _select_toolbar_mode("auto", DummyOutput(), toolbar_enabled=True, interactive=True)
        assert mode is ToolbarMode.LEGACY
        assert "dummy output" in reason

    def test_an_unqualified_dependency_falls_back(self) -> None:
        mode, reason = _select_toolbar_mode(
            "auto", qualified_output(), toolbar_enabled=True, interactive=True, version="3.0.99"
        )
        assert mode is ToolbarMode.LEGACY
        assert "3.0.99" in reason

    def test_a_disabled_toolbar_falls_back(self) -> None:
        """With no toolbar there is nothing to reserve a row for."""
        mode, reason = _select_toolbar_mode("auto", qualified_output(), toolbar_enabled=False, interactive=True)
        assert mode is ToolbarMode.LEGACY
        assert "toolbar" in reason

    def test_a_non_interactive_session_falls_back(self) -> None:
        """Redirected output has no terminal to reserve rows in."""
        mode, reason = _select_toolbar_mode("auto", qualified_output(), toolbar_enabled=True, interactive=False)
        assert mode is ToolbarMode.LEGACY
        assert "interactive" in reason


class TestForcedModes:
    def test_legacy_is_selected_whatever_the_terminal_supports(self) -> None:
        mode, reason = _select_toolbar_mode("legacy", qualified_output(), toolbar_enabled=True, interactive=True)
        assert mode is ToolbarMode.LEGACY
        assert reason == ""

    def test_reserved_is_selected_when_everything_qualifies(self) -> None:
        mode, _reason = _select_toolbar_mode("reserved", qualified_output(), toolbar_enabled=True, interactive=True)
        assert mode is ToolbarMode.RESERVED

    def test_forcing_reserved_on_an_unqualified_backend_is_an_error(self) -> None:
        """Falling back silently would give the caller the behaviour they ruled out."""
        with pytest.raises(ValueError, match="dummy output"):
            _select_toolbar_mode("reserved", DummyOutput(), toolbar_enabled=True, interactive=True)

    def test_forcing_reserved_on_an_unqualified_dependency_is_an_error(self) -> None:
        with pytest.raises(ValueError, match=r"3\.0\.99"):
            _select_toolbar_mode("reserved", qualified_output(), toolbar_enabled=True, interactive=True, version="3.0.99")

    def test_forcing_reserved_without_a_toolbar_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="toolbar"):
            _select_toolbar_mode("reserved", qualified_output(), toolbar_enabled=False, interactive=True)

    def test_forcing_reserved_without_a_terminal_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="interactive"):
            _select_toolbar_mode("reserved", qualified_output(), toolbar_enabled=True, interactive=False)

    def test_an_unknown_mode_is_rejected_before_anything_is_inspected(self) -> None:
        with pytest.raises(ValueError, match="pinned"):
            _select_toolbar_mode("pinned", qualified_output(), toolbar_enabled=True, interactive=True)


class TestConstructorWiring:
    def test_the_default_is_legacy(self) -> None:
        """Reserved rendering is opt-in until it has been through the release gates."""
        assert cmd2.Cmd(allow_cli_args=False).bottom_toolbar_mode is ToolbarMode.LEGACY

    @pytest.mark.parametrize("mode", list(ToolbarMode))
    def test_a_requested_mode_is_remembered(self, mode: ToolbarMode) -> None:
        app = cmd2.Cmd(allow_cli_args=False, enable_bottom_toolbar=True, bottom_toolbar_mode=mode)
        assert app.bottom_toolbar_mode is mode

    def test_a_mode_given_as_a_string_is_remembered_as_the_member(self) -> None:
        """Existing calls pass strings; they get the same behaviour and a real member back."""
        app = cmd2.Cmd(allow_cli_args=False, enable_bottom_toolbar=True, bottom_toolbar_mode="reserved")
        assert app.bottom_toolbar_mode is ToolbarMode.RESERVED

    def test_the_enum_is_importable_from_the_package(self) -> None:
        assert cmd2.ToolbarMode is ToolbarMode

    def test_an_unknown_mode_is_rejected_at_construction(self) -> None:
        """Not at the first prompt: a typo should fail where it was written."""
        with pytest.raises(ValueError, match="pinned"):
            cmd2.Cmd(allow_cli_args=False, bottom_toolbar_mode="pinned")

    def test_the_mode_is_read_only(self) -> None:
        app = cmd2.Cmd(allow_cli_args=False)
        with pytest.raises(AttributeError):
            app.bottom_toolbar_mode = "reserved"  # type: ignore[misc]


class TestLayoutPrerequisite:
    def test_an_unrecognized_layout_falls_back_under_auto(self) -> None:
        """Reserved rendering has to hide the native toolbar, and cannot find it here."""
        mode, reason = _select_toolbar_mode(
            "auto", qualified_output(), toolbar_enabled=True, interactive=True, layout_supported=False
        )
        assert mode is ToolbarMode.LEGACY
        assert "layout" in reason

    def test_forcing_reserved_on_an_unrecognized_layout_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="layout"):
            _select_toolbar_mode(
                "reserved", qualified_output(), toolbar_enabled=True, interactive=True, layout_supported=False
            )
