"""Development related tasks to be run with 'invoke'.

Make sure you satisfy the following Python module requirements if you are trying to publish a release to PyPI:
    - twine >= 1.11.0
    - wheel >= 0.31.0
    - setuptools >= 39.1.0
"""

import pathlib

import invoke

from plugins.template import (
    tasks as template_tasks,
)

# create namespaces
namespace = invoke.Collection(
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


@invoke.task()
def pytest(_) -> None:
    """Run tests and code coverage using pytest."""


namespace.add_task(pytest)


@invoke.task()
def pytest_clean(_) -> None:
    """Remove pytest cache and code coverage files and directories."""


namespace_clean.add_task(pytest_clean, 'pytest')


@invoke.task()
def mypy(_) -> None:
    """Run mypy optional static type checker."""


namespace.add_task(mypy)


@invoke.task()
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


@invoke.task()
def build_clean(_) -> None:
    """Remove the build directory."""


namespace_clean.add_task(build_clean, 'build')


@invoke.task()
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


@invoke.task(pre=[clean_all])
def sdist(_) -> None:
    """Create a source distribution."""


namespace.add_task(sdist)


@invoke.task(pre=[clean_all])
def wheel(_) -> None:
    """Build a wheel distribution."""


namespace.add_task(wheel)


# ruff linter
@invoke.task()
def lint(context) -> None:
    with context.cd(TASK_ROOT_STR):
        context.run("ruff check")


namespace.add_task(lint)


# ruff formatter
@invoke.task()
def format(context) -> None:  # noqa: A001
    """Run formatter."""
    with context.cd(TASK_ROOT_STR):
        context.run("ruff format --check")


namespace.add_task(format)
