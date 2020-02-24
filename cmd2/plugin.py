#
# coding=utf-8
"""Classes for the cmd2 plugin system"""
import attr


@attr.s
class PostparsingData:
    """Data class containing information passed to postparsing hook methods"""
    stop = attr.ib()
    statement = attr.ib()


@attr.s
class PrecommandData:
    """Data class containing information passed to precommand hook methods"""
    statement = attr.ib()


@attr.s
class PostcommandData:
    """Data class containing information passed to postcommand hook methods"""
    stop = attr.ib()
    statement = attr.ib()


@attr.s
class CommandFinalizationData:
    """Data class containing information passed to command finalization hook methods"""
    stop = attr.ib()
    statement = attr.ib()
