# Contributor's guide

We welcome pull requests from `cmd2` users and seasoned Python developers alike! Follow these steps
to contribute:

1. Find an issue that needs assistance by searching for the
   [Help Wanted](https://github.com/python-cmd2/cmd2/labels/help%20wanted) tag

2. Let us know you're working on it by posting a comment on the issue

3. Follow the [Contribution guidelines](#contribution-guidelines) below to start working on the
   issue

Remember to feel free to ask for help by leaving a comment within the Issue.

Working on your first pull request? You can learn how from the
[GitHub Docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request).

###### If you've found a bug that is not on the board, [follow these steps](../README.md#found-a-bug).

---

## Contribution guidelines

- [Prerequisites](#prerequisites)
- [Forking the project](#forking-the-project)
- [Creating a branch](#creating-a-branch)
- [Setting up for cmd2 development](#setting-up-for-cmd2-development)
- [Making changes](#making-changes)
- [Code Quality Checks](#code-quality-checks)
- [Running the test suite](#running-the-test-suite)
- [Squashing your commits](#squashing-your-commits)
- [Creating a pull request](#creating-a-pull-request)
- [Common steps](#common-steps)
- [How we review and merge pull requests](#how-we-review-and-merge-pull-requests)
- [How we close stale issues](#how-we-close-stale-issues)
- [Next steps](#next-steps)
- [Other resources](#other-resources)
- [Advice](#advice)
- [Developing in an IDE](#developing-in-an-ide)
- [Publishing a new release](#publishing-a-new-release)

### Prerequisites

`cmd2` development is heavily based around using [uv](https://github.com/astral-sh/uv) for Python
package and project management as well as creating and updating a local Python virtual environment.
We also rely on [npm](https://www.npmjs.com/) for installing a few dependencies like
[prettier](https://prettier.io/) for formatting non-Python files.

We have a [Makefile](../Makefile) with commands that make it quick and easy for developers to get
everything set up and perform common development tasks.

Nearly all project configuration, including for dependencies and quality tools is in the
[pyproject.toml](../pyproject.toml) file other than for `ruff` which is in
[ruff.toml](../ruff.toml).

> _Updating to the latest releases for all prerequisites via `uv` is recommended_. This can be done
> with `uv lock --upgrade` followed by `uv sync`.

#### Prerequisites to run cmd2 applications

See the `dependencies` list under the `[project]` heading in [pyproject.toml](../pyproject.toml).

| Prerequisite                                               | Minimum Version | Purpose                                                |
| ---------------------------------------------------------- | --------------- | ------------------------------------------------------ |
| [python](https://www.python.org/downloads/)                | `3.10`          | Python programming language                            |
| [pyperclip](https://github.com/asweigart/pyperclip)        | `1.8`           | Cross-platform clipboard functions                     |
| [rich](https://github.com/Textualize/rich)                 | `14.1.0`        | Add rich text and beautiful formatting in the terminal |
| [rich-argparse](https://github.com/hamdanal/rich-argparse) | `1.7.1`         | A rich-enabled help formatter for argparse             |

> `macOS` and `Windows` each have an extra dependency to ensure they have a viable alternative to
> [readline](https://tiswww.case.edu/php/chet/readline/rltop.html) available.

> Python 3.10 depends on [backports.strenum](https://github.com/clbarnes/backports.strenum) to use
> the `enum.StrEnum` class introduced in Python 3.11.

#### Additional prerequisites to build and publish cmd2

See the `build` list under the `[dependency-groups]` heading in [pyproject.toml](../pyproject.toml)
for a list of dependencies needed for building `cmd2`.

| Prerequisite                                             | Minimum Version | Purpose                          |
| -------------------------------------------------------- | --------------- | -------------------------------- |
| [build](https://pypi.org/project/build/)                 | `1.2.2`         | Python build frontend            |
| [setuptools](https://pypi.org/project/setuptools/)       | `72.1.0`        | Python package management        |
| [setuptools-scm](https://github.com/pypa/setuptools-scm) | `8.0.4`         | Manage your versions by scm tags |

> [twine](https://github.com/pypa/twine) 5.1 or newer is also needed for publishing releases to
> PyPI, but that is something only core maintainers need to worry about.

#### Additional prerequisites for developing cmd2

See the `dev` list under the `[dependency-groups]` heading in [pyproject.toml](../pyproject.toml)
for a list of dependencies needed for building `cmd2`.

| Prerequisite                                                                               | Minimum Version | Purpose                          |
| ------------------------------------------------------------------------------------------ | --------------- | -------------------------------- |
| [codecov](http://doc.pytest.org/en/latest/)                                                | `2.1.13`        | Cover coverage reporting         |
| [invoke](https://www.pyinvoke.org/)                                                        | `2.2.0`         | Command automation               |
| [mypy](https://mypy-lang.org/)                                                             | `1.13.0`        | Static type checker              |
| [pytest](https://docs.pytest.org/en/stable/)                                               | `3.0.6`         | Unit and integration tests       |
| [pytest-cov](http://doc.pytest.org/en/latest/)                                             | `6.0.0`         | Pytest code coverage             |
| [pytest-mock](https://pypi.org/project/pytest-mock/)                                       | `3.14.0`        | Pytest mocker fixture            |
| [mkdocs-include-markdown-plugin](https://pypi.org/project/mkdocs-include-markdown-plugin/) | `7.1.2`         | MkDocs Plugin include MkDn       |
| [mkdocs-macros-plugin](https://mkdocs-macros-plugin.readthedocs.io/)                       | `1.3.7`         | MkDocs Plugin for macros         |
| [mkdocs-material](https://squidfunk.github.io/mkdocs-material/)                            | `9.5.49`        | Documentation                    |
| [mkdocstrings[python]](https://mkdocstrings.github.io/)                                    | `0.27.0`        | MkDocs Plugin for Python AutoDoc |
| [ruff](https://github.com/astral-sh/ruff)                                                  | `0.7.3`         | Fast linter and formatter        |
| [uv](https://github.com/astral-sh/uv)                                                      | `0.5.1`         | Python package management        |

If Python is already installed in your machine, run the following commands to validate the versions:

```sh
$ python -V
$ pip freeze | grep pyperclip
```

If your versions are lower than the prerequisite versions, you should update.

If you do not already have Python installed on your machine, we recommend using
[uv](https://github.com/astral-sh/uv) for all of your Python needs because it is extremely fast,
meets all Python installation and packaging needs, and works on all platforms (Windows, Mac, and
Linux). You can install `uv` using instructions at the link above.

You can then install multiple versions of Python using `uv` like so:

```sh
uv python install 3.10 3.11 3.12 3.13
```

### Forking the project

#### Setting up your system

1. Install [Git](https://git-scm.com/) or your favorite Git client. If you aren't comfortable with
   Git at the command-line, then both [SmartGit](http://www.syntevo.com/smartgit/) and
   [GitKraken](https://www.gitkraken.com) are excellent cross-platform graphical Git clients.
2. (Optional) [Set up an SSH key](https://help.github.com/articles/generating-an-ssh-key/) for
   GitHub.
3. Create a parent projects directory on your system. For this guide, it will be assumed that it is
   `~/src`.

#### Forking cmd2

1. Go to the top-level cmd2 repository: <https://github.com/python-cmd2/cmd2>
2. Click the "Fork" button in the upper right hand corner of the interface
   ([more details here](https://help.github.com/articles/fork-a-repo/))
3. After the repository has been forked, you will be taken to your copy of the cmd2 repo at
   `yourUsername/cmd2`

#### Cloning your fork

1. Open a terminal / command line / Bash shell in your projects directory (_e.g.: `~/src/`_)
2. Clone your fork of cmd2, making sure to replace `yourUsername` with your GitHub username. This
   will download the entire cmd2 repo to your projects directory.

```sh
$ git clone https://github.com/yourUsername/cmd2.git
```

#### Set up your upstream

1. Change directory to the new cmd2 directory (`cd cmd2`)
2. Add a remote to the official cmd2 repo:

```sh
$ git remote add upstream https://github.com/python-cmd2/cmd2.git
```

Congratulations, you now have a local copy of the cmd2 repo!

#### Maintaining your fork

Now that you have a copy of your fork, there is work you will need to do to keep it current.

##### **Rebasing from upstream**

Do this prior to every time you create a branch for a PR:

1. Make sure you are on the `main` branch

> ```sh
> $ git status
> On branch main
> Your branch is up-to-date with 'origin/main'.
> ```

> If your aren't on `main`, resolve outstanding files and commits and checkout the `main` branch

> ```sh
> $ git checkout main
> ```

2. Do a pull with rebase against `upstream`

> ```sh
> $ git pull --rebase upstream main
> ```

> This will pull down all of the changes to the official mai branch, without making an additional
> commit in your local repo.

3. (_Optional_) Force push your updated main branch to your GitHub fork

> ```sh
> $ git push origin main --force
> ```

> This will overwrite the main branch of your fork.

### Creating a branch

Before you start working, you will need to create a separate branch specific to the issue or feature
you're working on. You will push your work to this branch.

#### Naming your branch

Name the branch something like `fix/xxx` or `feature/xxx` where `xxx` is a short description of the
changes or feature you are attempting to add. For example `fix/script-files` would be a branch where
you fix something specific to script files.

#### Adding your branch

To create a branch on your local machine (and switch to this branch):

```sh
$ git checkout -b [name_of_your_new_branch]
```

and to push to GitHub:

```sh
$ git push origin [name_of_your_new_branch]
```

##### If you need more help with branching, take a look at

_[this](https://github.com/Kunena/Kunena-Forum/wiki/Create-a-new-branch-with-git-and-manage-branches)_.

### Setting up for cmd2 development

For doing `cmd2` development, it is strongly recommended you create a virtual environment using `uv`
by following the instructions in the next section.

#### Create a new environment for cmd2 using uv

`cmd2` has support for using [uv](https://github.com/astral-sh/uv) for development.

`uv` is single tool to replace `pip`, `pip-tools`, `pipx`, `poetry`, `pyenv`, `twine`, `virtualenv`,
and more. `cmd2` contains configuration for using `uv` in it's `pyproject.toml` file which makes it
extremely easy to set up a `cmd2` development environment using `uv`.

To create a virtual environment using the latest stable version of Python and install everything
needed for `cmd2` development using `uv`, do the following from the root of your cloned `cmd2`
repository:

```sh
make install
```

This will also install the recommended Git pre-commit hooks for auto-formatting and linting locally.

To create a new virtualenv, using a specific version of Python you have installed, use the --python
VERSION flag, like so:

```sh
uv venv --python 3.12
```

Then you can run commands in this isolated virtual environment using `uv` like so:

```sh
uv run examples/hello_cmd2.py
```

Alternatively you can activate the virtual environment using the OS-specific command such as this on
Linux or macOS:

```sh
source .venv/bin/activate
```

Assuming you cloned the repository to `~/src/cmd2` and set up a virtual environment using `uv`,
`cmd2` in this venv is in
[editable mode](https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs). Changes to the
source code are immediately available when the python interpreter imports `cmd2`, there is no need
to re-install the module after every change. This command will also install all of the runtime
dependencies for `cmd2` and modules used for development of `cmd2`:

```sh
$ cd ~/src/cmd2
$ uv venv
```

This project uses many python modules for various development tasks, including testing, rendering
documentation, and building and distributing releases. These modules can be configured many
different ways, which can make it difficult to learn the specific incantations required for each
project you're familiar with.

This project uses [make]() to provide a clean, high-level interface for these development tasks. To
see the full list of make commands available:

```sh
$ make help
```

You can run multiple make commands in a single invocation, for example::

```sh
$ make test docs-test
```

That one command will run all unit and integration tests and also ensure the documentation builds
without any warnings.

If you want to see the details about what any of these commands are doing under the hood, just look
at the [Makefile](../Makefile).

Now you can check if everything is installed and working:

```sh
$ cd ~src/cmd2
$ make check
```

This will run all auto-formatters, linters, and type checkers to ensure code quality. You should run
this every time before committing any code. If this all runs successfully, then your virtual
environment is set up and working properly.

You can also run the example app and see a prompt that says "(Cmd)" running the command:

```sh
$ uv run examples/getting_started.py
```

You can type `help` to get help or `quit` to quit. If you see that, then congratulations – you're
all set. Otherwise, refer to the cmd2
[installation instructions](https://cmd2.readthedocs.io/en/latest/overview/installation.html). There
also might be an error in the console of your Bash / terminal / command line that will help identify
the problem.

### Making changes

This bit is up to you!

#### How to find code in the cmd2 codebase to fix/edit

The cmd2 project directory structure is pretty simple and straightforward. All actual code for cmd2
is located underneath the `cmd2` directory. The code to generate the documentation is in the `docs`
directory. Unit and integration tests are in the `tests` directory. The `examples` directory
contains examples of how to use cmd2. There are various other files in the root directory, but these
are primarily related to continuous integration and release deployment.

#### Changes to the documentation files

If you made changes to any file in the `/docs` directory, you need to build the MkDocs documentation
and make sure your changes look good:

```sh
$ make docs-test
```

In order to see the changes, use your web browser of choice to open `~/cmd2/build/html/index.html`.

If you would rather use a webserver to view the documentation, including automatic page refreshes as
you edit the files, use:

```sh
$ make docs
```

You will be shown the IP address and port number where the documents are now served, usually
[http://127.0.0.1:8000/](http://127.0.0.1:8000/).

### Code Quality Checks

You should have idiomatic formatters and linters running in your IDE or at the command line before
you commit code. `cmd2` uses [ruff](https://github.com/astral-sh/ruff) as part of its continuous
integration (CI) process for both linting and auto-formatting of Python code. It also uses
[prettier](https://prettier.io/) for auto-formatting other file types and
[mypy](https://mypy-lang.org/) for doing static type checking of Python code based on type
annotations.

> Please do not ignore any linting errors in code you write or modify, as they are meant to **help**
> you and to ensure a clean and simple code base. Don't worry about linting errors in code you don't
> touch though - cleaning up the legacy code is a work in progress.

You can quickly run all code quality stuff in one fell swoop using:

```sh
make check
```

#### Python Formatting

To check if Python formatting is correct:

```sh
make format
```

NOTE: This will automatically fix the formatting, so just run it twice and it should be good.

#### Linting

To run the Python linter:

```shell
make lint
```

#### Static Type Checking

```shell
make typecheck
```

### Running the test suite

When you're ready to share your code, run the test suite:

```sh
$ cd ~/cmd2
$ make test
```

and ensure all tests pass.

Running the test suite also calculates test code coverage. A summary of coverage is shown on the
screen. A full report is available in `~/cmd2/htmlcov/index.html`.

### Squashing your commits

While squashing your commits is best practice, don't worry about it. We do this automatically when
we merge in Pull Requests (PRs).

If you want to understand how to do this manually, see
[this article](http://forum.freecodecamp.com/t/how-to-squash-multiple-commits-into-one-with-git/13231).

### Creating a pull request

#### What is a pull request?

A pull request (PR) is a method of submitting proposed changes to the cmd2 repo (or any repo, for
that matter). You will make changes to copies of the files which make up cmd2 in a personal fork,
then apply to have them accepted by cmd2 proper.

#### Need help?

GitHub has a good guide on how to contribute to open source
[here](https://opensource.guide/how-to-contribute/).

#### Important: ALWAYS EDIT ON A BRANCH

If you take away only one thing from this document, it should be this: Never, **EVER** make edits to
the `main` branch. ALWAYS make a new branch BEFORE you edit files. This is critical, because if your
PR is not accepted, your copy of main will be forever sullied and the only way to fix it is to
delete your fork and re-fork.

#### Methods

There are two methods of creating a pull request for cmd2:

- Editing files on a local clone (recommended)
- Editing files via the GitHub Interface

##### Method 1: Editing via your local fork _(recommended)_

This is the recommended method. Read about
[how to set up and maintain a local instance of cmd2](#maintaining-your-fork).

1. Perform the maintenance step of rebasing `main`
2. Ensure you're on the `main` branch using `git status`:

```sh
$ git status
On branch main
Your branch is up-to-date with 'origin/main'.

nothing to commit, working directory clean
```

1. If you're not on main or your working directory is not clean, resolve any outstanding
   files/commits and checkout main `git checkout main`

2. Create a branch off of `main` with git: `git checkout -B branch/name-here` **Note:** Branch
   naming is important. Use a name like `fix/short-fix-description` or
   `feature/short-feature-description`. Review the
   [Contribution Guidelines](#contribution-guidelines) for more detail.

3. Edit your file(s) locally with the editor of your choice

4. Check your `git status` to see unstaged files

5. Add your edited files: `git add path/to/filename.ext` You can also do: `git add .` to add all
   unstaged files. Take care, though, because you can accidentally add files you don't want added.
   Review your `git status` first.

6. Commit your edits: `git commit -m "Brief description of commit"`. Do not add the issue number in
   the commit message.

7. Squash your commits, if there are more than one

8. Push your commits to your GitHub Fork: `git push -u origin branch/name-here`

9. Go to [Common steps](#common-steps)

##### Method 2: Editing via the GitHub interface

Note: Editing via the GitHub Interface is not recommended, since it is not possible to update your
fork via GitHub's interface without deleting and recreating your fork.

If you really want to go this route (which isn't recommended), you can Google for more information
on how to do it.

### Common steps

1. Once the edits have been committed, you will be prompted to create a pull request on your fork's
   GitHub page

2. By default, all pull requests should be against the cmd2 main repo, `main` branch

3. Submit a pull request from your branch to cmd2's `main` branch

4. The title (also called the subject) of your PR should be descriptive of your changes and
   succinctly indicate what is being fixed
    - **Do not add the issue number in the PR title or commit message**

    - Examples: `Add test cases for Unicode support`; `Correct typo in overview documentation`

5. In the body of your PR include a more detailed summary of the changes you made and why
    - If the PR is meant to fix an existing bug/issue, then, at the end of your PR's description,
      append the keyword `closes` and #xxxx (where xxxx is the issue number). Example:
      `closes #1337`. This tells GitHub to close the existing issue if the PR is merged.

6. Indicate what local testing you have done (e.g. what OS and version(s) of Python did you run the
   unit test suite with)

7. Creating the PR causes our continuous integration (CI) systems to automatically run all of the
   unit tests on all supported OSes and all supported versions of Python. You should watch your PR
   to make sure that all unit tests pass on every version of Python for each of Linux, Windows, and
   macOS.

8. If any unit tests fail, you should look at the details and fix the failures. You can then push
   the fix to the same branch in your fork. The PR will automatically get updated and the CI system
   will automatically run all of the unit tests again.

### How we review and merge pull requests

cmd2 has a team of volunteer Maintainers. These Maintainers routinely go through open pull requests
in a process called [Quality Assurance](https://en.wikipedia.org/wiki/Quality_assurance) (QA). We
use [GitHub Actions](https://github.com/features/actions) to automatically run all of the unit tests
on multiple operating systems and versions of Python and to also run the code quality checks on at
least one version of Python.

1. If your changes can merge without conflicts and all unit tests pass for all OSes and supported
   versions of Python, then your pull request (PR) will have a big green checkbox which says
   something like "All Checks Passed" next to it. If this is not the case, there will be a link you
   can click on to get details regarding what the problem is. It is your responsibility to make sure
   all unit tests are passing. Generally a Maintainer will not QA a pull request unless it can merge
   without conflicts and all unit tests pass on all supported platforms.

2. If a Maintainer QA's a pull request and confirms that the new code does what it is supposed to do
   without seeming to introduce any new bugs, and doesn't present any backward compatibility issues,
   they will merge the pull request.

If you would like to apply to join our Maintainer team, message
[@tleonhardt](https://github.com/tleonhardt) with links to 5 of your pull requests that have been
accepted.

### How we close stale issues

We will close any issues that have been inactive for more than 60 days or pull requests that have
been inactive for more than 30 days, except those that match any of the following criteria:

- bugs that are confirmed
- pull requests that are waiting on other pull requests to be merged
- features that are part of a cmd2 GitHub Milestone or Project

### Next steps

#### If your PR is accepted

Once your PR is accepted, you may delete the branch you created to submit it. This keeps your
working fork clean.

You can do this with a press of a button on the GitHub PR interface. You can delete the local copy
of the branch with: `git branch -D branch/to-delete-name`

#### If your PR is rejected

Don't despair! You should receive solid feedback from the Maintainers as to why it was rejected and
what changes are needed.

Many pull requests, especially first pull requests, require correction or updating. If you have used
the GitHub interface to create your PR, you will need to close your PR, create a new branch, and
re-submit.

If you have a local copy of the repo, you can make the requested changes and amend your commit with:
`git commit --amend` This will update your existing commit. When you push it to your fork you will
need to do a force push to overwrite your old commit: `git push --force`

Be sure to post in the PR conversation that you have made the requested changes.

### Other resources

- [PEP 8 Style Guide for Python Code](https://www.python.org/dev/peps/pep-0008/)

- [Searching for your issue on GitHub](https://help.github.com/articles/searching-issues/)

- [Creating a new GitHub issue](https://help.github.com/articles/creating-an-issue/)

### Advice

Here is some advice regarding what makes a good pull request (PR) from the perspective of the cmd2
maintainers:

- Multiple smaller PRs divided by topic are better than a single large PR containing a bunch of
  unrelated changes
- Maintaining backward compatibility is important
- Good unit/functional tests are very important
- Accurate documentation is also important
- Adding new features is of the lowest importance, behind bug fixes, unit test
  additions/improvements, code cleanup, and documentation
- It's best to create a dedicated branch for a PR, use it only for that PR, and delete it once the
  PR has been merged
- It's good if the branch name is related to the PR contents, even if it's just "fix123" or
  "add_more_tests"
- Code coverage of the unit tests matters, so try not to decrease it
- Think twice before adding dependencies to third-party libraries (outside of the Python standard
  library) because it could affect a lot of users

### Developing in an IDE

We recommend using [Visual Studio Code](https://code.visualstudio.com) with the
[Python extension](https://code.visualstudio.com/docs/languages/python) and its
[Integrated Terminal](https://code.visualstudio.com/docs/python/debugging) debugger for debugging
since it has excellent support for debugging console applications.

[PyCharm](https://www.jetbrains.com/pycharm/) is also quite good and has very nice
[code inspection](https://www.jetbrains.com/help/pycharm/code-inspection.html) capabilities.

#### PyCharm Settings

One of the best things about **PyCharm** is that it "just works" with essentially no configuration
tweaks required. The default out-of-the-box experience is excellent.

The one plugin we consider essential for PyCharm is
[RyeCharm](https://plugins.jetbrains.com/plugin/25230-ryecharm). `RyeCharm` is an all-in-one PyCharm
plugin for [Astral](https://astral.sh/)-backed Python tools: [uv](https://github.com/astral-sh/uv),
[Ruff](https://github.com/astral-sh/ruff), and [ty](https://github.com/astral-sh/ty). NOTE: `ty`
support is provisional as that new type checker is in early alpha developement.

#### VSCode Settings

While **VSCode** is a phenomenal IDE for developing in Python, the out-of-the-box experience leaves
a lot to be desired. You will need to install a number of extenstions and tweak the default
configuration for many of them in order to get an optimal developer experience.

Recommended VSCode extensions:

- [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python) - Python language
  support with extension access points for IntelliSense (Pylance), Debugging (Python Debugger),
  linting, formatting, etc.
- [Prettier](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode) - Code
  formatter for Markdown and YAML files
- [GitLens](https://marketplace.visualstudio.com/items?itemName=eamodio.gitlens) - Supercharges Git
  support in VSCode
- [YAML](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml) - YAML language
  support
- [Code Spell Checker](https://marketplace.visualstudio.com/items?itemName=streetsidesoftware.code-spell-checker) -
  Spell checker for source code
- [Markdown All in One](https://marketplace.visualstudio.com/items?itemName=yzhang.markdown-all-in-one) -
  All you need to write Markdown (keyboard shortcuts, table of contents, auto preview and more)
- [Makefile Tools](https://marketplace.visualstudio.com/items?itemName=ms-vscode.makefile-tools) -
  Provide makefile support in VS Code
- [Even Better TOML](https://marketplace.visualstudio.com/items?itemName=tamasfe.even-better-toml) -
  Fully-featured TOML support
- [Markdown Preview Mermaid Support](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-mermaid) -
  Adds Mermaid diagram and flowchart support to VS Code's builtin markdown preview
- [Ruff](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff) - Support for the
  Ruff linter and formatter

Depending on what file types you are editing, you may only need a subset of those extensions.

Here is an example of what your `User Settings JSON` file in VSCode might look like for a good
experience, take it as a starting point and tweak as you see fit

```json
{
    "[css]": {
        "editor.defaultFormatter": "esbenp.prettier-vscode"
    },
    "editor.formatOnSave": true,
    "editor.largeFileOptimizations": false,
    "editor.renderWhitespace": "trailing",
    "git.blame.editorDecoration.enabled": false,
    "git.openRepositoryInParentFolders": "always",
    "gitlens.telemetry.enabled": false,
    "[html]": {
        "editor.defaultFormatter": "esbenp.prettier-vscode"
    },
    "[json]": {
        "editor.defaultFormatter": "esbenp.prettier-vscode"
    },
    "[markdown]": {
        "editor.defaultFormatter": "esbenp.prettier-vscode",
        "editor.formatOnSave": true,
        "editor.formatOnPaste": true
    },
    "python.analysis.ignore": ["*"],
    "python.terminal.shellIntegration.enabled": true,
    "[python]": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.codeActionsOnSave": {
            "source.fixAll": "explicit",
            "source.organizeImports": "explicit"
        }
    },
    "redhat.telemetry.enabled": false,
    "ruff.lineLength": 127,
    "security.workspace.trust.untrustedFiles": "open",
    "telemetry.telemetryLevel": "off",
    "[toml]": {
        "editor.defaultFormatter": "esbenp.prettier-vscode",
        "editor.formatOnSave": true
    },
    "yaml.schemas": {
        "https://squidfunk.github.io/mkdocs-material/schema.json": "mkdocs.yml"
    },
    "yaml.customTags": [
        "!ENV scalar",
        "!ENV sequence",
        "!relative scalar",
        "tag:yaml.org,2002:python/name:material.extensions.emoji.to_svg",
        "tag:yaml.org,2002:python/name:material.extensions.emoji.twemoji",
        "tag:yaml.org,2002:python/name:pymdownx.superfences.fence_code_format",
        "tag:yaml.org,2002:python/object/apply:pymdownx.slugs.slugify mapping"
    ],
    "[yaml]": {
        "editor.defaultFormatter": "esbenp.prettier-vscode"
    }
}
```

## Branching Strategy and Semantic Versioning

Starting with version 1.0.0, `cmd2` has adopted [Semantic Versioning](https://semver.org).

### Semantic Versioning Summary

Given a version number `MAJOR`.`MINOR`.`PATCH`, increment the:

- `MAJOR` version when you make incompatible API changes,
- `MINOR` version when you add functionality in a backwards compatible manner, and
- `PATCH` version when you make backwards compatible bug fixes.

### Branching Strategy

We use the **main** branch for the upcoming `PATCH` release - i.e. if the current version of `cmd2`
is 1.0.2, then the **main** branch contains code which is planned for release in 1.0.3.

If work needs to be done for a `MAJOR` or `MINOR` release when we anticipate there will be a `PATCH`
release in-between, then a branch should be created named for the appropriate version number for the
work, e.g. if the current release of `cmd2` is 1.0.2 and a backwards-incompatible change needs to be
committed for an upcoming `MAJOR` release, then this work should be committed to a **2.0.0** branch
until such a time as we are ready to release version 2.0.0.

Following this strategy, releases are always done from the **main** branch and `MAJOR` or `MINOR`
branches are merged to **main** immediately prior to doing a release. Once merged to **main**, the
other branches can be deleted. All releases are tagged so that they can be reproduced if necessary.

## Publishing a new release

Since 0.9.2, the process of publishing a new release of `cmd2` to [PyPi](https://pypi.org/) has been
mostly automated. The manual steps are all git operations. Here's the checklist:

1. Make sure you're on the proper branch (almost always **main**)
1. Make sure all the unit tests pass with `invoke pytest` or `py.test`
1. Make sure latest year in `LICENSE` matches current year
1. Make sure `CHANGELOG.md` describes the version and has the correct release date
1. Add a git tag representing the version number using `invoke tag x.y.z`
    - Where x, y, and z are all small non-negative integers
1. (Optional) Run `invoke pypi-test` to clean, build, and upload a new release to
   [Test PyPi](https://test.pypi.org)
1. Run `invoke pypi` to clean, build, and upload a new release to [PyPi](https://pypi.org/)

## Acknowledgement

Thanks to the good folks at [freeCodeCamp](https://github.com/freeCodeCamp/freeCodeCamp) for
creating an excellent `CONTRIBUTING` file which we have borrowed heavily from.
