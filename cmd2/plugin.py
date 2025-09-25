"""Classes for the cmd2 lifecycle hooks that you can register multiple callback functions/methods with."""

from dataclasses import (
    dataclass,
)

from .parsing import (
    Statement,
)


@dataclass
class PostparsingData:
    """Data class containing information passed to postparsing hook methods."""

    stop: bool
    statement: Statement


@dataclass
class PrecommandData:
    """Data class containing information passed to precommand hook methods."""

    statement: Statement


@dataclass
class PostcommandData:
    """Data class containing information passed to postcommand hook methods."""

    stop: bool
    statement: Statement


@dataclass
class CommandFinalizationData:
    """Data class containing information passed to command finalization hook methods."""

    stop: bool
    statement: Statement | None
