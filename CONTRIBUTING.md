# Contributor's Guide

We welcome pull requests from cmd2 users and seasoned Python developers alike! Follow these steps to contribute:

1. Find an issue that needs assistance by searching for the [Help Wanted](https://github.com/python-cmd2/cmd2/labels/help%20wanted) tag.

2. Let us know you are working on it by posting a comment on the issue.

3. Follow the [Contribution Guidelines](#contribution-guidelines) to start working on the issue.

Remember to feel free to ask for help by leaving a comment within the Issue.

Working on your first Pull Request? You can learn how from this *free* series [How to Contribute to an Open Source Project on GitHub](https://egghead.io/series/how-to-contribute-to-an-open-source-project-on-github).

###### If you've found a bug that is not on the board, [follow these steps](#found-a-bug).

--------------------------------------------------------------------------------

## Contribution Guidelines

- [Prerequisites](#prerequisites)
- [Forking The Project](#forking-the-project)
- [Create A Branch](#create-a-branch)
- [Setup Linting](#setup-linting)
- [Setup for cmd2 development](#setup-for-cmd2-development)
- [Make Changes](#make-changes)
- [Run The Test Suite](#run-the-test-suite)
- [Squash Your Commits](#squash-your-commits)
- [Creating A Pull Request](#creating-a-pull-request)
- [Common Steps](#common-steps)
- [How We Review and Merge Pull Requests](#how-we-review-and-merge-pull-requests)
- [How We Close Stale Issues](#how-we-close-stale-issues)
- [Next Steps](#next-steps)
- [Other resources](#other-resources)
- [Advice](#advice)

### Prerequisites

The tables below list all prerequisites along with the minimum required version for each.

> _Updating to the latest releases for all prerequisites via pip or conda is recommended_.

#### Prerequisites to run cmd2 applications

| Prerequisite                                        | Minimum Version |
| --------------------------------------------------- | --------------- |
| [Python](https://www.python.org/downloads/)         | `3.3 or 2.7`    |
| [six](https://pypi.python.org/pypi/six)             | `1.8`           |
| [pyparsing](http://pyparsing.wikispaces.com)        | `2.0.3`         |
| [pyperclip](https://github.com/asweigart/pyperclip) | `1.5`           |

#### Additional prerequisites to run cmd2 unit tests

| Prerequisite                                | Minimum Version |
| ------------------------------------------- | --------------- |
| [pytest](http://doc.pytest.org/en/latest/)  | `2.6.3`         |
| [mock](https://pypi.python.org/pypi/six)    | `1.0.1`         |

### Additional prerequisites to build cmd2 documentation
| Prerequisite                                | Minimum Version |
| ------------------------------------------- | --------------- |
| [sphinx](http://www.sphinx-doc.org)         | `1.2.3`         |
| [sphinx-rtd-theme](https://github.com/snide/sphinx_rtd_theme) | `0.1.6` |

### Optional prerequisites for enhanced unit test features
| Prerequisite                                | Minimum Version |
| ------------------------------------------- | --------------- |
| [pytest-xdist](https://pypi.python.org/pypi/pytest-xdist)| `1.15` |
| [pytest-cov](https://pypi.python.org/pypi/pytest-cov) | `1.8` |

If Python is already installed in your machine, run the following commands to validate the versions:

```shell
python -V
pip freeze | grep six
pip freeze | grep pyparsing
```

If your versions are lower than the prerequisite versions, you should update.

If you do not already have Python installed on your machine, we recommend using the [Anaconda](https://www.continuum.io/downloads) distribution because it provides an excellent out-of-the-box install on all Platforms (Windows, Mac, or Linux) and because it supports having multiple Python environments (versions of Python) installed simultaneously.

### Forking The Project

#### Setting Up Your System

1. Install [Git](https://git-scm.com/) or your favorite Git client.  If you aren't comfortable with Git at the command-line, then both [SmartGit](http://www.syntevo.com/smartgit/) and [GitKraken](https://www.gitkraken.com) are excellent cross-platform graphical Git clients.
2. (Optional) [Setup an SSH Key](https://help.github.com/articles/generating-an-ssh-key/) for GitHub.
3. Create a parent projects directory on your system. For this guide, it will be assumed that it is `~/src`

#### Forking cmd2

1. Go to the top level cmd2 repository: <https://github.com/python-cmd2/cmd2>
2. Click the "Fork" Button in the upper right hand corner of the interface ([More Details Here](https://help.github.com/articles/fork-a-repo/))
3. After the repository has been forked, you will be taken to your copy of the cmd2 repo at `yourUsername/cmd2`

#### Cloning Your Fork

1. Open a Terminal / Command Line / Bash Shell in your projects directory (_i.e.: `/yourprojectdirectory/`_)
2. Clone your fork of cmd2

```shell
$ git clone https://github.com/yourUsername/cmd2.git
```

##### (make sure to replace `yourUsername` with your GitHub Username)

This will download the entire cmd2 repo to your projects directory.

#### Setup Your Upstream

1. Change directory to the new cmd2 directory (`cd cmd2`)
2. Add a remote to the official cmd2 repo:

```shell
$ git remote add upstream https://github.com/python-cmd2/cmd2.git
```

Congratulations, you now have a local copy of the cmd2 repo!

#### Maintaining Your Fork

Now that you have a copy of your fork, there is work you will need to do to keep it current.

##### **Rebasing from Upstream**

Do this prior to every time you create a branch for a PR:

1. Make sure you are on the `master` branch

  > ```shell
  > $ git status
  > On branch master
  > Your branch is up-to-date with 'origin/master'.
  > ```

  > If your aren't on `master`, resolve outstanding files / commits and checkout the `master` branch

  > ```shell
  > $ git checkout master
  > ```

2. Do A Pull with Rebase Against `upstream`

  > ```shell
  > $ git pull --rebase upstream master
  > ```

  > This will pull down all of the changes to the official master branch, without making an additional commit in your local repo.

3. (_Optional_) Force push your updated master branch to your GitHub fork

  > ```shell
  > $ git push origin master --force
  > ```

  > This will overwrite the master branch of your fork.

### Create A Branch

Before you start working, you will need to create a separate branch specific to the issue / feature you're working on. You will push your work to this branch.

#### Naming Your Branch

Name the branch something like `fix/xxx` or `feature/xxx` where `xxx` is a short description of the changes or feature you are attempting to add. For example `fix/script-files` would be a branch where you fix something specific to script files.

#### Adding Your Branch

To create a branch on your local machine (and switch to this branch):

```shell
$ git checkout -b [name_of_your_new_branch]
```

and to push to GitHub:

```shell
$ git push origin [name_of_your_new_branch]
```

##### If you need more help with branching, take a look at _[this](https://github.com/Kunena/Kunena-Forum/wiki/Create-a-new-branch-with-git-and-manage-branches)_.

### Setup Linting

You should have some sort of [PEP8](https://www.python.org/dev/peps/pep-0008/)-based linting running in your editor or IDE or at the command-line before you commit code.  [pylint](https://www.pylint.org) is a good Python linter which can be run at the command-line but also can integrate with many IDEs and editors.

> Please do not ignore any linting errors in code you write or modify, as they are meant to **help** you and to ensure a clean and simple code base.  Don't worry about linting errors in code you don't touch though - cleaning up the legacy code is a work in progress.


### Setup for cmd2 development
Once you have cmd2 cloned, before you start any cmd2 application, you first need to install all of the dependencies:

```bash
# Install cmd2 prerequisites
pip install -U six pyparsing pyperclip

# Install prerequisites for running cmd2 unit tests
pip install -U pytest mock

# Install prerequisites for building cmd2 documentation
pip install -U sphinx sphinx-rtd-theme

# Install optional prerequisites for running unit tests in parallel and doing code coverage analysis
pip install -U pytest-xdist pytest-cov
```

For doing cmd2 development, you actually do NOT want to have cmd2 installed as a Python package.  
So if you have previously installed cmd2, make sure to uninstall it:
```bash
pip uninstall cmd2
```

Then you should modify your PYTHONPATH environment variable to include the directory you have cloned the cmd2 repository to.
Add a line similar to the following to your .bashrc, .bashprofile, or to your Windows environment variables:

```bash
# Use cmd2 Python module from GitHub clone when it isn't installed
export PYTHONPATH=$PYTHONPATH:~/src/cmd2
```

Where `~src/cmd2` is replaced by the directory you cloned your fork of the cmd2 repo to.

Now navigate to your terminal to the directory you cloned your fork of the cmd2 repo to and
try running the example to make sure everything is working:

```bash
cd ~src/cmd2
python examples/example.py
```

If the example app loads, you should see a prompt that says "(Cmd)".  You can type `help` to get help or `quit` to quit.
If you see that, then congratulations – you're all set. Otherwise, refer to the cmd2 [Installation Instructions](https://cmd2.readthedocs.io/en/latest/install.html#installing).  There also might be an error in the console
of  your Bash / Terminal / Command Line that will help identify the problem.

### Make Changes
This bit is up to you!

#### How to find the code in the cmd2 codebase to fix/edit?

The cmd2 project directory structure is pretty simple and straightforward.  All actual code for cmd2
is located in a single file, `cmd2.py`.  The code to generate the documentation is in the `docs` directory.  Unit tests are in the `tests` directory.  The `examples` directory contains examples of how
to use cmd2.  There are various other files in the root directory, but these are primarily related to
continuous integration and to release deployment.

#### Changes to the documentation files
If you made changes to any file in the `/docs` directory, you need to build the Sphinx documentation
and make sure your changes look good:
```shell
cd docs
make clean html
```
In order to see the changes, use your web browser of choice to open `<cmd2>/docs/_build/html/index.html`.

### Run The Test Suite
When you're ready to share your code, run the test suite:

```shell
cd <cmd2>
py.test
```

and ensure all tests pass.

If you have the `pytest-xdist` pytest distributed testing plugin installed, then you can use it to
dramatically speed up test execution by running tests in parallel on multiple cores like so:

```shell
py.test -n4
```
where `4` should be replaced by the number of parallel threads you wish to run for testing.

#### Measuring code coverage

Code coverage can be measured as follows:

```shell
py.test -nauto --cov=cmd2 --cov-report=term-missing --cov-report=html
```

Then use your web browser of choice to look at the results which are in `<cmd2>/htmlcov/index.html`.

### Squash Your Commits
When you make a pull request, it is preferable for all of your changes to be in one commit.

If you have made more then one commit, then you will can _squash_ your commits.

To do this, see [Squashing Your Commits](http://forum.freecodecamp.com/t/how-to-squash-multiple-commits-into-one-with-git/13231).

### Creating A Pull Request

#### What is a Pull Request?

A pull request (PR) is a method of submitting proposed changes to the cmd2
Repo (or any Repo, for that matter). You will make changes to copies of the
files which make up cmd2 in a personal fork, then apply to have them
accepted by cmd2 proper.

#### Need Help?

GitHub has a good guide on how to contribute to open source [here](https://opensource.guide/how-to-contribute/).

#### Important: ALWAYS EDIT ON A BRANCH

Take away only one thing from this document, it should be this: Never, **EVER**
make edits to the `master` branch. ALWAYS make a new branch BEFORE you edit
files. This is critical, because if your PR is not accepted, your copy of
master will be forever sullied and the only way to fix it is to delete your
fork and re-fork.

#### Methods

There are two methods of creating a pull request for cmd2:

-   Editing files on a local clone (recommended)
-   Editing files via the GitHub Interface

##### Method 1: Editing via your Local Fork _(Recommended)_

This is the recommended method. Read about [How to Setup and Maintain a Local
Instance of cmd2](#maintaining-your-fork).

1.  Perform the maintenance step of rebasing `master`.
2.  Ensure you are on the `master` branch using `git status`:

```bash
$ git status
On branch master
Your branch is up-to-date with 'origin/master'.

nothing to commit, working directory clean
```

1.  If you are not on master or your working directory is not clean, resolve
    any outstanding files/commits and checkout master `git checkout master`

2.  Create a branch off of `master` with git: `git checkout -B
    branch/name-here` **Note:** Branch naming is important. Use a name like
    `fix/short-fix-description` or `feature/short-feature-description`. Review
     the [Contribution Guidelines](#contribution-guidelines) for more detail.

3.  Edit your file(s) locally with the editor of your choice

4.  Check your `git status` to see unstaged files.

5.  Add your edited files: `git add path/to/filename.ext` You can also do: `git
    add .` to add all unstaged files. Take care, though, because you can
    accidentally add files you don't want added. Review your `git status` first.

6.  Commit your edits: `git commit -m "Brief Description of Commit"`. Do not add the issue number in the commit message.

7.  Squash your commits, if there are more than one.

8.  Push your commits to your GitHub Fork: `git push -u origin branch/name-here`

9.  Go to [Common Steps](#common-steps)

##### Method 2: Editing via the GitHub Interface

Note: Editing via the GitHub Interface is not recommended, since it is not
possible to update your fork via GitHub's interface without deleting and
recreating your fork.

If you really want to go this route which isn't recommended, you can Google for more information on
how to do it.

### Common Steps

1.  Once the edits have been committed, you will be prompted to create a pull
    request on your fork's GitHub Page.

2.  By default, all pull requests should be against the cmd2 main repo, `master`
    branch.

3.  Submit a pull request from your branch to cmd2's `master` branch.

4.  The title (also called the subject) of your PR should be descriptive of your
    changes and succinctly indicates what is being fixed.

    -   **Do not add the issue number in the PR title or commit message.**

    -   Examples: `Add Test Cases for Unicode Support` `Correct typo in Overview documentation`

5.  In the body of your PR include a more detailed summary of the changes you
    made and why.

    -   If the PR is meant to fix an existing bug/issue, then, at the end of
        your PR's description, append the keyword `closes` and #xxxx (where xxxx
        is the issue number). Example: `closes #1337`. This tells GitHub to
        close the existing issue, if the PR is merged.

6.  Indicate what local testing you have done (e.g. what OS and version(s) of Python did you run the
    unit test suite with)
    
7.  Creating the PR causes our continuous integration (CI) systems to automatically run all of the
    unit tests on all supported OSes and all supported versions of Python.  You should watch your PR
    to make sure that all unit tests pass on Both TravisCI (Linux) and AppVeyor (Windows).  
    
8.  If any unit tests fail, you should look at the details and fix the failures.  You can then push
    the fix to the same branch in your fork and the PR will automatically get updated and the CI system
    will automatically run all of the unit tests again.


### How We Review and Merge Pull Requests

cmd2 has a team of volunteer Maintainers. These Maintainers routinely go through open pull requests in a process called [Quality Assurance](https://en.wikipedia.org/wiki/Quality_assurance) (QA).  We also utilize multiple continuous
integration (CI) providers to automatically run all of the unit tests on multiple operating systems and versions of Python.

1. If your changes can merge without conflicts and all unit tests pass for all OSes and supported versions of Python,
then your pull request (PR) will have a big green checkbox which says something like "All Checks Passed" next to it.
If this is not the case, there will be a link you can click on to get details regarding what the problem is.  
It is your responsibility to make sure all unit tests are passing.  Generally a Maintainer will not QA a
pull request unless it can merge without conflicts and all unit tests pass on all supported platforms.

2. If a Maintainer QA's a pull request and confirms that the new code does what it is supposed to do without seeming to introduce any new bugs,
and doesn't present any backward compatibility issues, they will merge the pull request.

If you would like to apply to join our Maintainer team, message [@tleonhardt](https://github.com/tleonhardt) with links to 5 of your pull requests that have been accepted.


### How We Close Stale Issues

We will close any issues that have been inactive for more than 60 days or pull requests that have been
inactive for more than 30 days, except those that match the following criteria:
- bugs that are confirmed
- pull requests that are waiting on other pull requests to be merged
- features that are part of a cmd2 GitHub Milestone or Project

### Next Steps

#### If your PR is accepted

Once your PR is accepted, you may delete the branch you created to submit it.
This keeps your working fork clean.

You can do this with a press of a button on the GitHub PR interface. You can
delete the local copy of the branch with: `git branch -D branch/to-delete-name`

#### If your PR is rejected

Don't despair! You should receive solid feedback from the Maintainers as to
why it was rejected and what changes are needed.

Many Pull Requests, especially first Pull Requests, require correction or
updating. If you have used the GitHub interface to create your PR, you will need
to close your PR, create a new branch, and re-submit.

If you have a local copy of the repo, you can make the requested changes and
amend your commit with: `git commit --amend` This will update your existing
commit. When you push it to your fork you will need to do a force push to
overwrite your old commit: `git push --force`

Be sure to post in the PR conversation that you have made the requested changes.

### Other resources

-   [PEP8 Style Guide for Python Code](https://www.python.org/dev/peps/pep-0008/)

-   [Searching for Your Issue on GitHub](https://help.github.com/articles/searching-issues/)

-   [Creating a New GitHub Issue](https://help.github.com/articles/creating-an-issue/)

### Advice

Here is some advice regarding what makes a good pull request (PR) from the perspective of the cmd2 maintainers:
- Multiple smaller PRs divided by topic are better than a single large PR containing a bunch of unrelated changes
- Maintaining backward compatibility is important
- Good unit/functional tests are very important
- Accurate documentation is also important
- Adding new features is of the lowest importance, behind bug fixes, unit test additions/improvements, code cleanup, and documentation
- It's best to create a dedicated branch for a PR and use it only for that PR (and delete it once the PR has been merged)
- It's good if the branch name is related to the PR contents, even if it's just "fix123" or "add_more_tests"
- Code coverage of the unit tests matters, try not to decrease it
- Think twice before adding dependencies to 3rd party libraries (outside of the Python standard library) because it could affect a lot of users

### Acknowledgement
Thanks to the good folks at [freeCodeCamp](https://github.com/freeCodeCamp/freeCodeCamp) for creating
an excellent `CONTRIBUTING` file which we have borrowed heavily from.
