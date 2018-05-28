#
# coding=utf-8
"""Development related tasks to be run with 'invoke'"""

import os
import shutil

import invoke

# shared function
def rmrf(dirs, verbose=True):
    "Silently remove a list of directories"
    if isinstance(dirs, str):
        dirs = [dirs]

    for dir_ in dirs:
        if verbose:
            print("Removing {}".format(dir_))
        shutil.rmtree(dir_, ignore_errors=True)


# create namespaces
namespace = invoke.Collection()
namespace_clean = invoke.Collection('clean')
namespace.add_collection(namespace_clean, 'clean')

#####
#
# pytest, tox, pylint, and codecov
#
#####
@invoke.task
def pytest(context):
    "Run tests and code coverage using pytest"
    context.run("pytest --cov=cmd2 --cov-report=html")
namespace.add_task(pytest)

@invoke.task
def pytest_clean(context):
    "Remove pytest cache directories"
    #pylint: disable=unused-argument
    dirs = ['.pytest-cache', '.cache', 'htmlcov']
    rmrf(dirs)
namespace_clean.add_task(pytest_clean, 'pytest')

@invoke.task
def tox(context):
    "Run unit and integration tests on multiple python versions using tox"
    context.run("tox")
namespace.add_task(tox)

@invoke.task
def tox_clean(context):
    "Remove tox virtualenvs and logs"
    #pylint: disable=unused-argument
    rmrf('.tox')
namespace_clean.add_task(tox_clean, 'tox')

@invoke.task
def codecov_clean(context):
    "Remove code coverage reports"
    #pylint: disable=unused-argument
    dirs = set()
    for name in os.listdir(os.curdir):
        if name.startswith('.coverage'):
            dirs.add(name)
    rmrf(dirs)
namespace_clean.add_task(codecov_clean, 'coverage')


#####
#
# documentation
#
#####
DOCS_SRCDIR = 'docs'
DOCS_BUILDDIR = os.path.join('docs', '_build')

@invoke.task()
def docs(context, builder='html'):
    "Build documentation using sphinx"
    cmdline = 'python -msphinx -M {} {} {}'.format(builder, DOCS_SRCDIR, DOCS_BUILDDIR)
    context.run(cmdline)
namespace.add_task(docs)

@invoke.task
def docs_clean(context):
    "Remove rendered documentation"
    #pylint: disable=unused-argument
    rmrf(DOCS_BUILDDIR)
namespace_clean.add_task(docs_clean, name='docs')

@invoke.task
def livehtml(context):
    "Launch webserver on http://localhost:8000 with rendered documentation"
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

@invoke.task
def build_clean(context):
    "Remove the build directory"
    #pylint: disable=unused-argument
    rmrf(BUILDDIR)
namespace_clean.add_task(build_clean, 'build')

@invoke.task
def dist_clean(context):
    "Remove the dist directory"
    #pylint: disable=unused-argument
    rmrf(DISTDIR)
namespace_clean.add_task(dist_clean, 'dist')

@invoke.task
def eggs_clean(context):
    "Remove egg directories"
    #pylint: disable=unused-argument
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
def pycache_clean(context):
    "Remove __pycache__ directories"
    #pylint: disable=unused-argument
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
@invoke.task(pre=list(namespace_clean.tasks.values()), default=True)
def clean_all(context):
    "Run all clean tasks"
    #pylint: disable=unused-argument
    pass
namespace_clean.add_task(clean_all, 'all')

@invoke.task
def sdist(context):
    "Create a source distribution"
    context.run('python setup.py sdist')
namespace.add_task(sdist)

@invoke.task
def wheel(context):
    "Build a wheel distribution"
    context.run('python setup.py bdist_wheel')
namespace.add_task(wheel)

@invoke.task(pre=[clean_all, sdist, wheel])
def pypi(context):
    "Build and upload a distribution to pypi"
    context.run('twine upload dist/*')
namespace.add_task(pypi)

@invoke.task(pre=[clean_all, sdist, wheel])
def pypi_test(context):
    "Build and upload a distribution to https://test.pypi.org"
    context.run('twine upload --repository-url https://test.pypi.org/legacy/ dist/*')
namespace.add_task(pypi_test)

