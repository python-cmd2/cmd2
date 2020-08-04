#
# -*- coding: utf-8 -*-
"""Development related tasks to be run with 'invoke'"""

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
        command_str = 'pytest --cov=cmd2_myplugin --cov-report=term --cov-report=html'
        if append_cov:
            command_str += ' --cov-append'
        if junit:
            command_str += ' --junitxml=junit/test-results.xml'
        command_str += ' ' + str((TASK_ROOT / 'tests').relative_to(ROOT_PATH))
        context.run(command_str, pty=pty)


namespace.add_task(pytest)


@invoke.task
def pytest_clean(context):
    """Remove pytest cache and code coverage files and directories"""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        dirs = ['.pytest_cache', '.cache', '.coverage']
        rmrf(dirs)


namespace_clean.add_task(pytest_clean, 'pytest')


@invoke.task
def pylint(context):
    """Check code quality using pylint"""
    context.run('pylint --rcfile=cmd2_myplugin/pylintrc cmd2_myplugin')


namespace.add_task(pylint)


@invoke.task
def pylint_tests(context):
    """Check code quality of test suite using pylint"""
    context.run('pylint --rcfile=tests/pylintrc tests')


namespace.add_task(pylint_tests)


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
    rmrf(BUILDDIR)


namespace_clean.add_task(build_clean, 'build')


@invoke.task
def dist_clean(context):
    """Remove the dist directory"""
    # pylint: disable=unused-argument
    rmrf(DISTDIR)


namespace_clean.add_task(dist_clean, 'dist')


@invoke.task
def eggs_clean(context):
    """Remove egg directories"""
    # pylint: disable=unused-argument
    dirs = set()
    dirs.add('.eggs')
    for name in os.listdir(os.curdir):
        if name.endswith('.egg-info'):
            dirs.add(name)
        if name.endswith('.egg'):
            dirs.add(name)
    rmrf(dirs)


namespace_clean.add_task(eggs_clean, 'eggs')


@invoke.task
def bytecode_clean(context):
    """Remove __pycache__ directories and *.pyc files"""
    # pylint: disable=unused-argument
    dirs = set()
    for root, dirnames, files in os.walk(os.curdir):
        if '__pycache__' in dirnames:
            dirs.add(os.path.join(root, '__pycache__'))
        for file in files:
            if file.endswith(".pyc"):
                dirs.add(os.path.join(root, file))
    print("Removing __pycache__ directories and .pyc files")
    rmrf(dirs, verbose=False)


namespace_clean.add_task(bytecode_clean, 'bytecode')

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
    context.run('python setup.py sdist')


namespace.add_task(sdist)


@invoke.task(pre=[clean_all])
def wheel(context):
    """Build a wheel distribution"""
    context.run('python setup.py bdist_wheel')


namespace.add_task(wheel)

#
# these two tasks are commented out so you don't
# accidentally run them and upload this template to pypi
#

# @invoke.task(pre=[sdist, wheel])
# def pypi(context):
#     """Build and upload a distribution to pypi"""
#     context.run('twine upload dist/*')
# namespace.add_task(pypi)

# @invoke.task(pre=[sdist, wheel])
# def pypi_test(context):
#     """Build and upload a distribution to https://test.pypi.org"""
#     context.run('twine upload --repository-url https://test.pypi.org/legacy/ dist/*')
# namespace.add_task(pypi_test)
