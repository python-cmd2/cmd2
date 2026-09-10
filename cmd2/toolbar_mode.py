"""Choose between reserved-row and legacy toolbar rendering.

Reserved rendering depends on things cmd2 does not control: which output backend
prompt-toolkit selected, which version of prompt-toolkit is installed, whether there is a
terminal at all. This module is the one place those prerequisites are decided, before
anything binds a bridge or writes a margin sequence.

The two non-default modes answer the same question differently, on purpose:

``auto`` falls back to legacy rendering for anything it has not qualified. A backend that
looks close enough is still a guess, and a wrong guess here corrupts the screen the user is
working in rather than merely rendering poorly.

``reserved`` refuses to start instead of falling back. A caller who asked for reserved
rendering and silently got legacy rendering has been given the behaviour they ruled out, and
would find out from a flickering toolbar rather than from an error.

Qualification is by exact version, not by the package requirement. ``prompt-toolkit>=3.0.53``
is what cmd2 *installs against*; this set is what the reserved-row mechanism has actually been
tested against, and it grows only when a version has been through the qualification gates.
"""

from importlib.metadata import version as _installed_version
from typing import TYPE_CHECKING, Literal

from .terminal_display import PhysicalTerminal

if TYPE_CHECKING:  # pragma: no cover
    from prompt_toolkit.output import Output

#: The modes a caller may ask for.
TOOLBAR_MODES: tuple[str, ...] = ("auto", "reserved", "legacy")

#: prompt-toolkit versions the reserved-row mechanism has been qualified against. The bridge
#: reaches into renderer internals whose shape is not part of any public API, so this is an
#: exact set rather than a floor.
QUALIFIED_PROMPT_TOOLKIT_VERSIONS = frozenset({"3.0.53"})

ToolbarMode = Literal["auto", "reserved", "legacy"]


def validate_toolbar_mode(mode: str) -> str:
    """Check that a mode name is one cmd2 offers.

    :param mode: the requested mode
    :return: the mode, unchanged
    :raises ValueError: if the name is not a mode
    """
    if mode not in TOOLBAR_MODES:
        offered = ", ".join(sorted(TOOLBAR_MODES))
        raise ValueError(f"{mode!r} is not a bottom toolbar mode; choose one of {offered}")
    return mode


def dependency_capability(version: str | None = None) -> tuple[bool, str]:
    """Decide whether the installed prompt-toolkit is one the reservation is qualified for.

    :param version: the version to judge; the installed one by default
    :return: whether it is qualified, and a reason suitable for diagnostics
    """
    installed = version if version is not None else _installed_version("prompt_toolkit")
    if installed in QUALIFIED_PROMPT_TOOLKIT_VERSIONS:
        return True, "qualified prompt-toolkit"
    qualified = ", ".join(sorted(QUALIFIED_PROMPT_TOOLKIT_VERSIONS))
    return False, f"prompt-toolkit {installed} is not qualified for reserved rendering (qualified: {qualified})"


def select_toolbar_mode(
    mode: str,
    output: "Output",
    *,
    toolbar_enabled: bool,
    interactive: bool,
    layout_supported: bool = True,
    version: str | None = None,
) -> tuple[str, str]:
    """Decide how the toolbar will be rendered for this session.

    :param mode: the requested mode
    :param output: the backend prompt-toolkit selected
    :param toolbar_enabled: whether a bottom toolbar is configured at all
    :param interactive: whether input and output are a terminal
    :param layout_supported: whether the session's layout has a toolbar window that reserved
        rendering can recognize and hide
    :param version: the prompt-toolkit version to judge; the installed one by default
    :return: the mode to use -- always ``"reserved"`` or ``"legacy"`` -- and, when falling
        back from ``auto``, the reason it fell back
    :raises ValueError: if the mode is not a mode, or if ``reserved`` was required and a
        prerequisite is missing
    """
    validate_toolbar_mode(mode)
    if mode == "legacy":
        return "legacy", ""

    reason = _unmet_prerequisite(
        output,
        toolbar_enabled=toolbar_enabled,
        interactive=interactive,
        layout_supported=layout_supported,
        version=version,
    )
    if reason is None:
        return "reserved", ""
    if mode == "reserved":
        raise ValueError(f"reserved bottom toolbar mode is not available here: {reason}")
    return "legacy", reason


def _unmet_prerequisite(
    output: "Output",
    *,
    toolbar_enabled: bool,
    interactive: bool,
    layout_supported: bool,
    version: str | None,
) -> str | None:
    """Find the first prerequisite reserved rendering does not have.

    Ordered from the cheapest and most user-visible outwards, so the reported reason is the
    one a caller can act on: being told the backend is unqualified is unhelpful when the real
    problem is that no toolbar was configured.

    :param output: the backend prompt-toolkit selected
    :param toolbar_enabled: whether a bottom toolbar is configured at all
    :param interactive: whether input and output are a terminal
    :param layout_supported: whether the session's toolbar window can be located
    :param version: the prompt-toolkit version to judge; the installed one by default
    :return: the reason, or ``None`` when every prerequisite is met
    """
    if not toolbar_enabled:
        return "no bottom toolbar is configured"
    if not interactive:
        return "the session is not interactive"
    if not layout_supported:
        return "the session's layout has no bottom toolbar window to replace"
    supported, reason = dependency_capability(version)
    if not supported:
        return reason
    supported, reason = PhysicalTerminal(output).capability()
    if not supported:
        return reason
    return None
