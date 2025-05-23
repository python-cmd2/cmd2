#
# coding=utf-8
"""Classes for the cmd2 plugin system"""

from dataclasses import (
    dataclass,
)
from typing import (
    Optional,
)

from .parsing import (
    Statement,
)


@dataclass
class PostparsingData:
    """Data class containing information passed to postparsing hook methods"""

    stop: bool
    statement: Statement


@dataclass
class PrecommandData:
    """Data class containing information passed to precommand hook methods"""

    statement: Statement


@dataclass
class PostcommandData:
    """Data class containing information passed to postcommand hook methods"""

    stop: bool
    statement: Statement


@dataclass
class CommandFinalizationData:
    """Data class containing information passed to command finalization hook methods"""

    stop: bool
    statement: Optional[Statement]
