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
            print("Removing {}".format(item))
        shutil.rmtree(item, ignore_errors=True)
        # rmtree doesn't remove bare files
        try:
            os.remove(item)
        except FileNotFoundError:
            pass


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
    ROOT_PATH = TASK_ROOT.parent.parent

    with context.cd(str(ROOT_PATH)):
        command_str = 'pytest --cov=cmd2_ext_test --cov-report=term --cov-report=html'
        if append_cov:
            command_str += ' --cov-append'
        if junit:
            command_str += ' --junitxml=junit/test-results.xml'
        command_str += ' ' + str((TASK_ROOT/'tests').relative_to(ROOT_PATH))
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
        context.run("mypy cmd2_ext_test")
        namespace.add_task(mypy)


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
    pass


namespace_clean.add_task(clean_all, 'all')


@invoke.task(pre=[clean_all])
def sdist(context):
    """Create a source distribution"""
    with context.cd(TASK_ROOT_STR):
        context.run('python setup.py sdist')


namespace.add_task(sdist)


@invoke.task(pre=[clean_all])
def wheel(context):
    """Build a wheel distribution"""
    with context.cd(TASK_ROOT_STR):
        context.run('python setup.py bdist_wheel')


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


# Flake8 - linter and tool for style guide enforcement and linting
@invoke.task
def flake8(context):
    """Run flake8 linter and tool for style guide enforcement"""
    with context.cd(TASK_ROOT_STR):
        context.run("flake8 --ignore=E252,W503 --max-complexity=26 --max-line-length=127 --show-source --statistics "
                    "--exclude=.git,__pycache__,.tox,.nox,.eggs,*.egg,.venv,.idea,.pytest_cache,.vscode,build,dist,htmlcov")


namespace.add_task(flake8)
