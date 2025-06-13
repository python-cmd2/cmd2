# Installation Instructions

`cmd2` works on Linux, macOS, and Windows. It requires Python 3.9 or higher,
[pip](https://pypi.org/project/pip), and [setuptools](https://pypi.org/project/setuptools). If
you've got all that, then you can just:

```shell
$ pip install cmd2
```

!!! note

    Depending on how and where you have installed Python on your system and on what OS you are using, you may need to have administrator or root privileges to install Python packages. If this is the case, take the necessary steps required to run the commands in this section as root/admin, e.g.: on most Linux or Mac systems, you can precede them with `sudo`:

    ```shell
    $ sudo pip install <package_name>
    ```

## Prerequisites

If you have Python 3 >=3.9 installed from [python.org](https://www.python.org), you will already
have [pip](https://pypi.org/project/pip) and [setuptools](https://pypi.org/project/setuptools), but
may need to upgrade to the latest versions:

On Linux or OS X:

```shell
$ pip install -U pip setuptools
```

On Windows:

```shell
C:\> python -m pip install -U pip setuptools
```

## Install from PyPI {: #pip_install }

[pip](https://pypi.org/project/pip) is the recommended installer. Installing packages from
[PyPI](https://pypi.org) with pip is easy:

```shell
$ pip install cmd2
```

This will install the required 3rd-party dependencies, if necessary.

## Install from GitHub {: #github }

The latest version of `cmd2` can be installed directly from the master branch on GitHub using
[pip](https://pypi.org/project/pip):

```shell
$ pip install -U git+git://github.com/python-cmd2/cmd2.git
```

## Install from Debian or Ubuntu repos

We recommend installing from [pip](https://pypi.org/project/pip), but if you wish to install from
Debian or Ubuntu repos this can be done with apt-get.

For Python 3:

    $ sudo apt-get install python3-cmd2

This will also install the required 3rd-party dependencies.

!!! warning

    Versions of `cmd2` before 1.0.0 should be considered to be of unstable "beta" quality and should not be relied upon for production use. If you cannot get a version >= 0.8.9 from your OS repository, then we recommend installing from either pip or GitHub - see [Pip Install](installation.md#pip_install) or [Install from GitHub](installation.md#github).

## Upgrading cmd2

Upgrade an already installed `cmd2` to the latest version from [PyPI](https://pypi.org):

    pip install -U cmd2

This will upgrade to the newest stable version of `cmd2` and will also upgrade any dependencies if
necessary.

## Uninstalling cmd2

If you wish to permanently uninstall `cmd2`, this can also easily be done with
[pip](https://pypi.org/project/pip):

    $ pip uninstall cmd2

## readline Considerations

Tab completion for `cmd2` applications is only tested against GNU Readline. It does not work
properly with the [libedit](http://thrysoee.dk/editline/) library which is similar, but not
identical to GNU Readline. `cmd2` will disable all tab-completion support if an incompatible version
of `readline` is found.

When installed using `pip`, `uv`, or similar Python packaging tool on either `macOS` or `Windows`,
`cmd2` will automatically install a compatiable version of readline.

Most `Linux` OSes come with a compatible version of readline. However, if you are using a tool like
`uv` to install Python on your system and configure a virtual environment, `uv` installed versions
of Python come with `libEdit`.

macOS comes with the [libedit](http://thrysoee.dk/editline/) library which is similar, but not
identical, to GNU Readline. Tab completion for `cmd2` applications is only tested against GNU
Readline. In this case you just need to install the `gnureadline` Python package which is statically
linked against GNU Readline:

```shell
$ pip install -U gnureadline
```
