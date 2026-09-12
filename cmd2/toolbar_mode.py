"""Choose whether and how to render the bottom toolbar.

The toolbar is disabled by default. Enabled toolbars can use legacy rendering or experimental
reserved rendering, qualified terminal by terminal. The set of qualified combinations decides
whether ``auto`` selects reserved rendering.

Reserved rendering depends on things cmd2 does not control: which output backend
prompt-toolkit selected, which version of prompt-toolkit is installed, whether there is a
terminal at all. This module is the one place those prerequisites are decided, before
anything binds a bridge or writes a margin sequence.

The two modes that can reserve rows answer the same question differently, on purpose:

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

from enum import StrEnum
from importlib.metadata import version as _installed_version
from typing import TYPE_CHECKING

from .terminal_display import PhysicalTerminal

if TYPE_CHECKING:  # pragma: no cover
    from prompt_toolkit.output import Output

#: prompt-toolkit versions the reserved-row mechanism has been qualified against. The bridge
#: reaches into renderer internals whose shape is not part of any public API, so this is an
#: exact set rather than a floor.
QUALIFIED_PROMPT_TOOLKIT_VERSIONS = frozenset({"3.0.53"})


class ToolbarMode(StrEnum):
    """How the bottom toolbar is rendered.

    A string enum rather than bare strings: this is the one place the set of modes is written
    down, and every comparison in the codebase is against a member rather than a spelling.
    Because the members *are* strings, ``bottom_toolbar_mode="reserved"`` keeps working and
    keeps comparing equal to :attr:`RESERVED`.
    """

    #: Disable the bottom toolbar (the default).
    OFF = "off"

    #: Use reserved rows where the terminal qualifies, and fall back silently where it does
    #: not. A backend that looks close enough is still a guess, and a wrong guess corrupts the
    #: screen the user is working in.
    AUTO = "auto"

    #: Require reserved rows, and refuse to start without them. A caller who asked for this
    #: and silently got legacy rendering has been given the behaviour they ruled out.
    RESERVED = "reserved"

    #: Redraw the toolbar with the prompt, as cmd2 always has.
    LEGACY = "legacy"


def _validate_toolbar_mode(mode: "ToolbarMode | str") -> ToolbarMode:
    """Check that a mode name is one cmd2 offers.

    :param mode: the requested mode, as a member or as its name
    :return: the corresponding member
    :raises ValueError: if the name is not a mode
    """
    try:
        return ToolbarMode(mode)
    except ValueError:
        offered = ", ".join(sorted(member.value for member in ToolbarMode))
        raise ValueError(f"{mode!r} is not a bottom toolbar mode; choose one of {offered}") from None


def _dependency_capability(version: str | None = None) -> tuple[bool, str]:
    """Decide whether the installed prompt-toolkit is one the reservation is qualified for.

    :param version: the version to judge; the installed one by default
    :return: whether it is qualified, and a reason suitable for diagnostics
    """
    installed = version if version is not None else _installed_version("prompt_toolkit")
    if installed in QUALIFIED_PROMPT_TOOLKIT_VERSIONS:
        return True, "qualified prompt-toolkit"
    qualified = ", ".join(sorted(QUALIFIED_PROMPT_TOOLKIT_VERSIONS))
    return False, f"prompt-toolkit {installed} is not qualified for reserved rendering (qualified: {qualified})"


def _select_toolbar_mode(
    mode: "ToolbarMode | str",
    output: "Output",
    *,
    toolbar_enabled: bool,
    interactive: bool,
    layout_supported: bool = True,
    version: str | None = None,
) -> tuple[ToolbarMode, str]:
    """Decide how the toolbar will be rendered for this session.

    :param mode: the requested mode, as a member or as its name
    :param output: the backend prompt-toolkit selected
    :param toolbar_enabled: whether a bottom toolbar is configured at all
    :param interactive: whether input and output are a terminal
    :param layout_supported: whether the session's layout has a toolbar window that reserved
        rendering can recognize and hide
    :param version: the prompt-toolkit version to judge; the installed one by default
    :return: the selected mode (``off``, ``legacy``, or ``reserved``) and, when
        falling back from ``auto``, the reason
    :raises ValueError: if the mode is not a mode, or if ``reserved`` was required and a
        prerequisite is missing
    """
    requested = _validate_toolbar_mode(mode)
    if requested in (ToolbarMode.OFF, ToolbarMode.LEGACY):
        return requested, ""

    reason = _unmet_prerequisite(
        output,
        toolbar_enabled=toolbar_enabled,
        interactive=interactive,
        layout_supported=layout_supported,
        version=version,
    )
    if reason is None:
        return ToolbarMode.RESERVED, ""
    if requested is ToolbarMode.RESERVED:
        raise ValueError(f"reserved bottom toolbar mode is not available here: {reason}")
    return ToolbarMode.LEGACY, reason


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
    supported, reason = _dependency_capability(version)
    if not supported:
        return reason
    supported, reason = PhysicalTerminal(output).capability()
    if not supported:
        return reason
    return None
