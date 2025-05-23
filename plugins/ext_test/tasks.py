"""Development related tasks to be run with 'invoke'.

Make sure you satisfy the following Python module requirements if you are trying to publish a release to PyPI:
    - twine >= 1.11.0
    - wheel >= 0.31.0
    - setuptools >= 39.1.0
"""

import contextlib
import os
import pathlib
import shutil

import invoke

TASK_ROOT = pathlib.Path(__file__).resolve().parent
TASK_ROOT_STR = str(TASK_ROOT)


# shared function
def rmrf(items, verbose=True):
    """Silently remove a list of directories or files"""
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
namespace = invoke.Collection()
namespace_clean = invoke.Collection('clean')
namespace.add_collection(namespace_clean, 'clean')

#####
#
# pytest, pylint, and codecov
#
#####


@invoke.task
def pytest(context, junit=False, pty=True, append_cov=False):
    """Run tests and code coverage using pytest"""
    root_path = TASK_ROOT.parent.parent

    with context.cd(str(root_path)):
        command_str = 'pytest --cov=cmd2_ext_test --cov-report=term --cov-report=html'
        if append_cov:
            command_str += ' --cov-append'
        if junit:
            command_str += ' --junitxml=junit/test-results.xml'
        command_str += ' ' + str((TASK_ROOT / 'tests').relative_to(root_path))
        context.run(command_str, pty=pty)


namespace.add_task(pytest)


@invoke.task
def pytest_clean(context):
    """Remove pytest cache and code coverage files and directories"""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        dirs = ['.pytest_cache', '.cache', 'htmlcov', '.coverage']
        rmrf(dirs)


namespace_clean.add_task(pytest_clean, 'pytest')


@invoke.task
def mypy(context):
    """Run mypy optional static type checker"""
    with context.cd(TASK_ROOT_STR):
        context.run("mypy .")


namespace.add_task(mypy)


@invoke.task
def mypy_clean(context):
    """Remove mypy cache directory"""
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


#####
#
# build and distribute
#
#####
BUILDDIR = 'build'
DISTDIR = 'dist'


@invoke.task
def build_clean(context):
    """Remove the build directory"""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        rmrf(BUILDDIR)


namespace_clean.add_task(build_clean, 'build')


@invoke.task
def dist_clean(context):
    """Remove the dist directory"""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        rmrf(DISTDIR)


namespace_clean.add_task(dist_clean, 'dist')


#
# make a dummy clean task which runs all the tasks in the clean namespace
clean_tasks = list(namespace_clean.tasks.values())


@invoke.task(pre=list(namespace_clean.tasks.values()), default=True)
def clean_all(context):
    """Run all clean tasks"""
    # pylint: disable=unused-argument


namespace_clean.add_task(clean_all, 'all')


@invoke.task(pre=[clean_all])
def sdist(context):
    """Create a source distribution"""
    with context.cd(TASK_ROOT_STR):
        context.run('python -m build --sdist')


namespace.add_task(sdist)


@invoke.task(pre=[clean_all])
def wheel(context):
    """Build a wheel distribution"""
    with context.cd(TASK_ROOT_STR):
        context.run('python -m build --wheel')


namespace.add_task(wheel)


@invoke.task(pre=[sdist, wheel])
def pypi(context):
    """Build and upload a distribution to pypi"""
    with context.cd(TASK_ROOT_STR):
        context.run('twine upload dist/*')


namespace.add_task(pypi)


@invoke.task(pre=[sdist, wheel])
def pypi_test(context):
    """Build and upload a distribution to https://test.pypi.org"""
    with context.cd(TASK_ROOT_STR):
        context.run('twine upload --repository-url https://test.pypi.org/legacy/ dist/*')


namespace.add_task(pypi_test)


# ruff fast linter
@invoke.task
def lint(context):
    """Run ruff fast linter"""
    with context.cd(TASK_ROOT_STR):
        context.run("ruff check")


namespace.add_task(lint)


@invoke.task
def format(context):  # noqa: A001
    """Run ruff format --check"""
    with context.cd(TASK_ROOT_STR):
        context.run("ruff format --check")


namespace.add_task(format)
