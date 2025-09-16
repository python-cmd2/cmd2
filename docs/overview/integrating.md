# Integrate cmd2 Into Your Project

Once installed, you will want to ensure that your project's dependencies include `cmd2`. Make sure
your `pyproject.toml` or `setup.py` includes the following dependency

    'cmd2>=3,<4'

The `cmd2` project uses :simple-semver: [Semantic Versioning](https://semver.org), which means that
any incompatible API changes will be release with a new major version number. The public API is
documented in the [API Reference](../api/index.md).

We recommend that you follow the advice given by the Python Packaging User Guide related to
[install_requires](https://packaging.python.org/discussions/install-requires-vs-requirements/). By
setting an upper bound on the allowed version, you can ensure that your project does not
inadvertently get installed with an incompatible future version of `cmd2`.

## OS Considerations

If you would like to use [Tab Completion](../features/completion.md), then you need a compatible
version of [readline](https://tiswww.case.edu/php/chet/readline/rltop.html) installed on your
operating system (OS). `cmd2` forces a sane install of `readline` on both `Windows` and `macOS`, but
does not do so on `Linux`. If for some reason, you have a version of Python on a Linux OS who's
built-in `readline` module is based on the
[Editline Library (libedit)](https://www.thrysoee.dk/editline/) instead of `readline`, you will need
to manually add a dependency on `gnureadline`. Make sure to include the following dependency in your
`pyproject.toml` or `setup.py`:

    'gnureadline'
