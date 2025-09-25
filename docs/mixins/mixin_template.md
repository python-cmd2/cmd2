# cmd2 Mixin Template

## Mixin Classes in General

In Python, a mixin is a class designed to provide a specific set of functionalities to other classes
through multiple inheritance. Mixins are not intended to be instantiated on their own; rather, they
serve as a way to "mix in" or compose behaviors into a base class without creating a rigid "is-a"
relationship.

For more information about Mixin Classes, we recommend this `Real Python` article on
[What Are Mixin Classes in Python?](https://realpython.com/python-mixin/).

## Overview of cmd2 mixins

If you have some set of re-usable behaviors that you wish to apply to multiple different `cmd2`
applications, then creating a mixin class to encapsulate this behavior can be a great idea. It is
one way to extend `cmd2` by relying on multiple inheritance. It is quick and easy, but there are
some potential pitfalls you should be aware of so you know how to do it correctly.

The [mixins.py](https://github.com/python-cmd2/cmd2/blob/main/examples/mixins.py) example is a
general example that shows you how you can develop a mixin class for `cmd2` applicaitons. In the
past we have referred to these as "Plugins", but in retrospect that probably isn't the best name for
them. They are generally mixin classes that add some extra functionality to your class which
inherits from [cmd2.Cmd][].

## Using this template

This file provides a very basic template for how you can create your own cmd2 Mixin class to
encapsulate re-usable behavior that can be applied to multiple `cmd2` applications via multiple
inheritance.

## Naming

If you decide to publish your Mixin as a Python package, you should consider prefixing the name of
your project with `cmd2-`. If you take this approach, then within that project, you should have a
package with a prefix of `cmd2_`.

## Adding functionality

There are many ways to add functionality to `cmd2` using a mixin. A mixin is a class that
encapsulates and injects code into another class. Developers who use a mixin in their `cmd2`
project, will inject the mixin's code into their subclass of [cmd2.Cmd][].

### Mixin and Initialization

The following short example shows how to create a mixin class and how everything gets initialized.

Here's the mixin:

```python
class MyMixin:
    def __init__(self, *args, **kwargs):
        # code placed here runs before cmd2.Cmd initializes
        super().__init__(*args, **kwargs)
        # code placed here runs after cmd2.Cmd initializes
```

and an example app which uses the mixin:

```python
import cmd2


class Example(MyMixin, cmd2.Cmd):
    """A cmd2 application class to show how to use a mixin class."""

    def __init__(self, *args, **kwargs):
        # code placed here runs before cmd2.Cmd or
        # any mixins initialize
        super().__init__(*args, **kwargs)
        # code placed here runs after cmd2.Cmd and
        # all mixins have initialized
```

Note how the mixin must be inherited (or mixed in) before `cmd2.Cmd`. This is required for two
reasons:

- The `cmd.Cmd.__init__()` method in the python standard library does not call `super().__init__()`.
  Because of this oversight, if you don't inherit from `MyMixin` first, the `MyMixin.__init__()`
  method will never be called.
- You may want your mixin to be able to override methods from `cmd2.Cmd`. If you mixin the mixin
  class after `cmd2.Cmd`, the python method resolution order will call `cmd2.Cmd` methods before it
  calls those in your mixin.

### Add commands

Your mixin can add user visible commands. You do it the same way in a mixin that you would in a
`cmd2.Cmd` app:

```python
class MyMixin:

    def do_say(self, statement):
        """Simple say command"""
        self.poutput(statement)
```

You have all the same capabilities within the mixin that you do inside a `cmd2.Cmd` app, including
argument parsing via decorators and custom help methods.

### Add (or hide) settings

A mixin may add user controllable settings to the application. Here's an example:

```python
class MyMixin:
    def __init__(self, *args, **kwargs):
        # code placed here runs before cmd2.Cmd initializes
        super().__init__(*args, **kwargs)
        # code placed here runs after cmd2.Cmd initializes
        self.mysetting = 'somevalue'
        self.settable.update({'mysetting': 'short help message for mysetting'})
```

You can also hide settings from the user by removing them from `self.settable`.

### Decorators

Your mixin can provide a decorator which users of your mixin can use to wrap functionality around
their own commands.

### Override methods

Your mixin can override core `cmd2.Cmd` methods, changing their behavior. This approach should be
used sparingly, because it is very brittle. If a developer chooses to use multiple mixins in their
application, and several of the mixins override the same method, only the first mixin to be mixed in
will have the overridden method called.

Hooks are a much better approach.

### Hooks

Mixins can register hooks, which are called by `cmd2.Cmd` during various points in the application
and command processing lifecycle. Mixins should not override any of the legacy `cmd` hook methods,
instead they should register their hooks as
[described](https://cmd2.readthedocs.io/en/latest/hooks.html) in the `cmd2` documentation.

You should name your hooks so that they begin with the name of your mixin. Hook methods get mixed
into the `cmd2` application and this naming convention helps avoid unintentional method overriding.

Here's a simple example:

```python
class MyMixin:

    def __init__(self, *args, **kwargs):
        # code placed here runs before cmd2 initializes
        super().__init__(*args, **kwargs)
        # code placed here runs after cmd2 initializes
        # this is where you register any hook functions
        self.register_postparsing_hook(self.cmd2_mymixin_postparsing_hook)

    def cmd2_mymixin_postparsing_hook(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """Method to be called after parsing user input, but before running the command"""
        self.poutput('in postparsing_hook')
        return data
```

Registration allows multiple mixins (or even the application itself) to each inject code to be
called during the application or command processing lifecycle.

See the [cmd2 hook documentation](https://cmd2.readthedocs.io/en/latest/hooks.html) for full details
of the application and command lifecycle, including all available hooks and the ways hooks can
influence the lifecycle.

### Classes and Functions

Your mixin can also provide classes and functions which can be used by developers of `cmd2` based
applications. Describe these classes and functions in your documentation so users of your mixin will
know what's available.
