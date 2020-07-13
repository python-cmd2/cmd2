#
# coding=utf-8
"""Description of myplugin

An overview of what myplugin does.
"""

from pkg_resources import get_distribution, DistributionNotFound

from .myplugin import empty_decorator, MyPluginMixin  # noqa: F401

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    __version__ = 'unknown'
