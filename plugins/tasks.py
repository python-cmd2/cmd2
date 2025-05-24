"""Development related tasks to be run with 'invoke'.

Make sure you satisfy the following Python module requirements if you are trying to publish a release to PyPI:
    - twine >= 1.11.0
    - wheel >= 0.31.0
    - setuptools >= 39.1.0
"""

import pathlib

import invoke

from plugins.ext_test import (
    tasks as ext_test_tasks,
)
from plugins.template import (
    tasks as template_tasks,
)

# create namespaces
namespace = invoke.Collection(
    ext_test=ext_test_tasks,
    template=template_tasks,
)
namespace_clean = invoke.Collection('clean')
namespace.add_collection(namespace_clean, 'clean')

#####
#
# pytest, pylint, and codecov
#
#####

TASK_ROOT = pathlib.Path(__file__).resolve().parent
TASK_ROOT_STR = str(TASK_ROOT)


@invoke.task(pre=[ext_test_tasks.pytest])
@invoke.task()
def pytest(_) -> None:
    """Run tests and code coverage using pytest."""


namespace.add_task(pytest)


@invoke.task(pre=[ext_test_tasks.pytest_clean])
def pytest_clean(_) -> None:
    """Remove pytest cache and code coverage files and directories."""


namespace_clean.add_task(pytest_clean, 'pytest')


@invoke.task(pre=[ext_test_tasks.mypy])
def mypy(_) -> None:
    """Run mypy optional static type checker."""


namespace.add_task(mypy)


@invoke.task(pre=[ext_test_tasks.mypy_clean])
def mypy_clean(_) -> None:
    """Remove mypy cache directory."""
    # pylint: disable=unused-argument


namespace_clean.add_task(mypy_clean, 'mypy')


#####
#
# build and distribute
#
#####
BUILDDIR = 'build'
DISTDIR = 'dist'


@invoke.task(pre=[ext_test_tasks.build_clean])
def build_clean(_) -> None:
    """Remove the build directory."""


namespace_clean.add_task(build_clean, 'build')


@invoke.task(pre=[ext_test_tasks.dist_clean])
def dist_clean(_) -> None:
    """Remove the dist directory."""


namespace_clean.add_task(dist_clean, 'dist')


# make a dummy clean task which runs all the tasks in the clean namespace
clean_tasks = list(namespace_clean.tasks.values())


@invoke.task(pre=list(namespace_clean.tasks.values()), default=True)
def clean_all(_) -> None:
    """Run all clean tasks."""
    # pylint: disable=unused-argument


namespace_clean.add_task(clean_all, 'all')


@invoke.task(pre=[clean_all], post=[ext_test_tasks.sdist])
def sdist(_) -> None:
    """Create a source distribution."""


namespace.add_task(sdist)


@invoke.task(pre=[clean_all], post=[ext_test_tasks.wheel])
def wheel(_) -> None:
    """Build a wheel distribution."""


namespace.add_task(wheel)


# ruff linter
@invoke.task(pre=[ext_test_tasks.lint])
def lint(context) -> None:
    with context.cd(TASK_ROOT_STR):
        context.run("ruff check")


namespace.add_task(lint)


# ruff formatter
@invoke.task(pre=[ext_test_tasks.format])
def format(context) -> None:  # noqa: A001
    """Run formatter."""
    with context.cd(TASK_ROOT_STR):
        context.run("ruff format --check")


namespace.add_task(format)
