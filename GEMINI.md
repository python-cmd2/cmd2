# Instructions for Gemini CLI in a `uv` Python project

This `GEMINI.md` file provides context and instructions for the Gemini CLI when working with this
Python project, which utilizes `uv` for environment and package management.

## General Instructions

- **Environment Management:** Prefer using `uv` for all Python environment management tasks.
- **Package Installation:** Always use `uv` to install packages and ensure they are installed within
  the project's virtual environment.
- **Running Scripts/Commands:**
    - To run Python scripts within the project's virtual environment, use `uv run ...`.
    - To run programs directly from a PyPI package (installing it on the fly if necessary), use
      `uvx ...` (shortcut for `uv tool run`).
- **New Dependencies:** If a new dependency is required, please state the reason for its inclusion.

## Python Code Standards

To ensure Python code adheres to required standards, the following commands **must** be run before
creating or modifying any `.py` files:

```bash
make check
```

To run unit tests use the following command:

```bash
make test
```

To make sure the documentation builds properly, use the following command:

```bash
make docs-test
```

All 3 of the above commands should be run prior to committing code.
