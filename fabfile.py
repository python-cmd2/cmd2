# coding=utf-8
from fabric.api import env, task, local
import os
import errno

env.projname = local("python setup.py --name", capture=True)
env.version = local("python setup.py --version", capture=True)


def mkdirs(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


@task
def clean():
    local("python setup.py clean")
    local("find . -name '*.pyc' -delete")


@task
def build():
    local("python setup.py sdist")


@task
def rebuild():
    clean()
    build()


@task
def prepare_cover_dir():
    # If there isn't a cover symlink, create and link the directory
    if os.path.isdir('cover'):
        return

    mkdirs('docs/_build/html/cover')
    local("ln -s docs/_build/html/cover")
    local("rm -rf cover/*")


@task
def coverage():
    prepare_cover_dir()
    local("py.test -n4 --cov=%s --cov-report=term-missing "
          "--cov-report=html" % env.projname)


@task
def pylint():
    local("pylint %s tests" % env.projname)


@task
def doc():
    local("sphinx-build -b html docs  docs/_build/html")


@task
def docwithcoverage():
    coverage()
    doc()


@task
def tox():
    local('tox')


@task
def release_check():
    tags = local("git tag", capture=True)
    tags = set(tags.splitlines())
    if 'a' in env.version:
        print("WARNING: alpha release %s" % env.version)

    # hacky CHANGELOG.md check
    with open("CHANGELOG.md") as f:
        raw_changes = f.read()
    assert "%s\n---" % env.version in raw_changes, \
        "The current version %s is not in CHANGELOG.md" % env.version
    if env.version in tags:
        raise Exception("Already released v. %r" % env.version)


@task
def release():
    release_check()
    clean()
    build()
    print("Releasing", env.projname, "version", env.version)
    local("git tag %s" % env.version)
    local("python setup.py sdist upload")
    local("git push --tags")


@task
def test_pip_install():
    local("d=$(mktemp -d) && cd $d && virtualenv . && . "
          "bin/activate && pip install -v %s" % env.projname)
