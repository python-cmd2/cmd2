#
# coding=utf-8
# flake8: noqa E302
"""Development related tasks to be run with 'invoke'.

Make sure you satisfy the following Python module requirements if you are trying to publish a release to PyPI:
    - twine >= 1.11.0
    - wheel >= 0.31.0
    - setuptools >= 39.1.0
"""
import os
import re
import shutil
import sys

import invoke
from plugins.cmd2_ext_test import tasks as ext_test_tasks

# create namespaces
namespace = invoke.Collection()
namespace_clean = invoke.Collection('clean')
namespace.add_collection(namespace_clean, 'clean')

#####
#
# pytest, tox, pylint, and codecov
#
#####
@invoke.task(pre=[ext_test_tasks.pytest])
def pytest(_):
    """Run tests and code coverage using pytest"""
    pass


namespace.add_task(pytest)


@invoke.task(pre=[ext_test_tasks.pytest_junit])
def pytest_junit(_):
    """Run tests and code coverage using pytest"""
    pass


namespace.add_task(pytest_junit)


@invoke.task(pre=[ext_test_tasks.pytest_clean])
def pytest_clean(_):
    """Remove pytest cache and code coverage files and directories"""
    pass


namespace_clean.add_task(pytest_clean, 'pytest')


@invoke.task(pre=[ext_test_tasks.mypy])
def mypy(context):
    """Run mypy optional static type checker"""
    pass


namespace.add_task(mypy)

@invoke.task(pre=[ext_test_tasks.mypy_clean])
def mypy_clean(context):
    """Remove mypy cache directory"""
    #pylint: disable=unused-argument
    pass


namespace_clean.add_task(mypy_clean, 'mypy')


#####
#
# build and distribute
#
#####
BUILDDIR = 'build'
DISTDIR = 'dist'

@invoke.task(pre=[ext_test_tasks.build_clean])
def build_clean(_):
    """Remove the build directory"""


namespace_clean.add_task(build_clean, 'build')


@invoke.task(pre=[ext_test_tasks.dist_clean])
def dist_clean(_):
    """Remove the dist directory"""
    pass


namespace_clean.add_task(dist_clean, 'dist')


@invoke.task(pre=[ext_test_tasks.eggs_clean])
def eggs_clean(context):
    """Remove egg directories"""
    pass


namespace_clean.add_task(eggs_clean, 'eggs')


@invoke.task(pre=[ext_test_tasks.pycache_clean])
def pycache_clean(context):
    """Remove __pycache__ directories"""
    pass


namespace_clean.add_task(pycache_clean, 'pycache')


# make a dummy clean task which runs all the tasks in the clean namespace
clean_tasks = list(namespace_clean.tasks.values())


@invoke.task(pre=list(namespace_clean.tasks.values()), default=True)
def clean_all(context):
    """Run all clean tasks"""
    #pylint: disable=unused-argument
    pass


namespace_clean.add_task(clean_all, 'all')


@invoke.task(pre=[clean_all], post=[ext_test_tasks.sdist])
def sdist(context):
    "Create a source distribution"
    context.run('python setup.py sdist')


namespace.add_task(sdist)


@invoke.task(pre=[clean_all], post=[ext_test_tasks.wheel])
def wheel(context):
    "Build a wheel distribution"
    context.run('python setup.py bdist_wheel')
namespace.add_task(wheel)


@invoke.task(pre=[sdist, wheel])
def pypi(context):
    "Build and upload a distribution to pypi"
    context.run('twine upload dist/*')
namespace.add_task(pypi)


@invoke.task(pre=[sdist, wheel])
def pypi_test(context):
    "Build and upload a distribution to https://test.pypi.org"
    context.run('twine upload --repository-url https://test.pypi.org/legacy/ dist/*')
namespace.add_task(pypi_test)


# Flake8 - linter and tool for style guide enforcement and linting
@invoke.task(pre=[ext_test_tasks.flake8])
def flake8(context):
    "Run flake8 linter and tool for style guide enforcement"
    context.run("flake8 --ignore=E252,W503 --max-complexity=26 --max-line-length=127 --show-source --statistics --exclude=.git,__pycache__,.tox,.eggs,*.egg,.venv,.idea,.pytest_cache,.vscode,build,dist,htmlcov")
namespace.add_task(flake8)
