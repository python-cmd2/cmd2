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
import re
import shutil
import sys

import invoke

from plugins import (
    tasks as plugin_tasks,
)

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
namespace = invoke.Collection(plugin=plugin_tasks)
namespace_clean = invoke.Collection('clean')
namespace.add_collection(namespace_clean, 'clean')

#####
#
# pytest, nox, pylint, and codecov
#
#####


@invoke.task()
def pytest(context, junit=False, pty=True, base=False, isolated=False):
    """Run tests and code coverage using pytest"""
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
            for root, dirnames, _ in os.walk(str(TASK_ROOT / 'tests_isolated')):
                for dir in dirnames:
                    if dir.startswith('test_'):
                        context.run(command_str + ' tests_isolated/' + dir)


namespace.add_task(pytest)


@invoke.task(post=[plugin_tasks.pytest_clean])
def pytest_clean(context):
    """Remove pytest cache and code coverage files and directories"""
    # pylint: disable=unused-argument
    with context.cd(str(TASK_ROOT / 'tests')):
        dirs = ['.pytest_cache', '.cache', 'htmlcov', '.coverage']
        rmrf(dirs)
    rmrf(dirs)


namespace_clean.add_task(pytest_clean, 'pytest')


@invoke.task(post=[plugin_tasks.mypy])
def mypy(context):
    """Run mypy optional static type checker"""
    with context.cd(TASK_ROOT_STR):
        context.run("mypy cmd2")


namespace.add_task(mypy)


@invoke.task(post=[plugin_tasks.mypy_clean])
def mypy_clean(context):
    """Remove mypy cache directory"""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        dirs = ['.mypy_cache', 'dmypy.json', 'dmypy.sock']
        rmrf(dirs)


namespace_clean.add_task(mypy_clean, 'mypy')


@invoke.task
def nox_clean(context):
    """Remove nox virtualenvs and logs"""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        rmrf('.nox')


namespace_clean.add_task(nox_clean, 'nox')


#####
#
# documentation
#
#####
DOCS_SRCDIR = 'docs'
DOCS_BUILDDIR = os.path.join('docs', '_build')
SPHINX_OPTS = '-nvWT'  # Be nitpicky, verbose, and treat warnings as errors


@invoke.task()
def docs(context, builder='html'):
    """Build documentation using sphinx"""
    with context.cd(TASK_ROOT_STR):
        cmdline = 'python -msphinx -M {} {} {} {}'.format(builder, DOCS_SRCDIR, DOCS_BUILDDIR, SPHINX_OPTS)
        context.run(cmdline, pty=True)


namespace.add_task(docs)


@invoke.task()
def doc8(context):
    """Check documentation with doc8"""
    with context.cd(TASK_ROOT_STR):
        context.run('doc8 docs --ignore-path docs/_build --ignore-path docs/.nox')


namespace.add_task(doc8)


@invoke.task
def docs_clean(context):
    """Remove rendered documentation"""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        rmrf(DOCS_BUILDDIR)


namespace_clean.add_task(docs_clean, name='docs')


@invoke.task()
def linkcheck(context):
    """Check external links in Sphinx documentation for integrity."""
    with context.cd(str(TASK_ROOT / 'docs')):
        context.run('make linkcheck', pty=True)


namespace.add_task(linkcheck)


@invoke.task
def livehtml(context):
    """Launch webserver on http://localhost:8000 with rendered documentation"""
    with context.cd(TASK_ROOT_STR):
        builder = 'html'
        outputdir = os.path.join(DOCS_BUILDDIR, builder)
        cmdline = 'sphinx-autobuild -b {} {} {}'.format(builder, DOCS_SRCDIR, outputdir)
        context.run(cmdline, pty=True)


namespace.add_task(livehtml)


#####
#
# build and distribute
#
#####
BUILDDIR = 'build'
DISTDIR = 'dist'


@invoke.task(post=[plugin_tasks.build_clean])
def build_clean(context):
    """Remove the build directory"""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        rmrf(BUILDDIR)


namespace_clean.add_task(build_clean, 'build')


@invoke.task(post=[plugin_tasks.dist_clean])
def dist_clean(context):
    """Remove the dist directory"""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        rmrf(DISTDIR)


namespace_clean.add_task(dist_clean, 'dist')


@invoke.task()
def eggs_clean(context):
    """Remove egg directories"""
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
def pycache_clean(context):
    """Remove __pycache__ directories"""
    # pylint: disable=unused-argument
    with context.cd(TASK_ROOT_STR):
        dirs = set()
        for root, dirnames, _ in os.walk(os.curdir):
            if '__pycache__' in dirnames:
                dirs.add(os.path.join(root, '__pycache__'))
        print("Removing __pycache__ directories")
        rmrf(dirs, verbose=False)


namespace_clean.add_task(pycache_clean, 'pycache')

#
# make a dummy clean task which runs all the tasks in the clean namespace
clean_tasks = list(namespace_clean.tasks.values())
clean_tasks.append(plugin_tasks.clean_all)


@invoke.task(pre=clean_tasks, default=True)
def clean_all(_):
    """Run all clean tasks"""
    # pylint: disable=unused-argument
    pass


namespace_clean.add_task(clean_all, 'all')


@invoke.task
def tag(context, name, message=''):
    """Add a Git tag and push it to origin"""
    # If a tag was provided on the command-line, then add a Git tag and push it to origin
    if name:
        context.run('git tag -a {} -m {!r}'.format(name, message))
        context.run('git push origin {}'.format(name))


namespace.add_task(tag)


@invoke.task()
def validatetag(context):
    """Check to make sure that a tag exists for the current HEAD and it looks like a valid version number"""
    # Validate that a Git tag exists for the current commit HEAD
    result = context.run("git describe --exact-match --tags $(git log -n1 --pretty='%h')")
    git_tag = result.stdout.rstrip()

    # Validate that the Git tag appears to be a valid version number
    ver_regex = re.compile(r'(\d+)\.(\d+)\.(\d+)')
    match = ver_regex.fullmatch(git_tag)
    if match is None:
        print('Tag {!r} does not appear to be a valid version number'.format(git_tag))
        sys.exit(-1)
    else:
        print('Tag {!r} appears to be a valid version number'.format(git_tag))


namespace.add_task(validatetag)


@invoke.task(pre=[clean_all], post=[plugin_tasks.sdist])
def sdist(context):
    """Create a source distribution"""
    with context.cd(TASK_ROOT_STR):
        context.run('python setup.py sdist')


namespace.add_task(sdist)


@invoke.task(pre=[clean_all], post=[plugin_tasks.wheel])
def wheel(context):
    """Build a wheel distribution"""
    with context.cd(TASK_ROOT_STR):
        context.run('python setup.py bdist_wheel')


namespace.add_task(wheel)


@invoke.task(pre=[validatetag, sdist, wheel])
def pypi(context):
    """Build and upload a distribution to pypi"""
    with context.cd(TASK_ROOT_STR):
        context.run('twine upload dist/*')


namespace.add_task(pypi)


@invoke.task(pre=[validatetag, sdist, wheel])
def pypi_test(context):
    """Build and upload a distribution to https://test.pypi.org"""
    with context.cd(TASK_ROOT_STR):
        context.run('twine upload --repository-url https://test.pypi.org/legacy/ dist/*')


namespace.add_task(pypi_test)


# Flake8 - linter and tool for style guide enforcement and linting
@invoke.task(post=[plugin_tasks.flake8])
def flake8(context):
    """Run flake8 linter and tool for style guide enforcement"""
    with context.cd(TASK_ROOT_STR):
        context.run("flake8")


namespace.add_task(flake8)
