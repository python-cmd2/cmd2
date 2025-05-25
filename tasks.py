"""Development related tasks to be run with 'invoke'.

Make sure you satisfy the following Python module requirements if you are trying to publish a release to PyPI:
    - twine >= 1.11.0
    - wheel >= 0.31.0
    - setuptools >= 39.1.0
"""

import contextlib
import os
import pathlib
import re
import shutil
import sys
from typing import Union

import invoke
from invoke.context import Context

from plugins import (
    tasks as plugin_tasks,
)

TASK_ROOT = pathlib.Path(__file__).resolve().parent
TASK_ROOT_STR = str(TASK_ROOT)


# shared function
def rmrf(items: Union[str, list[str], set[str]], verbose: bool = True) -> None:
    """Silently remove a list of directories or files."""
    if isinstance(items, str):
        items = [items]

    for item in items:
        if verbose:
            print(f"Removing {item}")
        shutil.rmtree(item, ignore_errors=True)
        # rmtree doesn't remove bare files
        with contextlib.suppress(FileNotFoundError):
            os.remove(item)


# create namespaces
namespace = invoke.Collection(plugin=plugin_tasks)
namespace_clean = invoke.Collection('clean')
namespace.add_collection(namespace_clean, 'clean')

#####
#
# pytest, pylint, and codecov
#
#####


@invoke.task()
def pytest(context: Context, junit: bool = False, pty: bool = True, base: bool = False, isolated: bool = False) -> None:
    """Run tests and code coverage using pytest."""
    with context.cd(TASK_ROOT_STR):
        command_str = 'pytest '
        command_str += ' --cov=cmd2 '
        command_str += ' --cov-append --cov-report=term --cov-report=html '

        if not base and not isolated:
            base = True
            isolated = True

        if junit:
            command_str += ' --junitxml=junit/test-results.xml '

        if base:
            tests_cmd = command_str + ' tests'
            context.run(tests_cmd, pty=pty)
        if isolated:
            for _root, dirnames, _ in os.walk(str(TASK_ROOT / 'tests_isolated')):
                for dir_name in dirnames:
                    if dir_name.startswith('test_'):
                        context.run(command_str + ' tests_isolated/' + dir_name)


namespace.add_task(pytest)


@invoke.task(post=[plugin_tasks.pytest_clean])
def pytest_clean(context: Context) -> None:
    """Remove pytest cache and code coverage files and directories."""
    # pylint: disable=unused-argument
    with context.cd(str(TASK_ROOT / 'tests')):
        dirs = ['.pytest_cache', '.cache', 'htmlcov', '.coverage']
        rmrf(dirs)
    rmrf(dirs)


namespace_clean.add_task(pytest_clean, 'pytest')


@invoke.task()
def mypy(context: Context) -> None:
    """Run mypy optional static type checker."""
    with context.cd(TASK_ROOT_STR):
        context.run("mypy .")


namespace.add_task(mypy)


@invoke.task()
def mypy_clean(context: Context) -> None:
    """Remove mypy cache directory."""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        dirs = ['.mypy_cache', 'dmypy.json', 'dmypy.sock']
        rmrf(dirs)


namespace_clean.add_task(mypy_clean, 'mypy')


#####
#
# documentation
#
#####
DOCS_BUILDDIR = 'build'
MKDOCS_OPTS = '-nvWT'  # Be nitpicky, verbose, and treat warnings as errors


@invoke.task()
def docs(context: Context) -> None:
    """Build documentation using MkDocs."""
    with context.cd(TASK_ROOT_STR):
        context.run('mkdocs build', pty=True)


namespace.add_task(docs)


@invoke.task
def docs_clean(context: Context) -> None:
    """Remove rendered documentation."""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        rmrf(DOCS_BUILDDIR)


namespace_clean.add_task(docs_clean, name='docs')


@invoke.task
def livehtml(context: Context) -> None:
    """Launch webserver on http://localhost:8000 with rendered documentation."""
    with context.cd(TASK_ROOT_STR):
        context.run('mkdocs serve', pty=True)


namespace.add_task(livehtml)


#####
#
# build and distribute
#
#####
BUILDDIR = 'build'
DISTDIR = 'dist'


@invoke.task(post=[plugin_tasks.build_clean])
def build_clean(context: Context) -> None:
    """Remove the build directory."""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        rmrf(BUILDDIR)


namespace_clean.add_task(build_clean, 'build')


