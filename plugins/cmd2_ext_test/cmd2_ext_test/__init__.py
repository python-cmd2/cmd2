#
# coding=utf-8
"""Description of myplugin

An overview of what myplugin does.
"""

from pkg_resources import get_distribution, DistributionNotFound

from .cmd2_ext_test import ExternalTestMixin

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    __version__ = 'unknown'
