# Contributor's guide

We welcome pull requests from cmd2 users and seasoned Python developers alike! Follow these steps to contribute:

1. Find an issue that needs assistance by searching for the [Help Wanted](https://github.com/python-cmd2/cmd2/labels/help%20wanted) tag

2. Let us know you're working on it by posting a comment on the issue

3. Follow the [Contribution guidelines](#contribution-guidelines) to start working on the issue

Remember to feel free to ask for help by leaving a comment within the Issue.

Working on your first pull request? You can learn how from this *free* series 
[How to Contribute to an Open Source Project on GitHub](https://egghead.io/series/how-to-contribute-to-an-open-source-project-on-github).

###### If you've found a bug that is not on the board, [follow these steps](README.md#found-a-bug).

--------------------------------------------------------------------------------

## Contribution guidelines

- [Prerequisites](#prerequisites)
- [Forking the project](#forking-the-project)
- [Creating a branch](#creating-a-branch)
- [Setting up for cmd2 development](#setting-up-for-cmd2-development)
- [Making changes](#making-changes)
- [Static code analysis](#static-code-analysis)
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

The tables below list all prerequisites along with the minimum required version for each.

> _Updating to the latest releases for all prerequisites via pip or conda is recommended_.

#### Prerequisites to run cmd2 applications

| Prerequisite                                        | Minimum Version |
| --------------------------------------------------- | --------------- |
| [python](https://www.python.org/downloads/)         | `3.5`           |
| [attrs](https://github.com/python-attrs/attrs)      | `16.3`          |
| [colorama](https://github.com/tartley/colorama)     | `0.3.7`         |
| [pyperclip](https://github.com/asweigart/pyperclip) | `1.6`           |
| [setuptools](https://pypi.org/project/setuptools/)  | `34.4`          |
| [wcwidth](https://pypi.python.org/pypi/wcwidth)     | `0.1.7`         |


#### Additional prerequisites to run cmd2 unit tests

| Prerequisite                                | Minimum Version |
| ------------------------------------------- | --------------- |
| [pytest](http://doc.pytest.org/en/latest/)  | `3.0.6`         |
| [pytest-mock](https://pypi.org/project/pytest-mock/) | `1.3`  |

#### Additional prerequisites to build cmd2 documentation
| Prerequisite                                | Minimum Version |
| ------------------------------------------- | --------------- |
| [sphinx](http://www.sphinx-doc.org)         | `1.4.9`         |
| [sphinx-rtd-theme](https://github.com/snide/sphinx_rtd_theme) | `0.1.9` |

#### Optional prerequisites for enhanced unit test features
| Prerequisite                                | Minimum Version |
| ------------------------------------------- | --------------- |
| [pytest-cov](https://pypi.python.org/pypi/pytest-cov) | `2.4` |
| [flake8](http://flake8.pycqa.org/en/latest/)| `3.0`           |

If Python is already installed in your machine, run the following commands to validate the versions:

```sh
$ python -V
$ pip freeze | grep pyperclip
```

If your versions are lower than the prerequisite versions, you should update.

If you do not already have Python installed on your machine, we recommend using the 
[Anaconda](https://www.continuum.io/downloads) distribution because it provides an excellent out-of-the-box install on 
all platforms (Windows, Mac, and Linux) and because it supports having multiple Python environments (versions of Python) 
installed simultaneously.

### Forking the project

#### Setting up your system

1. Install [Git](https://git-scm.com/) or your favorite Git client.  If you aren't comfortable with Git at the 
command-line, then both [SmartGit](http://www.syntevo.com/smartgit/) and [GitKraken](https://www.gitkraken.com) are 
excellent cross-platform graphical Git clients.
2. (Optional) [Set up an SSH key](https://help.github.com/articles/generating-an-ssh-key/) for GitHub.
3. Create a parent projects directory on your system. For this guide, it will be assumed that it is `~/src`.

#### Forking cmd2

1. Go to the top-level cmd2 repository: <https://github.com/python-cmd2/cmd2>
2. Click the "Fork" button in the upper right hand corner of the interface 
([more details here](https://help.github.com/articles/fork-a-repo/))
3. After the repository has been forked, you will be taken to your copy of the cmd2 repo at `yourUsername/cmd2`

#### Cloning your fork

1. Open a terminal / command line / Bash shell in your projects directory (_e.g.: `~/src/`_)
2. Clone your fork of cmd2, making sure to replace `yourUsername` with your GitHub username. This will download the 
entire cmd2 repo to your projects directory.

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

1. Make sure you are on the `master` branch

  > ```sh
  > $ git status
  > On branch master
  > Your branch is up-to-date with 'origin/master'.
  > ```

  > If your aren't on `master`, resolve outstanding files and commits and checkout the `master` branch

  > ```sh
  > $ git checkout master
  > ```

2. Do a pull with rebase against `upstream`

  > ```sh
  > $ git pull --rebase upstream master
  > ```

  > This will pull down all of the changes to the official master branch, without making an additional commit in your local repo.

3. (_Optional_) Force push your updated master branch to your GitHub fork

  > ```sh
  > $ git push origin master --force
  > ```

  > This will overwrite the master branch of your fork.

### Creating a branch

Before you start working, you will need to create a separate branch specific to the issue or feature you're working on. 
You will push your work to this branch.

#### Naming your branch

Name the branch something like `fix/xxx` or `feature/xxx` where `xxx` is a short description of the changes or feature 
you are attempting to add. For example `fix/script-files` would be a branch where you fix something specific to script 
files.

#### Adding your branch

To create a branch on your local machine (and switch to this branch):

```sh
$ git checkout -b [name_of_your_new_branch]
```

and to push to GitHub:

```sh
$ git push origin [name_of_your_new_branch]
```

##### If you need more help with branching, take a look at _[this](https://github.com/Kunena/Kunena-Forum/wiki/Create-a-new-branch-with-git-and-manage-branches)_.


### Setting up for cmd2 development
For doing cmd2 development, it is recommended you create a virtual environment using Conda or Virtualenv and install the 
package from the source.

#### Create a new environment for cmd2 using Pipenv
`cmd2` has support for using [Pipenv](https://docs.pipenv.org/en/latest/) for development.  

`Pipenv` essentially combines the features of `pip` and `virtualenv` into a single tool.  `cmd2` contains a Pipfile which
 makes it extremely easy to setup a `cmd2` development environment using `pipenv`.  

To create a virtual environment and install everything needed for `cmd2` development using `pipenv`, do the following 
from a GitHub checkout:
```sh
pipenv install --dev
```

To create a new virtualenv, using a specific version of Python you have installed (and on your PATH), use the 
--python VERSION flag, like so:
```sh
pipenv install --dev --python 3.7
```

Then you can enter that virtual environment with:
```sh
pipenv shell
```

#### Create a new environment for cmd2 using Conda
```sh
$ conda create -n cmd2_py36 python=3.6
$ conda activate cmd2
```

#### Create a new environment for cmd using Virtualenv
We recommend that you use [pyenv](https://github.com/pyenv/pyenv) to manage your installed python versions.

```sh
# Check pyenv versions installed
pyenv versions

# Install python version defined
pyenv install 3.6.3
```
With the Python version installed, you can set the virtualenv properly. 

```sh
$ cd ~/src/cmd2
$ virtualenv -p $(pyenv root)/versions/3.6.3/ cmd_py36 
$ source ~/src/cmd2/bin/activate
```

Assuming you cloned the repository to `~/src/cmd2` you can install cmd2 in 
[editable mode](https://pip.pypa.io/en/stable/reference/pip_install/#editable-installs).
Changes to the source code are immediately available when the python interpreter
imports `cmd2`, there is no need to re-install the module after every change. This
command will also install all of the runtime dependencies for `cmd2` and modules used for development of `cmd2`:
```sh
$ cd ~/src/cmd2
$ pip install -e .[dev]
```

This project uses many python modules for various development tasks, including
testing, rendering documentation, and building and distributing releases. These
modules can be configured many different ways, which can make it difficult to
learn the specific incantations required for each project you're familiar with.

This project uses `invoke <http://www.pyinvoke.org>` to provide a clean,
high-level interface for these development tasks. To see the full list of functions
available:
```sh
$ invoke -l
```

You can run multiple tasks in a single invocation, for example::
```sh
$ invoke docs sdist wheel
```

That one command will remove all superflous cache, testing, and build
files, render the documentation, and build a source distribution and a
wheel distribution.

If you want to see the details about what `invoke` is doing under the hood,
have a look at `tasks.py`.

Now you can check if everything is installed and working:
```sh
$ cd ~src/cmd2
$ invoke pytest
```

If the tests are executed it means that dependencies and project are installed succesfully.

You can also run the example app and see a prompt that says "(Cmd)" running the command:
```sh
$ python examples/example.py
```

You can type `help` to get help or `quit` to quit. If you see that, then congratulations
– you're all set. Otherwise, refer to the cmd2 [installation instructions](https://cmd2.readthedocs.io/en/latest/overview/installation.html).
There also might be an error in the console of your Bash / terminal / command line
that will help identify the problem.

### Making changes
This bit is up to you!

#### How to find code in the cmd2 codebase to fix/edit

The cmd2 project directory structure is pretty simple and straightforward.  All
actual code for cmd2 is located underneath the `cmd2` directory.  The code to
generate the documentation is in the `docs` directory.  Unit tests are in the
`tests` directory.  The `examples` directory contains examples of how to use
cmd2.  There are various other files in the root directory, but these are
primarily related to continuous integration and release deployment.

#### Changes to the documentation files

If you made changes to any file in the `/docs` directory, you need to build the
Sphinx documentation and make sure your changes look good:
```sh
$ invoke docs
```
In order to see the changes, use your web browser of choice to open `~/cmd2/docs/_build/html/index.html`.

If you would rather use a webserver to view the documentation, including
automatic page refreshes as you edit the files, use:

```sh
$ invoke livehtml
```

You will be shown the IP address and port number where the documents are now
served (usually [http://localhost:8000](http://localhost:8000)).

### Static code analysis

You should have some sort of [PEP 8](https://www.python.org/dev/peps/pep-0008/)-based linting running in your editor or 
IDE or at the command line before you commit code.  `cmd2` uses [flake8](http://flake8.pycqa.org/en/latest/) as part of
its continuous integration (CI) process.  [pylint](https://www.pylint.org) is another good Python linter which can be 
run at the command line but also can integrate with many IDEs and editors.

> Please do not ignore any linting errors in code you write or modify, as they are meant to **help** you and to ensure a clean and simple code base.  Don't worry about linting errors in code you don't touch though - cleaning up the legacy code is a work in progress.

### Running the test suite
When you're ready to share your code, run the test suite:
```sh
$ cd ~/cmd2
$ invoke pytest
```
and ensure all tests pass.

Running the test suite also calculates test code coverage. A summary of coverage
is shown on the screen. A full report is available in `~/cmd2/htmlcov/index.html`.

### Squashing your commits
When you make a pull request, it is preferable for all of your changes to be in one commit.
If you have made more then one commit, then you can _squash_ your commits.
To do this, see [this article](http://forum.freecodecamp.com/t/how-to-squash-multiple-commits-into-one-with-git/13231).

### Creating a pull request

#### What is a pull request?

A pull request (PR) is a method of submitting proposed changes to the cmd2
repo (or any repo, for that matter). You will make changes to copies of the
files which make up cmd2 in a personal fork, then apply to have them
accepted by cmd2 proper.

#### Need help?

GitHub has a good guide on how to contribute to open source [here](https://opensource.guide/how-to-contribute/).

#### Important: ALWAYS EDIT ON A BRANCH

If you take away only one thing from this document, it should be this: Never, **EVER**
make edits to the `master` branch. ALWAYS make a new branch BEFORE you edit
files. This is critical, because if your PR is not accepted, your copy of
master will be forever sullied and the only way to fix it is to delete your
fork and re-fork.

#### Methods

There are two methods of creating a pull request for cmd2:

-   Editing files on a local clone (recommended)
-   Editing files via the GitHub Interface

##### Method 1: Editing via your local fork _(recommended)_

This is the recommended method. Read about [how to set up and maintain a local
instance of cmd2](#maintaining-your-fork).

1.  Perform the maintenance step of rebasing `master`
2.  Ensure you're on the `master` branch using `git status`:

```sh
$ git status
On branch master
Your branch is up-to-date with 'origin/master'.

nothing to commit, working directory clean
```

1.  If you're not on master or your working directory is not clean, resolve
    any outstanding files/commits and checkout master `git checkout master`

2.  Create a branch off of `master` with git: `git checkout -B
    branch/name-here` **Note:** Branch naming is important. Use a name like
    `fix/short-fix-description` or `feature/short-feature-description`. Review
     the [Contribution Guidelines](#contribution-guidelines) for more detail.

3.  Edit your file(s) locally with the editor of your choice

4.  Check your `git status` to see unstaged files

5.  Add your edited files: `git add path/to/filename.ext` You can also do: `git
    add .` to add all unstaged files. Take care, though, because you can
    accidentally add files you don't want added. Review your `git status` first.

6.  Commit your edits: `git commit -m "Brief description of commit"`. Do not add the issue number in the commit message.

7.  Squash your commits, if there are more than one

8.  Push your commits to your GitHub Fork: `git push -u origin branch/name-here`

9.  Go to [Common steps](#common-steps)

##### Method 2: Editing via the GitHub interface

Note: Editing via the GitHub Interface is not recommended, since it is not
possible to update your fork via GitHub's interface without deleting and
recreating your fork.

If you really want to go this route (which isn't recommended), you can Google for more information on
how to do it.

### Common steps

1.  Once the edits have been committed, you will be prompted to create a pull
    request on your fork's GitHub page

2.  By default, all pull requests should be against the cmd2 main repo, `master`
    branch

3.  Submit a pull request from your branch to cmd2's `master` branch

4.  The title (also called the subject) of your PR should be descriptive of your
    changes and succinctly indicate what is being fixed

    -   **Do not add the issue number in the PR title or commit message**

    -   Examples: `Add test cases for Unicode support`; `Correct typo in overview documentation`

5.  In the body of your PR include a more detailed summary of the changes you
    made and why

    -   If the PR is meant to fix an existing bug/issue, then, at the end of
        your PR's description, append the keyword `closes` and #xxxx (where xxxx
        is the issue number). Example: `closes #1337`. This tells GitHub to
        close the existing issue if the PR is merged.

6.  Indicate what local testing you have done (e.g. what OS and version(s) of Python did you run the
    unit test suite with)

7.  Creating the PR causes our continuous integration (CI) systems to automatically run all of the
    unit tests on all supported OSes and all supported versions of Python. You should watch your PR
    to make sure that all unit tests pass on TravisCI (Linux), AppVeyor (Windows), and VSTS (macOS).

8.  If any unit tests fail, you should look at the details and fix the failures. You can then push
    the fix to the same branch in your fork. The PR will automatically get updated and the CI system
    will automatically run all of the unit tests again.


### How we review and merge pull requests

cmd2 has a team of volunteer Maintainers. These Maintainers routinely go through open pull requests in a process called [Quality Assurance](https://en.wikipedia.org/wiki/Quality_assurance) (QA).  We also use multiple continuous
integration (CI) providers to automatically run all of the unit tests on multiple operating systems and versions of Python.

1. If your changes can merge without conflicts and all unit tests pass for all OSes and supported versions of Python,
then your pull request (PR) will have a big green checkbox which says something like "All Checks Passed" next to it.
If this is not the case, there will be a link you can click on to get details regarding what the problem is.
It is your responsibility to make sure all unit tests are passing.  Generally a Maintainer will not QA a
pull request unless it can merge without conflicts and all unit tests pass on all supported platforms.

2. If a Maintainer QA's a pull request and confirms that the new code does what it is supposed to do without seeming to introduce any new bugs,
and doesn't present any backward compatibility issues, they will merge the pull request.

If you would like to apply to join our Maintainer team, message [@tleonhardt](https://github.com/tleonhardt) with links to 5 of your pull requests that have been accepted.


### How we close stale issues

We will close any issues that have been inactive for more than 60 days or pull requests that have been
inactive for more than 30 days, except those that match any of the following criteria:
- bugs that are confirmed
- pull requests that are waiting on other pull requests to be merged
- features that are part of a cmd2 GitHub Milestone or Project

### Next steps

#### If your PR is accepted

Once your PR is accepted, you may delete the branch you created to submit it.
This keeps your working fork clean.

You can do this with a press of a button on the GitHub PR interface. You can
delete the local copy of the branch with: `git branch -D branch/to-delete-name`

#### If your PR is rejected

Don't despair! You should receive solid feedback from the Maintainers as to
why it was rejected and what changes are needed.

Many pull requests, especially first pull requests, require correction or
updating. If you have used the GitHub interface to create your PR, you will need
to close your PR, create a new branch, and re-submit.

If you have a local copy of the repo, you can make the requested changes and
amend your commit with: `git commit --amend` This will update your existing
commit. When you push it to your fork you will need to do a force push to
overwrite your old commit: `git push --force`

Be sure to post in the PR conversation that you have made the requested changes.

### Other resources

-   [PEP 8 Style Guide for Python Code](https://www.python.org/dev/peps/pep-0008/)

-   [Searching for your issue on GitHub](https://help.github.com/articles/searching-issues/)

-   [Creating a new GitHub issue](https://help.github.com/articles/creating-an-issue/)

### Advice

Here is some advice regarding what makes a good pull request (PR) from the perspective of the cmd2 maintainers:
- Multiple smaller PRs divided by topic are better than a single large PR containing a bunch of unrelated changes
- Maintaining backward compatibility is important
- Good unit/functional tests are very important
- Accurate documentation is also important
- Adding new features is of the lowest importance, behind bug fixes, unit test additions/improvements, code cleanup, and documentation
- It's best to create a dedicated branch for a PR, use it only for that PR, and delete it once the PR has been merged
- It's good if the branch name is related to the PR contents, even if it's just "fix123" or "add_more_tests"
- Code coverage of the unit tests matters, so try not to decrease it
- Think twice before adding dependencies to third-party libraries (outside of the Python standard library) because it could affect a lot of users

### Developing in an IDE

We recommend using [Visual Studio Code](https://code.visualstudio.com) with the [Python extension](https://code.visualstudio.com/docs/languages/python) and its [Integrated Terminal](https://code.visualstudio.com/docs/python/debugging) debugger for debugging since it has
excellent support for debugging console applications.

[PyCharm](https://www.jetbrains.com/pycharm/) is also quite good and has very nice [code inspection](https://www.jetbrains.com/help/pycharm/code-inspection.html) capabilities.

## Publishing a new release

Since 0.9.2, the process of publishing a new release of `cmd2` to [PyPi](https://pypi.org/) has been
mostly automated. The manual steps are all git operations. Here's the checklist:

1. Make sure you're on the proper branch (almost always **master**)
1. Make sure all the unit tests pass with `invoke pytest` or `py.test`
1. Make sure `CHANGELOG.md` describes the version and has the correct release date
1. Add a git tag representing the version number using ``invoke tag x.y.z`` 
    * Where x, y, and z are all small non-negative integers
1. (Optional) Run `invoke pypi-test` to clean, build, and upload a new release to [Test PyPi](https://test.pypi.org)
1. Run `invoke pypi` to clean, build, and upload a new release to [PyPi](https://pypi.org/)

## Acknowledgement
Thanks to the good folks at [freeCodeCamp](https://github.com/freeCodeCamp/freeCodeCamp) for creating
an excellent `CONTRIBUTING` file which we have borrowed heavily from.
