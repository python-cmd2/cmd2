#
# coding=utf-8
"""Description of myplugin

An overview of what myplugin does.
"""

from pkg_resources import DistributionNotFound, get_distribution

from .cmd2_ext_test import ExternalTestMixin

__all__ = [
    'ExternalTestMixin'
]


try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    __version__ = 'unknown'