@invoke.task(post=[plugin_tasks.dist_clean])
def dist_clean(context: Context) -> None:
    """Remove the dist directory."""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        rmrf(DISTDIR)


namespace_clean.add_task(dist_clean, 'dist')


@invoke.task()
def eggs_clean(context: Context) -> None:
    """Remove egg directories."""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        dirs = set()
        dirs.add('.eggs')
        for name in os.listdir(os.curdir):
            if name.endswith('.egg-info'):
                dirs.add(name)
            if name.endswith('.egg'):
                dirs.add(name)
        rmrf(dirs)


namespace_clean.add_task(eggs_clean, 'eggs')


@invoke.task()
def pycache_clean(context: Context) -> None:
    """Remove __pycache__ directories."""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        dirs = set()
        for root, dirnames, _ in os.walk(os.curdir):
            if '__pycache__' in dirnames:
                dirs.add(os.path.join(root, '__pycache__'))
        print("Removing __pycache__ directories")
        rmrf(dirs, verbose=False)


namespace_clean.add_task(pycache_clean, 'pycache')


# ruff fast linter
@invoke.task()
def lint(context: Context) -> None:
    """Run ruff fast linter."""
    with context.cd(TASK_ROOT_STR):
        context.run("ruff check")


namespace.add_task(lint)


# ruff fast formatter
@invoke.task()
def format(context: Context) -> None:  # noqa: A001
    """Run ruff format --check."""
    with context.cd(TASK_ROOT_STR):
        context.run("ruff format --check")


namespace.add_task(format)


@invoke.task()
def ruff_clean(context: Context) -> None:
    """Remove .ruff_cache directory."""
    with context.cd(TASK_ROOT_STR):
        context.run("ruff clean")


namespace_clean.add_task(ruff_clean, 'ruff')

#
# make a dummy clean task which runs all the tasks in the clean namespace
clean_tasks = list(namespace_clean.tasks.values())
clean_tasks.append(plugin_tasks.clean_all)


@invoke.task(pre=clean_tasks, default=True)
def clean_all(_: Context) -> None:
    """Run all clean tasks."""
    # pylint: disable=unused-argument


namespace_clean.add_task(clean_all, 'all')


@invoke.task
def tag(context: Context, name: str, message: str = '') -> None:
    """Add a Git tag and push it to origin."""
    # If a tag was provided on the command-line, then add a Git tag and push it to origin
    if name:
        context.run(f'git tag -a {name} -m {message!r}')
        context.run(f'git push origin {name}')


namespace.add_task(tag)


@invoke.task()
def validatetag(context: Context) -> None:
    """Check to make sure that a tag exists for the current HEAD and it looks like a valid version number."""
    # Validate that a Git tag exists for the current commit HEAD
    result = context.run("git describe --exact-match --tags $(git log -n1 --pretty='%h')")
    git_tag = result.stdout.rstrip()

    # Validate that the Git tag appears to be a valid version number
    ver_regex = re.compile(r'(\d+)\.(\d+)\.(\d+)')
    match = ver_regex.fullmatch(git_tag)
    if match is None:
        print(f'Tag {git_tag!r} does not appear to be a valid version number')
        sys.exit(-1)
    else:
        print(f'Tag {git_tag!r} appears to be a valid version number')


namespace.add_task(validatetag)


@invoke.task(pre=[clean_all], post=[plugin_tasks.sdist])
def sdist(context: Context) -> None:
    """Create a source distribution."""
    with context.cd(TASK_ROOT_STR):
        context.run('python -m build --sdist')


namespace.add_task(sdist)


@invoke.task(pre=[clean_all], post=[plugin_tasks.wheel])
def wheel(context: Context) -> None:
    """Build a wheel distribution."""
    with context.cd(TASK_ROOT_STR):
        context.run('python -m build --wheel')


namespace.add_task(wheel)


@invoke.task(pre=[validatetag, sdist, wheel])
def pypi(context: Context) -> None:
    """Build and upload a distribution to pypi."""
    with context.cd(TASK_ROOT_STR):
        context.run('twine upload dist/*')


namespace.add_task(pypi)


@invoke.task(pre=[validatetag, sdist, wheel])
def pypi_test(context: Context) -> None:
    """Build and upload a distribution to https://test.pypi.org."""
    with context.cd(TASK_ROOT_STR):
        context.run('twine upload --repository testpypi dist/*')


namespace.add_task(pypi_test)
