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
