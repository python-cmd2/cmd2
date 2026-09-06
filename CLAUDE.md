# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## Project

`cmd2` is a framework for building interactive command-line applications (REPLs) in Python. It
extends the stdlib `cmd` module and is built on **prompt-toolkit** (interactive input, key bindings,
completion, toolbars) and **Rich** / **rich-argparse** (all output rendering, help formatting,
theming). Requires Python >= 3.11. Environment/package management is **uv**.

## Commands

All work happens inside the uv-managed venv — run Python via `uv run ...`, and `uvx ...` for one-off
tools. Never `pip install`; if a new dependency is needed, state why before adding it.

```bash
make install     # create the venv, install prek git hooks + prettier (one time)
make check       # lock check + prek (ruff format/lint, prettier, typos) + ty + mypy
make test        # pytest with coverage over tests/
make docs-test   # verify the docs build cleanly (zensical)
make docs        # build + serve docs with live reload
make help        # list all targets
```

`make check`, `make test`, and `make docs-test` must all pass before committing. Run `make check`
before creating or modifying any `.py` file as well.

Narrower targets: `make format`, `make lint`, `make mypy`, `make ty`, `make typecheck`.

Running a single test or file (coverage flags come from `pyproject.toml` `addopts`, so pass
`--no-cov` when you just want a fast run):

```bash
uv run pytest tests/test_cmd2.py --no-cov
uv run pytest tests/test_cmd2.py::test_base_help -x --no-cov
uv run pytest -k "toolbar" --no-cov
```

On Windows-sensitive code, note `make test` runs pytest under `python -Xutf8`.

## Architecture

### Command dispatch

`cmd2/cmd2.py` (the `Cmd` class) is the core and by far the largest module. The flow for one line of
input is:

1. `cmdloop()` → `_cmdloop()` drives a prompt-toolkit `PromptSession` (created in
   `_create_prompt_session`), not readline. Completion, history, lexing, and key bindings are all
   supplied by prompt-toolkit adapters in `cmd2/pt_utils.py` (`Cmd2Completer`, `Cmd2History`,
   `Cmd2Lexer`).
2. `onecmd_plus_hooks()` parses the line into a `Statement` (`cmd2/parsing.py` — handles shortcuts,
   aliases, macros, terminators, multiline commands, redirection and pipe tokens), then runs the
   plugin hook chain.
3. `_redirect_output()` swaps `self.stdout` for a file or subprocess pipe when the statement has
   redirection, and restores it in the `finally` path.
4. `onecmd()` looks up and calls the `do_*` method.

Hooks (`cmd2/plugin.py` dataclasses, registered via `register_postparsing_hook`,
`register_precmd_hook`, `register_postcmd_hook`, `register_cmdfinalization_hook`,
`register_preloop_hook`, `register_postloop_hook`) are the supported extension points; the legacy
`precmd`/`postcmd` overrides still exist but are weaker.

### Argument parsing and completion

Three layers, all producing a `Cmd2ArgumentParser`:

- `cmd2/argparse_utils.py` — `Cmd2ArgumentParser` plus monkey-patching that extends argparse with
  range `nargs` tuples, per-argument completion metadata, and subcommand records.
- `cmd2/decorators.py` — `@with_argparser`, `@with_argument_list`, `@with_category`,
  `@as_subcommand_to` attach parsers/metadata to `do_*` methods.
- `cmd2/annotated.py` — the newer, still-experimental Typer-style path: `@with_annotated` builds a
  parser from a function's type hints, with `Argument`/`Option` metadata via `typing.Annotated`.

Parsers are built lazily and cached by the `CommandParsers` class in `cmd2.py` (`_build_parser`), so
that `CommandSet`-supplied subcommands can be attached and detached at runtime.
`cmd2/argparse_completer.py` walks a parser to produce tab completions; completion results are
`Completions`/`CompletionItem` objects from `cmd2/completion.py`.

### Output and theming

Never print directly — go through `Cmd.print_to` / `poutput` / `perror` / `pwarning` / `pfeedback` /
`ppaged`, which route to Rich consoles defined in `cmd2/rich_utils.py` (`Cmd2GeneralConsole`,
`Cmd2RichArgparseConsole`, `Cmd2ExceptionConsole`). Styling flows one way: `cmd2/styles.py`
(style-name StrEnum + defaults) → `cmd2/theme.py` (single global theme, updated in-place for Rich
and exposed to prompt-toolkit through a `DynamicStyle`) → `cmd2/pt_utils.py` (`rich_to_pt_style`
converts Rich styles into prompt-toolkit ones). Adding a color or style means touching
`styles.py`/`colors.py`/`theme.py`, not hardcoding ANSI.

`cmd2/command_toolbar.py` and `cmd2/pager.py` are the trickiest parts of the codebase: they keep a
prompt-toolkit application alive _during_ synchronous command execution (bottom toolbar refresh,
paging) while stdout is proxied and redirection may be active. Changes there need care around
threads, signals, and Windows behavior.

### Modularity

`cmd2/command_set.py` (`CommandSet`) lets commands live in separate classes that are registered and
unregistered at runtime via `Cmd.register_command_set`; `cmd2/py_bridge.py` exposes the app to
embedded Python/IPython shells and `run_pyscript` while keeping isolation.

## Conventions

- Ruff is authoritative for format and lint (`ruff.toml`, line length 127, double quotes). Do not
  suppress lint errors in code you write; broad ignores already exist for `examples/` and `tests/`.
- Both `mypy --strict` and `ty` must pass on the `cmd2` package. Full type annotations are required
  on all library code (excluded: `tests/`, `examples/`, `docs/`).
- Docstrings are enforced by pydocstyle rules; public API items are documented in `docs/api/*.md`
  and rendered by mkdocstrings, so keep docstrings accurate when changing signatures.
- Anything not documented under `docs/api/` is not public API (`cmd2/constants.py` says so
  explicitly).
- Add user-visible changes to `CHANGELOG.md` under the current in-progress version heading.
- `main` is the branch for the next PATCH release; MAJOR/MINOR work happens on a branch named for
  the target version. Releases are tagged and published from `main`.
- Do not commit spec, plan, or markdown documents without asking first. Save plans to
  `~/.superpowers/plans/` rather than the project directory.

## Commit conventions

Never add "Co-Authored-By" lines to commits. Do not include Claude attribution in commit messages,
PR descriptions, or any git metadata.
