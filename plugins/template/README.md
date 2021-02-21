# cmd2 Plugin Template

## Table of Contents

- [Using this template](#using-this-template)
- [Naming](#naming)
- [Adding functionality](#adding-functionality)
- [Examples](#examples)
- [Development Tasks](#development-tasks)
- [Packaging and Distribution](#packaging-and-distribution)
- [License](#license)


## Using this template

This template assumes you are creating a new cmd2 plugin called `myplugin`. Your
plugin will have a different name. You will need to rename some of the files and
directories in this template. Don't forget to modify the imports and `setup.py`.

You'll probably also want to rewrite the README :)


## Naming

You should prefix the name of your project with `cmd2-`. Within that project,
you should have a package with a prefix of `cmd2_`.


## Adding functionality

There are many ways to add functionality to `cmd2` using a plugin. Most plugins
will be implemented as a mixin. A mixin is a class that encapsulates and injects
code into another class. Developers who use a plugin in their `cmd2` project,
will inject the plugin's code into their subclass of `cmd2.Cmd`.


### Mixin and Initialization

The following short example shows how to mix in a plugin and how the plugin
gets initialized.

Here's the plugin:

```python
class MyPlugin:
    def __init__(self, *args, **kwargs):
        # code placed here runs before cmd2.Cmd initializes
        super().__init__(*args, **kwargs)
        # code placed here runs after cmd2.Cmd initializes
```

and an example app which uses the plugin:

```python
import cmd2
import cmd2_myplugin

class Example(cmd2_myplugin.MyPlugin, cmd2.Cmd):
    """An class to show how to use a plugin"""
    def __init__(self, *args, **kwargs):
        # code placed here runs before cmd2.Cmd or
        # any plugins initialize
        super().__init__(*args, **kwargs)
        # code placed here runs after cmd2.Cmd and
        # all plugins have initialized
```

Note how the plugin must be inherited (or mixed in) before `cmd2.Cmd`. This is
required for two reasons:

- The `cmd.Cmd.__init__()` method in the python standard library does not call
  `super().__init__()`. Because of this oversight, if you don't inherit from `MyPlugin` first, the
  `MyPlugin.__init__()` method will never be called.
- You may want your plugin to be able to override methods from `cmd2.Cmd`.
  If you mixin the plugin after `cmd2.Cmd`, the python method resolution order
  will call `cmd2.Cmd` methods before it calls those in your plugin.


### Add commands

Your plugin can add user visable commands. You do it the same way in a plugin
that you would in a `cmd2.Cmd` app:

```python
class MyPlugin:

    def do_say(self, statement):
        """Simple say command"""
        self.poutput(statement)
```

You have all the same capabilities within the plugin that you do inside a
`cmd2.Cmd` app, including argument parsing via decorators and custom help
methods.

### Add (or hide) settings

A plugin may add user controllable settings to the application. Here's an
example:

```python
class MyPlugin:
    def __init__(self, *args, **kwargs):
        # code placed here runs before cmd2.Cmd initializes
        super().__init__(*args, **kwargs)
        # code placed here runs after cmd2.Cmd initializes
        self.mysetting = 'somevalue'
        self.settable.update({'mysetting': 'short help message for mysetting'})
```

You can also hide settings from the user by removing them from `self.settable`.

### Decorators

Your plugin can provide a decorator which users of your plugin can use to wrap
functionality around their own commands.

### Override methods

Your plugin can override core `cmd2.Cmd` methods, changing their behavior.
This approach should be used sparingly, because it is very brittle. If a
developer chooses to use multiple plugins in their application, and several of
the plugins override the same method, only the first plugin to be mixed in
will have the overridden method called.

Hooks are a much better approach.

### Hooks

Plugins can register hooks, which are called by `cmd2.Cmd` during various points
in the application and command processing lifecycle. Plugins should not override
any of the deprecated hook methods, instead they should register their hooks as
[described](https://cmd2.readthedocs.io/en/latest/hooks.html) in the cmd2
documentation.

You should name your hooks so that they begin with the name of your plugin. Hook
methods get mixed into the `cmd2` application and this naming convention helps
avoid unintentional method overriding.


Here's a simple example:

```python
class MyPlugin:

    def __init__(self, *args, **kwargs):
        # code placed here runs before cmd2 initializes
        super().__init__(*args, **kwargs)
        # code placed here runs after cmd2 initializes
        # this is where you register any hook functions
        self.register_postparsing_hook(self.cmd2_myplugin_postparsing_hook)

    def cmd2_myplugin_postparsing_hook(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """Method to be called after parsing user input, but before running the command"""
        self.poutput('in postparsing_hook')
        return data
```

Registration allows multiple plugins (or even the application itself) to each inject code
to be called during the application or command processing lifecycle.

See the [cmd2 hook documentation](https://cmd2.readthedocs.io/en/latest/hooks.html)
for full details of the application and command lifecycle, including all
available hooks and the ways hooks can influence the lifecycle.


### Classes and Functions

Your plugin can also provide classes and functions which can be used by
developers of cmd2 based applications. Describe these classes and functions in
your documentation so users of your plugin will know what's available.


## Examples

Include an example or two in the `examples` directory which demonstrate how your
plugin works. This will help developers utilize it from within their
application.


## Development Tasks

This project uses many other python modules for various development tasks,
including testing, linting, building wheels, and distributing releases. These
modules can be configured many different ways, which can make it difficult to
learn the specific incantations required for each project you are familiar with.

This project uses [invoke](<http://www.pyinvoke.org>) to provide a clean,
high level interface for these development tasks. To see the full list of
functions available:
```
$ invoke -l
```

You can run multiple tasks in a single invocation, for example:
```
$ invoke clean docs sdist wheel
```

That one command will remove all superflous cache, testing, and build
files, render the documentation, and build a source distribution and a
wheel distribution.

For more information, read `tasks.py`.

While developing your plugin, you should make sure you support all versions of
python supported by cmd2, and all supported platforms. cmd2 uses a three
tiered testing strategy to accomplish this objective.

- [pytest](https://pytest.org) runs the unit tests
- [nox](https://nox.thea.codes/en/stable/) runs the unit tests on multiple versions
  of python
- [GitHub Actions](https://github.com/features/actions) runs the tests on the various 
  supported platforms

This plugin template is set up to use the same strategy.


### Create python environments

This project uses [nox](https://nox.thea.codes/en/stable/) to run the test
suite against multiple python versions. I recommend
[pyenv](https://github.com/pyenv/pyenv) with the
[pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv>) plugin to manage
these various versions. If you are a Windows user, `pyenv` won't work for you,
but [conda](https://conda.io/) can also be used to solve this problem.

This distribution includes a shell script `build-pyenvs.sh` which
automates the creation of these environments.

If you prefer to create these virtualenvs by hand, do the following:
```
$ cd cmd2_abbrev
$ pyenv install 3.7.0
$ pyenv virtualenv -p python3.7 3.7.0 cmd2-3.7
$ pyenv install 3.6.5
$ pyenv virtualenv -p python3.6 3.6.5 cmd2-3.6
$ pyenv install 3.8.5
$ pyenv virtualenv -p python3.8 3.8.5 cmd2-3.8
$ pyenv install 3.9.0
$ pyenv virtualenv -p python3.9 3.9.0 cmd2-3.9
```

Now set pyenv to make all three of those available at the same time:
```
$ pyenv local cmd2-3.7 cmd2-3.6 cmd2-3.8 cmd2-3.9
```

Whether you ran the script, or did it by hand, you now have isolated virtualenvs
for each of the major python versions. This table shows various python commands,
the version of python which will be executed, and the virtualenv it will
utilize.

| Command     | python | virtualenv |
| ----------- | ------ | ---------- |
| `python`    | 3.7.0  | cmd2-3.6   |
| `python3`   | 3.7.0  | cmd2-3.6   |
| `python3.7` | 3.7.0  | cmd2-3.7   |
| `python3.6` | 3.6.5  | cmd2-3.6   |
| `python3.8` | 3.8.5  | cmd2-3.8   |
| `python3.9` | 3.9.0  | cmd2-3.9   |
| `pip`       | 3.7.0  | cmd2-3.6   |
| `pip3`      | 3.7.0  | cmd2-3.6   |
| `pip3.7`    | 3.7.0  | cmd2-3.7   |
| `pip3.6`    | 3.6.5  | cmd2-3.6   |
| `pip3.8`    | 3.8.5  | cmd2-3.8   |
| `pip3.9`    | 3.9.0  | cmd2-3.9   |

## Install Dependencies

Install all the development dependencies:
```
$ pip install -e .[dev]
```

This command also installs `cmd2-myplugin` "in-place", so the package points to
the source code instead of copying files to the python `site-packages` folder.

All the dependencies now have been installed in the `cmd2-3.7`
virtualenv. If you want to work in other virtualenvs, you'll need to manually
select it, and install again::

   $ pyenv shell cmd2-3.4
   $ pip install -e .[dev]

Now that you have your python environments created, you need to install the
package in place, along with all the other development dependencies:
```
$ pip install -e .[dev]
```


### Running unit tests

Run `invoke pytest` from the top level directory of your plugin to run all the
unit tests found in the `tests` directory.


### Use nox to run unit tests in multiple versions of python

The included `noxfile.py` is setup to run the unit tests in python 3.6, 3.7, 3.8,
and 3.9. You can run your unit tests in all of these versions of python by:
```
$ nox
```


### Run unit tests on multiple platforms

[GitHub Actions](https://github.com/features/actions) offers free plans for open source projects


## Packaging and Distribution

When creating your `setup.py` file, keep the following in mind:

- use the keywords `cmd2 plugin` to make it easier for people to find your plugin
- since cmd2 uses semantic versioning, you should use something like
  `install_requires=['cmd2 >= 0.9.4, <=2']` to make sure that your plugin
  doesn't try and run with a future version of `cmd2` with which it may not be
  compatible


## License

cmd2 [uses the very liberal MIT license](https://github.com/python-cmd2/cmd2/blob/master/LICENSE).
We invite plugin authors to consider doing the same.
