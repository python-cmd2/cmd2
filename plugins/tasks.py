#
# coding=utf-8
# flake8: noqa E302
"""Development related tasks to be run with 'invoke'.

Make sure you satisfy the following Python module requirements if you are trying to publish a release to PyPI:
    - twine >= 1.11.0
    - wheel >= 0.31.0
    - setuptools >= 39.1.0
"""
import invoke

from plugins.ext_test import tasks as ext_test_tasks
from plugins.template import tasks as template_tasks

# create namespaces
namespace = invoke.Collection(ext_test=ext_test_tasks,
                              template=template_tasks,
                              )
namespace_clean = invoke.Collection('clean')
namespace.add_collection(namespace_clean, 'clean')

#####
#
# pytest, pylint, and codecov
#
#####


@invoke.task(pre=[ext_test_tasks.pytest])
@invoke.task()
def pytest(_):
    """Run tests and code coverage using pytest"""
    pass


namespace.add_task(pytest)


@invoke.task(pre=[ext_test_tasks.pytest_clean])
def pytest_clean(_):
    """Remove pytest cache and code coverage files and directories"""
    pass


namespace_clean.add_task(pytest_clean, 'pytest')


@invoke.task(pre=[ext_test_tasks.mypy])
def mypy(_):
    """Run mypy optional static type checker"""
    pass


namespace.add_task(mypy)


@invoke.task(pre=[ext_test_tasks.mypy_clean])
def mypy_clean(_):
    """Remove mypy cache directory"""
    # pylint: disable=unused-argument
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
    pass


namespace_clean.add_task(build_clean, 'build')


@invoke.task(pre=[ext_test_tasks.dist_clean])
def dist_clean(_):
    """Remove the dist directory"""
    pass


namespace_clean.add_task(dist_clean, 'dist')


# make a dummy clean task which runs all the tasks in the clean namespace
clean_tasks = list(namespace_clean.tasks.values())


@invoke.task(pre=list(namespace_clean.tasks.values()), default=True)
def clean_all(_):
    """Run all clean tasks"""
    # pylint: disable=unused-argument
    pass


namespace_clean.add_task(clean_all, 'all')


@invoke.task(pre=[clean_all], post=[ext_test_tasks.sdist])
def sdist(_):
    """Create a source distribution"""
    pass


namespace.add_task(sdist)


@invoke.task(pre=[clean_all], post=[ext_test_tasks.wheel])
def wheel(_):
    """Build a wheel distribution"""
    pass


namespace.add_task(wheel)


# Flake8 - linter and tool for style guide enforcement and linting
@invoke.task(pre=[ext_test_tasks.flake8])
def flake8(_):
    """Run flake8 linter and tool for style guide enforcement"""
    pass


namespace.add_task(flake8)
