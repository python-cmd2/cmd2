#
# coding=utf-8
"""Classes for the cmd2 plugin system"""
import attr


@attr.s
class PostparsingData:
    stop = attr.ib()
    statement = attr.ib()


@attr.s
class PrecommandData:
    statement = attr.ib()


@attr.s
class PostcommandData:
    stop = attr.ib()
    statement = attr.ib()


@attr.s
class CommandFinalizationData:
    stop = attr.ib()
    statement = attr.ib()
