# Packaging a cmd2 application for distribution

As a general-purpose tool for building interactive command-line applications, `cmd2` is designed to
be used in many ways. How you distribute your `cmd2` application to customers or end users is up to
you. See the [Overview of Packaging for Python](https://packaging.python.org/overview/) from the
Python Packaging Authority for a thorough discussion of the extensive options within the Python
ecosystem.

## Publishing to the Python Package Index (PyPI)

The easiest way is to use to follow the tutorial for
[Packaging Python Projects](https://packaging.python.org/en/latest/tutorials/packaging-projects/).
This will show you how to package your application as a Python package and uploadi to the Python
Package Index ([PyPI](https://pypi.org/)). Once published there, users will be able to install it
using idiomatic Python packaging tools such as [pip](https://pip.pypa.io/) or
[uv](https://github.com/astral-sh/uv).

Small tweaks on this process can allow you to publish to private PyPI mirror such as one hosted on
[AWS CodeArtifact](https://aws.amazon.com/codeartifact/).

## Packaging your application in a container using Docker

Packing your Python application in a [Docker](https://www.docker.com/) container is a great when it
comes to cross-platform portability and convenience since your this container will inlude all
dependencies for your application and run them in an isolated environment which won't conflict with
operating system dependencies.

This convenient blog post will show you
[How to "Dockerize" Your Python Applications](https://www.docker.com/blog/how-to-dockerize-your-python-applications/).

## Packing your application along with Python in an installer

For developers wishing to package a `cmd2` application into a single binary image or compressed
file, we can recommend all of the following based on personal and professional experience:

- [PyInstaller](https://www.pyinstaller.org)
    - Freeze (package) Python programs into stand-alone executables
    - PyInstaller bundles a Python application and all its dependencies into a single package
    - The user can run the packaged app without installing a Python interpreter or any modules
- [Nuitka](https://nuitka.net)
    - Nuitka is a Python compiler written in Python
    - You feed it your Python app, it does a lot of clever things, and spits out an executable or
      extension module
    - This can be particularly convenient if you wish to obfuscate the Python source code behind
      your application
- [Conda Constructor](https://github.com/conda/constructor)
    - Allows you to create a custom Python distro based on
      [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- [PyOxidizer](https://github.com/indygreg/PyOxidizer)
    - PyOxidizer is a utility for producing binaries that embed Python
    - PyOxidizer is capable of producing a single file executable - with a copy of Python and all
      its dependencies statically linked and all resources embedded in the executable
    - You can copy a single executable file to another machine and run a Python application
      contained within. It just works.

!!! warning

    We haven't personally tested PyOxidizer with `cmd2` applications like everything else on this page, though we have heard good things about it
