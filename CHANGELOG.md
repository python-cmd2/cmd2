## 2.1.2 (July 5, 2021)
* Enhancements
    * Added the following accessor methods for cmd2-specific attributes to the `argparse.Action` class
        * `get_choices_callable()`
        * `set_choices_provider()`
        * `set_completer()`
        * `get_descriptive_header()`
        * `set_descriptive_header()`
        * `get_nargs_range()`
        * `set_nargs_range()`
        * `get_suppress_tab_hint()`
        * `set_suppress_tab_hint()`
* Deprecations
    * Now that `set_choices_provider()` and `set_completer()` have been added as methods to the
      `argparse.Action` class, the standalone functions of the same name will be removed in version
      2.2.0. To update to the new convention, do the following:
        * Change `set_choices_provider(action, provider)` to `action.set_choices_provider(provider)`
        * Change `set_completer(action, completer)` to `action.set_completer(completer)`

## 2.1.1 (June 17, 2021)
* Bug Fixes
   * Fixed handling of argparse's default options group name which was changed in Python 3.10
* Enhancements
    * Restored `plugins` and `tests_isolated` directories to tarball published to PyPI for `cmd2` release

## 2.1.0 (June 14, 2021)
* Enhancements
   * Converted persistent history files from pickle to compressed JSON

## 2.0.1 (June 7, 2021)
* Bug Fixes
  * Exclude `plugins` and `tests_isolated` directories from tarball published to PyPI for `cmd2` release

## 2.0.0 (June 6, 2021)
* Bug Fixes
  * Fixed issue where history indexes could get repeated
  * Fixed issue where TableCreator was tossing blank last line
  * Corrected help text for alias command
* Breaking Changes
    * `cmd2` 2.0 supports Python 3.6+ (removed support for Python 3.5)
    * Argparse Completion / Settables
        * Replaced `choices_function` / `choices_method` with `choices_provider`.
        * Replaced `completer_function` / `completer_method` with `completer`.
        * ArgparseCompleter now always passes `cmd2.Cmd` or `CommandSet` instance as the first positional
        argument to choices_provider and completer functions.
    * Moved `basic_complete` from utils into `cmd2.Cmd` class.
    * Moved `CompletionError` to exceptions.py
    * ``Namespace.__statement__`` has been removed. Use `Namespace.cmd2_statement.get()` instead.
    * Removed `--silent` flag from `alias/macro create` since startup scripts can be run silently.
    * Removed `--with_silent` flag from `alias/macro list` since startup scripts can be run silently.
    * Removed `with_argparser_and_unknown_args` since it was deprecated in 1.3.0.
    * Renamed `silent_startup_script` to `silence_startup_script` for clarity.
    * Replaced `cmd2.Cmd.completion_header` with `cmd2.Cmd.formatted_completions`. See Enhancements
      for description of this new class member.
    * Settables now have new initialization parameters. It is now a required parameter to supply the reference to the
      object that holds the settable attribute. `cmd2.Cmd.settables` is no longer a public dict attribute - it is now a
      property that aggregates all Settables across all registered CommandSets.
    * Failed transcript testing now sets self.exit_code to 1 instead of -1.
    * Renamed `use_ipython` keyword parameter of `cmd2.Cmd.__init__()` to `include_ipy`.
    * `py` command is only enabled if `include_py` parameter is `True`. See Enhancements for a description
      of this parameter.
    * Removed ability to run Python commands from the command line with `py`. Now `py` takes no arguments
      and just opens an interactive Python shell.
    * Changed default behavior of `runcmds_plus_hooks()` to not stop when Ctrl-C is pressed and instead
      run the next command in its list.
    * Removed `cmd2.Cmd.quit_on_sigint` flag, which when `True`, quit the application when Ctrl-C was pressed at the prompt.
    * The history bug fix resulted in structure changes to the classes in `cmd2.history`. Therefore, persistent history
      files created with versions older than 2.0.0 are not compatible.
* Enhancements
    * Added support for custom tab completion and up-arrow input history to `cmd2.Cmd2.read_input`.
      See [read_input.py](https://github.com/python-cmd2/cmd2/blob/master/examples/read_input.py)
      for an example.
    * Added `cmd2.exceptions.PassThroughException` to raise unhandled command exceptions instead of printing them.
    * Added support for ANSI styles and newlines in tab completion results using `cmd2.Cmd.formatted_completions`.
      `cmd2` provides this capability automatically if you return argparse completion matches as `CompletionItems`.
    * Settables enhancements:
        * Settables may be optionally scoped to a CommandSet. Settables added to CommandSets will appear when a
          CommandSet is registered and disappear when a CommandSet is unregistered. Optionally, scoped Settables
          may have a prepended prefix.
        * Settables now allow changes to be applied to any arbitrary object attribute. It no longer needs to match an
          attribute added to the cmd2 instance itself.
    * Raising ``SystemExit`` or calling ``sys.exit()`` in a command or hook function will set ``self.exit_code``
      to the exit code used in those calls. It will also result in the command loop stopping.
    * ipy command now includes all of `self.py_locals` in the IPython environment
    * Added `include_py` keyword parameter to `cmd2.Cmd.__init__()`. If `False`, then the `py` command will
      not be available. Defaults to `False`. `run_pyscript` is not affected by this parameter.
    * Made the amount of space between columns in a SimpleTable configurable
    * On POSIX systems, shell commands and processes being piped to are now run in the user's preferred shell
      instead of /bin/sh. The preferred shell is obtained by reading the SHELL environment variable. If that
      doesn't exist or is empty, then /bin/sh is used.
    * Changed `cmd2.Cmd._run_editor()` to the public method `cmd2.Cmd.run_editor()`

## 1.5.0 (January 31, 2021)
* Bug Fixes
    * Fixed bug where setting `always_show_hint=True` did not show a hint when completing `Settables`
    * Fixed bug in editor detection logic on Linux systems that do not have `which`
    * Fixed bug in table creator where column headers with tabs would result in an incorrect width calculation
    * Fixed `FileNotFoundError` which occurred when running `history --clear` and no history file existed.
* Enhancements
    * Added `silent_startup_script` option to `cmd2.Cmd.__init__()`. If `True`, then the startup script's
      output will be suppressed. Anything written to stderr will still display.
    * cmd2 now uses pyreadline3 when running Python 3.8 or greater on Windows
* Notes
    * This is the last release planned to support Python 3.5

## 1.4.0 (November 11, 2020)
* Bug Fixes
    * Fixed tab completion crash on Windows
* Enhancements
    * Changed how multiline doc string help is formatted to match style of other help messages

## 1.3.11 (October 1, 2020)
* Bug Fixes
    * Fixed issue where quoted redirectors and terminators in aliases and macros were not being
    restored when read from a startup script.
    * Fixed issue where instantiating more than one cmd2-based class which uses the `@as_subcommand_to`
    decorator resulted in duplicated help text in the base command the subcommands belong to.

## 1.3.10 (September 17, 2020)
* Enhancements
    * Added user-settable option called `always_show_hint`. If True, then tab completion hints will always
    display even when tab completion suggestions print. Arguments whose help or hint text is suppressed will
    not display hints even when this setting is True.
    * argparse tab completion now groups flag names which run the same action. Optional flags are wrapped
    in brackets like it is done in argparse usage text.
    * default category decorators are now heritable by default and will propagate the category down the
    class hierarchy until overridden. There's a new optional flag to set heritable to false.
    * Added `--silent` flag to `alias/macro create`. If used, then no confirmation message will be printed
    when aliases and macros are created or overwritten.
    * Added `--with_silent` flag to `alias/macro list`. Use this option when saving to a startup script
    that should silently create aliases and macros.
* Bug Fixes
    * Fixed issue where flag names weren't always sorted correctly in argparse tab completion

## 1.3.9 (September 03, 2020)
* Breaking Changes
    * `CommandSet.on_unregister()` is now called as first step in unregistering a `CommandSet` and not
    the last. `CommandSet.on_unregistered()` is now the last step.
* Enhancements
    * Added `CommandSet.on_registered()`. This is called by `cmd2.Cmd` after a `CommandSet` is registered
    and all its commands have been added to the CLI.
    * Added `CommandSet.on_unregistered()`. This is called by `cmd2.Cmd` after a `CommandSet` is unregistered
    and all its commands have been removed from the CLI.

## 1.3.8 (August 28, 2020)
* Bug Fixes
    * Fixed issue where subcommand added with `@as_subcommand_to` decorator did not display help
    when called with `-h/--help`.
* Enhancements
    * `add_help=False` no longer has to be passed to parsers used in `@as_subcommand_to` decorator.
      Only pass this if your subcommand should not have the `-h/--help` help option (as stated in
      argparse documentation).

## 1.3.7 (August 27, 2020)
* Bug Fixes
    * Fixes an issue introduced in 1.3.0 with processing command strings containing terminator/separator 
      character(s) that are manually passed to a command that uses argparse.

## 1.3.6 (August 27, 2020)
* Breaking changes
    * The functions cmd2 adds to Namespaces (`get_statement()` and `get_handler()`) are now 
    `Cmd2AttributeWrapper` objects named `cmd2_statement` and `cmd2_handler`. This makes it
    easy to filter out which attributes in an `argparse.Namespace` were added by `cmd2`.
* Deprecations
    * ``Namespace.__statement__`` will be removed in `cmd2` 2.0.0. Use `Namespace.cmd2_statement.get()`
    going forward.

## 1.3.5 (August 25, 2020)
* Bug Fixes
    * Fixed `RecursionError` when printing an `argparse.Namespace` caused by custom attribute cmd2 was adding
* Enhancements
    * Added `get_statement()` function to `argparse.Namespace` which returns `__statement__` attribute

## 1.3.4 (August 20, 2020)
* Bug Fixes
    * Fixed `AttributeError` when `CommandSet` that uses `as_subcommand_to` decorator is loaded during
    `cmd2.Cmd.__init__()`.
* Enhancements
    * Improved exception messages when using mock without `spec=True`.
    See [testing](https://cmd2.readthedocs.io/en/latest/testing.html) documentation for more details on testing
    cmd2-based applications with mock.

## 1.3.3 (August 13, 2020)
* Breaking changes
    * CommandSet command functions (do_, complete_, help_) will no longer have the cmd2 app
      passed in as the first parameter after `self` since this is already a class member.
    * Renamed `install_command_set()` and `uninstall_command_set()` to `register_command_set()` and 
      `unregister_command_set()` for better name consistency.
* Bug Fixes
    * Fixed help formatting bug in `Cmd2ArgumentParser` when `metavar` is a tuple
    * Fixed tab completion bug when using `CompletionItem` on an argument whose `metavar` is a tuple
    * Added explicit testing against python 3.5.2 for Ubuntu 16.04, and 3.5.3 for Debian 9
    * Added fallback definition of typing.Deque (taken from 3.5.4)
    * Removed explicit type hints that fail due to a bug in 3.5.2 favoring comment-based hints instead
    * When passing a ns_provider to an argparse command, will now attempt to resolve the correct
      CommandSet instance for self. If not, it'll fall back and pass in the cmd2 app
* Other 
    * Added missing doc-string for new cmd2.Cmd __init__ parameters 
      introduced by CommandSet enhancement

## 1.3.2 (August 10, 2020)
* Bug Fixes
    * Fixed `prog` value of subcommands added with `as_subcommand_to()` decorator.
    * Fixed missing settings in subcommand parsers created with `as_subcommand_to()` decorator. These settings
      include things like description and epilog text.
    * Fixed issue with CommandSet auto-discovery only searching direct sub-classes
* Enhancements
    * Added functions to fetch registered CommandSets by type and command name

## 1.3.1 (August 6, 2020)
* Bug Fixes
    * Fixed issue determining whether an argparse completer function required a reference to a containing
      CommandSet. Also resolves issues determining the correct CommandSet instance when calling the argparse 
      argument completer function.  Manifested as a TypeError when using `cmd2.Cmd.path_complete` as a completer 
      for an argparse-based command defined in a CommandSet

## 1.3.0 (August 4, 2020)
* Enhancements
    * Added CommandSet - Enables defining a separate loadable module of commands to register/unregister
      with your cmd2 application.
* Other
    * Marked with_argparser_and_unknown_args pending deprecation and consolidated implementation into
      with_argparser 

## 1.2.1 (July 14, 2020)
* Bug Fixes
    * Relax minimum version of `importlib-metadata` to >= 1.6.0 when using Python < 3.8

## 1.2.0 (July 13, 2020)
* Bug Fixes
    * Fixed `typing` module compatibility issue with Python 3.5 prior to 3.5.4 
* Enhancements
    * Switched to getting version using `importlib.metadata` instead of using `pkg_resources`
        * Improves `cmd2` application launch time on systems that have a lot of Python packages on `sys.path`
        * Added dependency on `importlib_metadata` when running on versions of Python prior to 3.8

## 1.1.0 (June 6, 2020)
* Bug Fixes
    * Fixed issue where subcommand usage text could contain a subcommand alias instead of the actual name
    * Fixed bug in `ArgparseCompleter` where `fill_width` could become negative if `token_width` was large 
      relative to the terminal width.
* Enhancements
    * Made `ipy` consistent with `py` in the following ways
        * `ipy` returns whether any of the commands run in it returned True to stop command loop
        * `Cmd.in_pyscript()` returns True while in `ipy`.
        * Starting `ipy` when `Cmd.in_pyscript()` is already True is not allowed.
    * `with_argument_list`, `with_argparser`, and `with_argparser_and_unknown_args` wrappers now pass
      `kwargs` through to their wrapped command function.
    * Added `table_creator` module for creating richly formatted tables. This module is in beta and subject
      to change.
        * See [table_creation](https://cmd2.readthedocs.io/en/latest/features/table_creation.html)
          documentation for an overview.
        * See [table_creation.py](https://github.com/python-cmd2/cmd2/blob/master/examples/table_creation.py)
          for an example.
    * Added the following exceptions to the public API
        * `SkipPostcommandHooks` - Custom exception class for when a command has a failure bad enough to skip
          post command hooks, but not bad enough to print the exception to the user.
        * `Cmd2ArgparseError` - A `SkipPostcommandHooks` exception for when a command fails to parse its arguments.
          Normally argparse raises a `SystemExit` exception in these cases. To avoid stopping the command
          loop, catch the `SystemExit` and raise this instead. If you still need to run post command hooks
          after parsing fails, just return instead of raising an exception.
    * Added explicit handling of `SystemExit`. If a command raises this exception, the command loop will be
      gracefully stopped.
    
## 1.0.2 (April 06, 2020)
* Bug Fixes
    * Ctrl-C now stops a running text script instead of just the current `run_script` command
* Enhancements
    * `do_shell()` now saves the return code of the command it runs in `self.last_result` for use in pyscripts

## 1.0.1 (March 13, 2020)
* Bug Fixes
    * Fixed issue where postcmd hooks were running after an `argparse` exception in a command.

## 1.0.0 (March 1, 2020)
* Enhancements
    * The documentation at [cmd2.rftd.io](https://cmd2.readthedocs.io) received a major overhaul
* Other
    * Moved [categorize](https://cmd2.readthedocs.io/en/latest/api/utils.html#miscellaneous) utility function from **decorators** module to **utils** module
* Notes
    * Now that the 1.0 release is out, `cmd2` intends to follow [Semantic Versioning](https://semver.org)

## 0.10.1 (February 19, 2020)
* Bug Fixes
    * Corrected issue where the actual new value was not always being printed in do_set. This occurred in cases where
      the typed value differed from what the setter had converted it to.
    * Fixed bug where ANSI style sequences were not correctly handled in `utils.truncate_line()`. 
    * Fixed bug where pyscripts could edit `cmd2.Cmd.py_locals` dictionary.
    * Fixed bug where cmd2 set `sys.path[0]` for a pyscript to cmd2's working directory instead of the 
    script file's directory.
    * Fixed bug where `sys.path` was not being restored after a pyscript ran.
* Enhancements
    * Renamed set command's `-l/--long` flag to `-v/--verbose` for consistency with help and history commands.
    * Setting the following pyscript variables:
        * `__name__`: __main__
        * `__file__`: script path (as typed, ~ will be expanded)
    * Only tab complete after redirection tokens if redirection is allowed
    * Made `CompletionError` exception available to non-argparse tab completion
    * Added `apply_style` to `CompletionError` initializer. It defaults to True, but can be set to False if
    you don't want the error text to have `ansi.style_error()` applied to it when printed.
* Other
    * Removed undocumented `py run` command since it was replaced by `run_pyscript` a while ago
    * Renamed `AutoCompleter` to `ArgparseCompleter` for clarity
    * Custom `EmptyStatement` exception is no longer part of the documented public API
* Notes
    * This is a beta release leading up to the 1.0.0 release
    * We intend no more breaking changes prior to 1.0.0
        * Just bug fixes, documentation updates, and enhancements

## 0.10.0 (February 7, 2020)
* Enhancements
    * Changed the default help text to make `help -v` more discoverable
    * **set** command now supports tab completion of values
    * Added `add_settable()` and `remove_settable()` convenience methods to update `self.settable` dictionary
    * Added convenience `ansi.fg` and `ansi.bg` enums of foreground and background colors
        * `ansi.style()` `fg` argument can now either be of type `str` or `ansi.fg`
        * `ansi.style()` `bg` argument can now either be of type `str` or `ansi.bg`
        * This supports IDE auto-completion of color names
        * The enums also support
            * `f-strings` and `format()` calls (e.g. `"{}hello{}".format(fg.blue, fg.reset)`)
            * string concatenation (e.g. `fg.blue + "hello" + fg.reset`)
* Breaking changes
    * Renamed `locals_in_py` attribute of `cmd2.Cmd` to `self_in_py`
    * The following public attributes of `cmd2.Cmd` are no longer settable at runtime by default:
        * `continuation_prompt`
        * `self_in_py`
        * `prompt`
    * `self.settable` changed to `self.settables`
        * It is now a Dict[str, Settable] instead of Dict[str, str]
        * setting onchange callbacks have a new method signature and must be added to the
          Settable instance in order to be called
    * Removed `cast()` utility function
    * Removed `ansi.FG_COLORS` and `ansi.BG_COLORS` dictionaries
        * Replaced with `ansi.fg` and `ansi.bg` enums providing similar but improved functionality
* Notes
    * This is an alpha release leading up to the 1.0.0 release
    * We intend no more breaking changes prior to 1.0.0
        * Just bug fixes, documentation updates, and enhancements

## 0.9.25 (January 26, 2020)
* Enhancements
    * Reduced what gets put in package downloadable from PyPI (removed irrelevant CI config files and such)

## 0.9.24 (January 23, 2020)
* Enhancements
    * Flushing stderr when setting the window title and printing alerts for better responsiveness in cases where
    stderr is not unbuffered.
    * Added function to truncate a single line to fit within a given display width. `cmd2.utils.truncate_line`
    supports characters with display widths greater than 1 and ANSI style sequences.
    * Added line truncation support to `cmd2.utils` text alignment functions.
    * Added support for Python 3.9 alpha

## 0.9.23 (January 9, 2020)
* Bug Fixes
    * Fixed bug where startup script containing a single quote in its file name was incorrectly quoted
    * Added missing implicit dependency on `setuptools` due to build with `setuptools_scm`
* Enhancements
    * Added dim text style support via `style()` function and `ansi.INTENSITY_DIM` setting.
* Breaking changes
    * Renamed the following `ansi` members for accuracy in what types of ANSI escape sequences are handled
        * `ansi.allow_ansi` -> `ansi.allow_style`
        * `ansi.ansi_safe_wcswidth()` -> `ansi.style_aware_wcswidth()`
        * `ansi.ansi_aware_write()` -> `ansi.style_aware_write()`
    * Renamed the following `ansi` members for clarification
        * `ansi.BRIGHT` -> `ansi.INTENSITY_BRIGHT`
        * `ansi.NORMAL` -> `ansi.INTENSITY_NORMAL`

## 0.9.22 (December 9, 2019)
* Bug Fixes
    * Fixed bug where a redefined `ansi.style_error` was not being used in all `cmd2` files
* Enhancements
    * Enabled line buffering when redirecting output to a file
    * Added `align_left()`, `align_center()`, and `align_right()` to utils.py. All 3 of these functions support
    ANSI escape sequences and characters with display widths greater than 1. They wrap `align_text()` which
    is also in utils.py.

## 0.9.21 (November 26, 2019)
* Bug Fixes
    * Fixed bug where pipe processes were not being stopped by Ctrl-C
    * Added exception handling to account for non-standard Python environments in which readline is not loaded
     dynamically from a shared library file
* Enhancements
    * Added `read_input()` function that is used to read from stdin. Unlike the Python built-in `input()`, it also has
    an argument to disable tab completion while input is being entered.
    * Added capability to override the argument parser class used by cmd2 built-in commands. See override_parser.py
    example for more details.
    * Added `end` argument to `pfeedback()` to be consistent with the other print functions like `poutput()`.
    * Added `apply_style` to `pwarning()`.
* Breaking changes
    * For consistency between all the print functions:
        * Made `end` and `chop` keyword-only arguments of `ppaged()`
        * `end` is always added to message in `ppaged()`

## 0.9.20 (November 12, 2019)
* Bug Fixes
    * Fixed bug where setting `use_ipython` to False removed ipy command from the entire `cmd2.Cmd` class instead of
    just the instance being created
    * Fix bug where cmd2 ran 'stty sane' command when stdin was not a terminal
* Enhancements
    * Send all startup script paths to run_script. Previously we didn't do this if the file was empty, but that
    showed no record of the run_script command in history.
    * Made it easier for developers to override `edit` command by having `do_history` no longer call `do_edit`. This
    also removes the need to exclude `edit` command from history list.
    * It is no longer necessary to set the `prog` attribute of an argparser with subcommands. cmd2 now automatically
    sets the prog value of it and all its subparsers so that all usage statements contain the top level command name
    and not sys.argv[0].
* Breaking changes
    * Some constants were moved from cmd2.py to constants.py
    * cmd2 command decorators were moved to decorators.py. If you were importing them via cmd2's \_\_init\_\_.py, then
    there will be no issues.

## 0.9.19 (October 14, 2019)
* Bug Fixes
    * Fixed `ValueError` exception which could occur when an old format persistent history file is loaded with new `cmd2`
* Enhancements
    * Improved displaying multiline CompletionErrors by indenting all lines

## 0.9.18 (October 1, 2019)
* Bug Fixes
    * Fixed bug introduced in 0.9.17 where help functions for hidden and disabled commands were not being filtered
    out as help topics
* Enhancements
    * `AutoCompleter` now handles argparse's mutually exclusive groups. It will not tab complete flag names or positionals
    for already completed groups. It also will print an error if you try tab completing a flag's value if the flag
    belongs to a completed group.
    * `AutoCompleter` now uses the passed-in parser's help formatter to generate hint text. This gives help and
    hint text for an argument consistent formatting.

## 0.9.17 (September 23, 2019)
* Bug Fixes
    * Fixed a bug when using WSL when all Windows paths have been removed from $PATH
    * Fixed a bug when running a cmd2 application on Linux without Gtk libraries installed
* Enhancements
    * No longer treating empty text scripts as an error condition
    * Allow dynamically extending a `cmd2.Cmd` object instance with a `do_xxx` method at runtime
    * Choices/Completer functions can now be passed a dictionary that maps command-line tokens to their
    argparse argument. This is helpful when one argument determines what is tab completed for another argument.
    If these functions have an argument called `arg_tokens`, then AutoCompleter will automatically pass this
    dictionary to them.
    * Added CompletionError class that can be raised during argparse-based tab completion and printed to the user
    * Added the following convenience methods
        - `Cmd.in_script()` - return whether a text script is running
        - `Cmd.in_pyscript()` - return whether a pyscript is running

## 0.9.16 (August 7, 2019)
* Bug Fixes
    * Fixed inconsistent parsing/tab completion behavior based on the value of `allow_redirection`. This flag is
    only meant to be a security setting that prevents redirection of stdout and should not alter parsing logic.
* Enhancements
    * Raise `TypeError` if trying to set choices/completions on argparse action that accepts no arguments
    * Create directory for the persistent history file if it does not already exist
    * Added `set_choices_function()`, `set_choices_method()`, `set_completer_function()`, and `set_completer_method()`
    to support cases where this functionality needs to be added to an argparse action outside of the normal
    `parser.add_argument()` call.
* Breaking Changes
    * Aliases and macros can no longer have the same name as a command

## 0.9.15 (July 24, 2019)
* Bug Fixes
    * Fixed exception caused by tab completing after an invalid subcommand was entered
    * Fixed bug where `history -v` was sometimes showing raw and expanded commands when they weren't different
    * Fixed bug where multiline commands were having leading and ending spaces stripped. This would mess up quoted
    strings that crossed multiple lines.
    * Fixed a bug when appending to the clipboard where contents were in reverse order
    * Fixed issue where run_pyscript failed if the script's filename had 2 or more consecutive spaces
    * Fixed issue where completer function of disabled command would still run
* Enhancements
    * Greatly simplified using argparse-based tab completion. The new interface is a complete overhaul that breaks
    the previous way of specifying completion and choices functions. See header of [argparse_custom.py](https://github.com/python-cmd2/cmd2/blob/master/cmd2/argparse_custom.py)
    for more information.
    * Enabled tab completion on multiline commands
* **Renamed Commands Notice**
    * The following commands were renamed in the last release and have been removed in this release
        * `load` - replaced by `run_script`
        * `_relative_load` - replaced by `_relative_run_script`
        * `pyscript` - replaced by `run_pyscript`
    * We apologize for any inconvenience, but the new names are more self-descriptive
        * Lots of end users were confused particularly about what exactly `load` should be loading
* Breaking Changes
    * Restored `cmd2.Cmd.statement_parser` to be a public attribute (no underscore)
        * Since it can be useful for creating [post-parsing hooks](https://cmd2.readthedocs.io/en/latest/features/hooks.html#postparsing-hooks)
    * Completely overhauled the interface for adding tab completion to argparse arguments. See enhancements for more details.
    * `ACArgumentParser` is now called `Cmd2ArgumentParser`
    * Moved `basic_complete` to utils.py
    * Made optional arguments on the following completer methods keyword-only:
    `delimiter_complete`, `flag_based_complete`, `index_based_complete`, `path_complete`, `shell_cmd_complete`
    * Renamed history option from `--output-file` to `--output_file`
    * Renamed `matches_sort_key` to `default_sort_key`. This value determines the default sort ordering of string
    results like alias, command, category, macro, settable, and shortcut names. Unsorted tab completion results
    also are sorted with this key. Its default value (ALPHABETICAL_SORT_KEY) performs a case-insensitive alphabetical
    sort, but it can be changed to a natural sort by setting the value to NATURAL_SORT_KEY.
    * `StatementParser` now expects shortcuts to be passed in as dictionary. This eliminates the step of converting the
    shortcuts dictionary into a tuple before creating `StatementParser`.
    * Renamed `Cmd.pyscript_name` to `Cmd.py_bridge_name`
    * Renamed `Cmd.pystate` to `Cmd.py_locals`
    * Renamed `PyscriptBridge` to `PyBridge`

## 0.9.14 (June 29, 2019)
* Enhancements
    * Added support for and testing with Python 3.8, starting with 3.8 beta
    * Improved information displayed during transcript testing
    * Added `ansi` module with functions and constants to support ANSI escape sequences which are used for things
    like applying style to text
    * Added support for applying styles (color, bold, underline) to text via `style()` function in `ansi` module
    * Added default styles to ansi.py for printing `success`, `warning`. and `error` text. These are the styles used
    by cmd2 and can be overridden to match the color scheme of your application.
    * Added `ansi_aware_write()` function to `ansi` module. This function takes into account the value of `allow_ansi`
    to determine if ANSI escape sequences should be stripped when not writing to a tty. See documentation for more
    information on the `allow_ansi` setting.
* Breaking Changes
    * Python 3.4 reached its [end of life](https://www.python.org/dev/peps/pep-0429/) on March 18, 2019 and is no longer supported by `cmd2`
        * If you need to use Python 3.4, you should pin your requirements to use `cmd2` 0.9.13
    * Made lots of changes to minimize the public API of the `cmd2.Cmd` class
        * Attributes and methods we do not intend to be public now all begin with an underscore
        * We make no API stability guarantees about these internal functions
    * Split `perror` into 2 functions:
        * `perror` - print a message to sys.stderr
        * `pexcept` - print Exception message to sys.stderr. If debug is true, print exception traceback if one exists
    * Signature of `poutput` and `perror` significantly changed
        * Removed color parameters `color`, `err_color`, and `war_color` from `poutput` and `perror`
            * See the docstrings of these methods or the [cmd2 docs](https://cmd2.readthedocs.io/en/latest/features/generating_output.html) for more info on applying styles to output messages
        * `end` argument is now keyword-only and cannot be specified positionally
        * `traceback_war` no longer exists as an argument since it isn't needed now that `perror` and `pexcept` exist
    * Moved `cmd2.Cmd.colors` to ansi.py and renamed it to `allow_ansi`. This is now an application-wide setting.
    * Renamed the following constants and moved them to ansi.py
        * `COLORS_ALWAYS` --> `ANSI_ALWAYS`
        * `COLORS_NEVER` --> `ANSI_NEVER`
        * `COLORS_TERMINAL` --> `ANSI_TERMINAL`
* **Renamed Commands Notice**
    * The following commands have been renamed. The old names will be supported until the next release.
        * `load` --> `run_script`
        * `_relative_load` --> `_relative_run_script`
        * `pyscript` --> `run_pyscript`

## 0.9.13 (June 14, 2019)
* Bug Fixes
    * Fixed issue where the wrong terminator was being appended by `Statement.expanded_command_line()`
    * Fixed issue where aliases and macros could not contain terminator characters in their values
    * History now shows what was typed for macros and not the resolved value by default. This is consistent with
    the behavior of aliases. Use the `expanded` or `verbose` arguments to `history` to see the resolved value for
    the macro.
    * Fixed parsing issue in case where output redirection appears before a pipe. In that case, the pipe was given
    precedence even though it appeared later in the command.
    * Fixed issue where quotes around redirection file paths were being lost in `Statement.expanded_command_line()`
    * Fixed a bug in how line numbers were calculated for transcript testing
    * Fixed issue where `_cmdloop()` suppressed exceptions by returning from within its `finally` code
    * Fixed UnsupportedOperation on fileno error when a shell command was one of the commands run while generating
    a transcript
    * Fixed bug where history was displaying expanded multiline commands when -x was not specified
* Enhancements
    * **Added capability to chain pipe commands and redirect their output (e.g. !ls -l | grep user | wc -l > out.txt)**
    * `pyscript` limits a command's stdout capture to the same period that redirection does.
    Therefore output from a command's postparsing and finalization hooks isn't saved in the StdSim object.
    * `StdSim.buffer.write()` now flushes when the wrapped stream uses line buffering and the bytes being written
    contain a newline or carriage return. This helps when `pyscript` is echoing the output of a shell command
    since the output will print at the same frequency as when the command is run in a terminal.
    * **ACArgumentParser** no longer prints complete help text when a parsing error occurs since long help messages
    scroll the actual error message off the screen.
    * Exceptions occurring in tab completion functions are now printed to stderr before returning control back to
    readline. This makes debugging a lot easier since readline suppresses these exceptions.
    * Added support for custom Namespaces in the argparse decorators. See description of `ns_provider` argument
    for more information.
    * Transcript testing now sets the `exit_code` returned from `cmdloop` based on Success/Failure
    * The history of entered commands previously was saved using the readline persistence mechanism,
    and only persisted if you had readline installed. Now history is persisted independent of readline; user
    input from previous invocations of `cmd2` based apps now shows in the `history` command.
    * Text scripts now run immediately instead of adding their commands to `cmdqueue`. This allows easy capture of
    the entire script's output.
    * Added member to `CommandResult` called `stop` which is the return value of `onecmd_plus_hooks` after it runs
    the given command line.
* Breaking changes
    * Replaced `unquote_redirection_tokens()` with `unquote_specific_tokens()`. This was to support the fix
    that allows terminators in alias and macro values.
    * Changed `Statement.pipe_to` to a string instead of a list
    * `preserve_quotes` is now a keyword-only argument in the argparse decorators
    * Refactored so that `cmd2.Cmd.cmdloop()` returns the `exit_code` instead of a call to `sys.exit()`
    It is now application developer's responsibility to treat the return value from `cmdloop()` accordingly
    * Only valid commands are persistent in history between invocations of `cmd2` based apps. Previously
    all user input was persistent in history. If readline is installed, the history available with the up and
    down arrow keys (readline history) may not match that shown in the `history` command, because `history`
    only tracks valid input, while readline history captures all input.
    * History is now persisted in a binary format, not plain text format. Previous history files are destroyed
    on first launch of a `cmd2` based app of version 0.9.13 or higher.
    * HistoryItem class is no longer a subclass of `str`. If you are directly accessing the `.history` attribute
    of a `cmd2` based app, you will need to update your code to use `.history.get(1).statement.raw` instead.
    * Removed internally used `eos` command that was used to keep track of when a text script's commands ended
    * Removed `cmd2` member called `_STOP_AND_EXIT` since it was just a boolean value that should always be True
    * Removed `cmd2` member called `_should_quit` since `PyBridge` now handles this logic
    * Removed support for `cmd.cmdqueue`
    * `allow_cli_args` is now an argument to __init__ instead of a `cmd2` class member
* **Python 3.4 EOL notice**
    * Python 3.4 reached its [end of life](https://www.python.org/dev/peps/pep-0429/) on March 18, 2019
    * This is the last release of `cmd2` which will support Python 3.4

## 0.9.12 (April 22, 2019)
* Bug Fixes
    * Fixed a bug in how redirection and piping worked inside ``py`` or ``pyscript`` commands
    * Fixed bug in `async_alert` where it didn't account for prompts that contained newline characters
    * Fixed path completion case when CWD is just a slash. Relative path matches were incorrectly prepended with a slash.
* Enhancements
    * Added ability to include command name placeholders in the message printed when trying to run a disabled command.
        * See docstring for ``disable_command()`` or ``disable_category()`` for more details.
    * Added instance attributes to customize error messages without having to override methods. Theses messages can
    also be colored.
        * `help_error` - the error that prints when no help information can be found
        * `default_error` - the error that prints when a non-existent command is run
    * The `with_argparser` decorators now add the Statement object created when parsing the command line to the
    `argparse.Namespace` object they pass to the `do_*` methods. It is stored in an attribute called `__statement__`.
    This can be useful if a command function needs to know the command line for things like logging.
    * Added a `-t` option to the `load` command for automatically generating a transcript based on a script file
    * When in a **pyscript**, the stdout and stderr streams of shell commands and processes being piped to are now
    captured and included in the ``CommandResult`` structure.
* Potentially breaking changes
    * The following commands now write to stderr instead of stdout when printing an error. This will make catching
    errors easier in pyscript.
        * ``do_help()`` - when no help information can be found
        * ``default()`` - in all cases since this is called when an invalid command name is run
        * ``_report_disabled_command_usage()`` - in all cases since this is called when a disabled command is run
    * Removed *** from beginning of error messages printed by `do_help()` and `default()`
    * Significantly refactored ``cmd.Cmd`` class so that all class attributes got converted to instance attributes, also:
        * Added ``allow_redirection``, ``terminators``, ``multiline_commands``, and ``shortcuts`` as optional arguments
        to ``cmd2.Cmd.__init__()``
        * A few instance attributes were moved inside ``StatementParser`` and properties were created for accessing them
    * ``self.pipe_proc`` is now called ``self.cur_pipe_proc_reader`` and is a ``ProcReader`` class.
    * Shell commands and commands being piped to while in a *pyscript* will function as if their output is going
    to a pipe and not a tty. This was necessary to be able to capture their output.
    * Removed `reserved_words` class attribute due to lack of use
    * Removed `keywords` instance attribute due to lack of use

## 0.9.11 (March 13, 2019)
* Bug Fixes
    * Fixed bug in how **history** command deals with multiline commands when output to a script
    * Fixed a bug when the ``with_argument_list`` decorator is called with the optional ``preserve_quotes`` argument
    * Fix bug in ``perror()`` where it would try to print an exception Traceback even if none existed
* Enhancements
    * Improvements to the **history** command
        * Simplified the display format and made it more similar to **bash**
        * Added **-x**, **--expanded** flag
            * output expanded commands instead of entered command (expands aliases, macros, and shortcuts)
        * Added **-v**, **--verbose** flag
            * display history and include expanded commands if they differ from the typed command
        * Added support for negative indices
    * Added ``matches_sort_key`` to override the default way tab completion matches are sorted
    * Added ``StdSim.pause_storage`` member which when True will cause ``StdSim`` to not save the output sent to it.
      See documentation for ``CommandResult`` in ``pyscript_bridge.py`` for reasons pausing the storage can be useful.
    * Added ability to disable/enable individual commands and entire categories of commands. When a command
      is disabled, it will not show up in the help menu or tab complete. If a user tries to run the command
      or call help on it, a command-specific message supplied by the developer will be printed. The following
      commands were added to support this feature.
        * ``enable_command()``
        * ``enable_category()``
        * ``disable_command()``
        * ``disable_category()``
* Potentially breaking changes
    * Made ``cmd2_app`` a positional and required argument of ``AutoCompleter`` since certain functionality now
    requires that it can't be ``None``.
    * ``AutoCompleter`` no longer assumes ``CompletionItem`` results are sorted. Therefore you should follow the
    ``cmd2`` convention of setting ``self.matches_sorted`` to True before returning the results if you have already
    sorted the ``CompletionItem`` list. Otherwise it will be sorted using ``self.matches_sort_key``.
    * Removed support for bash completion since this feature had slow performance. Also it relied on
    ``AutoCompleter`` which has since developed a dependency on ``cmd2`` methods.
    * Removed ability to call commands in ``pyscript`` as if they were functions (e.g. ``app.help()``) in favor
    of only supporting one ``pyscript`` interface. This simplifies future maintenance.
    * No longer supporting C-style comments. Hash (#) is the only valid comment marker.
    * No longer supporting comments embedded in a command. Only command line input where the first
    non-whitespace character is a # will be treated as a comment. This means any # character appearing
    later in the command will be treated as a literal. The same applies to a # in the middle of a multiline
    command, even if it is the first character on a line.
        * \# this is a comment
        * this # is not a comment

## 0.9.10 (February 22, 2019)
* Bug Fixes
    * Fixed unit test that hangs on Windows

## 0.9.9 (February 21, 2019)
* Bug Fixes
    * Fixed bug where the ``set`` command was not tab completing from the current ``settable`` dictionary.
* Enhancements
    * Changed edit command to use do_shell() instead of calling os.system()

## 0.9.8 (February 06, 2019)
* Bug Fixes
    * Fixed issue with echoing strings in StdSim. Because they were being sent to a binary buffer, line buffering
    was being ignored.
* Enhancements
    * Made quit() and exit() functions available to scripts run with pyscript. This allows those scripts to exit
    back to the console's prompt instead of exiting the whole application.

## 0.9.7 (January 08, 2019)
* Bug Fixes
    * Fixed bug when user chooses a zero or negative index when calling ``Cmd.select()``
    * Restored behavior where ``cmd_echo`` always starts as False in a py script. This was broken in 0.9.5.
* Enhancements
    * **cmdloop** now only attempts to register a custom signal handler for SIGINT if running in the main thread
    * commands run as a result of ``default_to_shell`` being **True** now run via ``do_shell()`` and are saved
    to history.
    * Added more tab completion to pyscript command.
* Deletions (potentially breaking changes)
    * Deleted ``Cmd.colorize()`` and ``Cmd._colorcodes`` which were deprecated in 0.9.5
    * Replaced ``dir_exe_only`` and  ``dir_only`` flags in ``path_complete`` with optional ``path_filter`` function
    that is used to filter paths out of completion results.
    * ``perror()`` no longer prepends "ERROR: " to the error message being printed

## 0.9.6 (October 13, 2018)
* Bug Fixes
    * Fixed bug introduced in 0.9.5 caused by backing up and restoring `self.prompt` in `pseudo_raw_input`.
      As part of this fix, continuation prompts will not be redrawn with `async_update_prompt` or `async_alert`.
* Enhancements
    * All platforms now depend on [wcwidth](https://pypi.python.org/pypi/wcwidth) to assist with asynchronous alerts.
    * Macros now accept extra arguments when called. These will be tacked onto the resolved command.
    * All cmd2 commands run via `py` now go through `onecmd_plus_hooks`.

## 0.9.5 (October 11, 2018)
* Bug Fixes
    * Fixed bug where ``get_all_commands`` could return non-callable attributes
    * Fixed bug where **alias** command was dropping quotes around arguments
    * Fixed bug where running help on argparse commands didn't work if they didn't support -h
    * Fixed transcript testing bug where last command in transcript has no expected output
    * Fixed bugs with how AutoCompleter and ArgparseFunctor handle argparse
    arguments with nargs=argparse.REMAINDER. Tab completion now correctly
    matches how argparse will parse the values. Command strings generated by
    ArgparseFunctor should now be compliant with how argparse expects
    REMAINDER arguments to be ordered.
    * Fixed bugs with how AutoCompleter handles flag prefixes. It is no
    longer hard-coded to use '-' and will check against the prefix_chars in
    the argparse object. Also, single-character tokens that happen to be a
    prefix char are not treated as flags by argparse and AutoCompleter now
    matches that behavior.
    * Fixed bug where AutoCompleter was not distinguishing between a negative number and a flag
    * Fixed bug where AutoCompleter did not handle -- the same way argparse does (all args after -- are non-options)
* Enhancements
    * Added ``exit_code`` attribute of ``cmd2.Cmd`` class
        * Enables applications to return a non-zero exit code when exiting from ``cmdloop``
    * ``ACHelpFormatter`` now inherits from ``argparse.RawTextHelpFormatter`` to make it easier
    for formatting help/description text
    * Aliases are now sorted alphabetically
    * The **set** command now tab completes settable parameter names
    * Added ``async_alert``, ``async_update_prompt``, and ``set_window_title`` functions
        * These allow you to provide feedback to the user in an asychronous fashion, meaning alerts can
        display when the user is still entering text at the prompt. See [async_printing.py](https://github.com/python-cmd2/cmd2/blob/master/examples/async_printing.py)
        for an example.
    * Cross-platform colored output support
        * ``colorama`` gets initialized properly in ``Cmd.__init()``
        * The ``Cmd.colors`` setting is no longer platform dependent and now has three values:
            * Terminal (default) - output methods do not strip any ANSI escape sequences when output is a terminal, but
            if the output is a pipe or a file the escape sequences are stripped
            * Always - output methods **never** strip ANSI escape sequences, regardless of the output destination
            * Never - output methods strip all ANSI escape sequences
    * Added ``macro`` command to create macros, which are similar to aliases, but can take arguments when called
    * All cmd2 command functions have been converted to use argparse.
    * Renamed argparse_example.py to decorator_example.py to help clarify its intent
* Deprecations
    * Deprecated the built-in ``cmd2`` support for colors including ``Cmd.colorize()`` and ``Cmd._colorcodes``
* Deletions (potentially breaking changes)
    * The ``preparse``, ``postparsing_precmd``, and ``postparsing_postcmd`` methods *deprecated* in the previous release
    have been deleted
        * The new application lifecycle hook system allows for registration of callbacks to be called at various points
        in the lifecycle and is more powerful and flexible than the previous system
    * ``alias`` is now a command with subcommands to create, list, and delete aliases. Therefore its syntax
      has changed. All current alias commands in startup scripts or transcripts will break with this release.
    * `unalias` was deleted since ``alias delete`` replaced it

## 0.9.4 (August 21, 2018)
* Bug Fixes
    * Fixed bug where ``preparse`` was not getting called
    * Fixed bug in parsing of multiline commands where matching quote is on another line
* Enhancements
    * Improved implementation of lifecycle hooks to support a plugin
      framework, see ``docs/hooks.rst`` for details.
    * New dependency on ``attrs`` third party module
    * Added ``matches_sorted`` member to support custom sorting of tab completion matches
    * Added [tab_autocomp_dynamic.py](https://github.com/python-cmd2/cmd2/blob/master/examples/tab_autocomp_dynamic.py) example
        * Demonstrates updating the argparse object during init instead of during class construction
* Deprecations
    * Deprecated the following hook methods, see ``hooks.rst`` for full details:
       * ``cmd2.Cmd.preparse()`` - equivalent functionality available
         via ``cmd2.Cmd.register_postparsing_hook()``
       * ``cmd2.Cmd.postparsing_precmd()`` - equivalent functionality available
         via ``cmd2.Cmd.register_postparsing_hook()``
       * ``cmd2.Cmd.postparsing_postcmd()`` - equivalent functionality available
         via ``cmd2.Cmd.register_postcmd_hook()``

## 0.8.9 (August 20, 2018)
* Bug Fixes
    * Fixed extra slash that could print when tab completing users on Windows

## 0.9.3 (July 12, 2018)
* Bug Fixes
    * Fixed bug when StatementParser ``__init__()`` was called with ``terminators`` equal to ``None``
    * Fixed bug when ``Cmd.onecmd()`` was called with a raw ``str``
* Enhancements
    * Added ``--clear`` flag to ``history`` command that clears both the command and readline history.
* Deletions
    * The ``CmdResult`` helper class which was *deprecated* in the previous release has now been deleted
        * It has been replaced by the improved ``CommandResult`` class

## 0.9.2 (June 28, 2018)
* Bug Fixes
    * Fixed issue where piping and redirecting did not work correctly with paths that had spaces
* Enhancements
    * Added ability to print a header above tab completion suggestions using `completion_header` member
    * Added ``pager`` and ``pager_chop`` attributes to the ``cmd2.Cmd`` class
        * ``pager`` defaults to **less -RXF** on POSIX and **more** on Windows
        * ``pager_chop`` defaults to **less -SRXF** on POSIX and **more** on Windows
    * Added ``chop`` argument to ``cmd2.Cmd.ppaged()`` method for displaying output using a pager
        * If ``chop`` is ``False``, then ``self.pager`` is used as the pager
        * Otherwise ``self.pager_chop`` is used as the pager
    * Greatly improved the [table_display.py](https://github.com/python-cmd2/cmd2/blob/master/examples/table_display.py) example
        * Now uses the new [tableformatter](https://github.com/python-tableformatter/tableformatter) module which looks better than ``tabulate``
* Deprecations
    * The ``CmdResult`` helper class is *deprecated* and replaced by the improved ``CommandResult`` class
        * ``CommandResult`` has the following attributes: **stdout**, **stderr**, and **data**
            * ``CmdResult`` had attributes of: **out**, **err**, **war**
        * ``CmdResult`` will be deleted in the next release

## 0.8.8 (June 28, 2018)
* Bug Fixes
    * Prevent crashes that could occur attempting to open a file in non-existent directory or with very long filename
* Enhancements
    * `display_matches` is no longer restricted to delimited strings

## 0.9.1 (May 28, 2018)
* Bug Fixes
    * fix packaging error for 0.8.x versions (yes we had to deploy a new version
      of the 0.9.x series to fix a packaging error with the 0.8.x version)

## 0.9.0 (May 28, 2018)
* Bug Fixes
    * If self.default_to_shell is true, then redirection and piping are now properly passed to the shell. Previously it was truncated.
    * Submenus now call all hooks, it used to just call precmd and postcmd.
* Enhancements
    * Automatic completion of ``argparse`` arguments via ``cmd2.argparse_completer.AutoCompleter``
        * See the [tab_autocompletion.py](https://github.com/python-cmd2/cmd2/blob/master/examples/tab_autocompletion.py) example for a demonstration of how to use this feature
    * ``cmd2`` no longer depends on the ``six`` module
    * ``cmd2`` is now a multi-file Python package instead of a single-file module
    * New pyscript approach that provides a pythonic interface to commands in the cmd2 application.
    * Switch command parsing from pyparsing to custom code which utilizes shlex.
        * The object passed to do_* methods has changed. It no longer is the pyparsing object, it's a new Statement object, which is a subclass of ``str``. The statement object has many attributes which give you access to various components of the parsed input. If you were using anything but the string in your do_* methods, this change will require you to update your code.
        * ``commentGrammers`` is no longer supported or available. Comments are C-style or python style.
        * Input redirection no longer supported. Use the load command instead.
        * ``multilineCommand`` attribute is ``now multiline_command``
        * ``identchars`` is now ignored. The standardlibrary cmd uses those characters to split the first "word" of the input, but cmd2 hasn't used those for a while, and the new parsing logic parses on whitespace, which has the added benefit of full unicode support, unlike cmd or prior versions of cmd2.
        * ``set_posix_shlex`` function and ``POSIX_SHLEX`` variable have been removed. Parsing behavior is now always the more forgiving ``posix=false``.
        * ``set_strip_quotes`` function and ``STRIP_QUOTES_FOR_NON_POSIX`` have been removed. Quotes are stripped from arguments when presented as a list (a la ``sys.argv``), and present when arguments are presented as a string (like the string passed to do_*).
* Changes
    * ``strip_ansi()`` and ``strip_quotes()`` functions have moved to new utils module
    * Several constants moved to new constants module
    * Submenu support has been moved to a new [cmd2-submenu](https://github.com/python-cmd2/cmd2-submenu) plugin. If you use submenus, you will need to update your dependencies and modify your imports.
* Deletions (potentially breaking changes)
    * Deleted all ``optparse`` code which had previously been deprecated in release 0.8.0
        * The ``options`` decorator no longer exists
        * All ``cmd2`` code should be ported to use the new ``argparse``-based decorators
        * See the [Argument Processing](http://cmd2.readthedocs.io/en/latest/argument_processing.html) section of the documentation for more information on these decorators
        * Alternatively, see the [argparse_example.py](https://github.com/python-cmd2/cmd2/blob/master/examples/argparse_example.py)
    * Deleted ``cmd_with_subs_completer``, ``get_subcommands``, and ``get_subcommand_completer``
        * Replaced by default AutoCompleter implementation for all commands using argparse
    * Deleted support for old method of calling application commands with ``cmd()`` and ``self``
    * ``cmd2.redirector`` is no longer supported. Output redirection can only be done with '>' or '>>'
    * Deleted ``postparse()`` hook since it was redundant with ``postparsing_precmd``
* Python 2 no longer supported
    * ``cmd2`` now supports Python 3.4+
* Known Issues
    * Some developers have noted very slow performance when importing the ``cmd2`` module. The issue
    it intermittent, and investigation of the root cause is ongoing.

## 0.8.6 (May 27, 2018)
* Bug Fixes
    * Commands using the @with_argparser_and_unknown_args were not correctly recognized when tab completing
    * Fixed issue where completion display function was overwritten when a submenu quits
    * Fixed ``AttributeError`` on Windows when running a ``select`` command cause by **pyreadline** not implementing ``remove_history_item``
* Enhancements
    * Added warning about **libedit** variant of **readline** not being supported on macOS
    * Added tab completion of alias names in value field of **alias** command
    * Enhanced the ``py`` console in the following ways
        * Added tab completion of Python identifiers instead of **cmd2** commands
        * Separated the ``py`` console history from the **cmd2** history

## 0.8.5 (April 15, 2018)
* Bug Fixes
    * Fixed a bug with all argument decorators where the wrapped function wasn't returning a value and thus couldn't cause the cmd2 app to quit

* Enhancements
    * Added support for verbose help with -v where it lists a brief summary of what each command does
    * Added support for categorizing commands into groups within the help menu
        * See the [Grouping Commands](http://cmd2.readthedocs.io/en/latest/argument_processing.html?highlight=verbose#grouping-commands) section of the docs for more info
        * See [help_categories.py](https://github.com/python-cmd2/cmd2/blob/master/examples/help_categories.py) for an example
    * Tab completion of paths now supports ~user user path expansion
    * Simplified implementation of various tab completion functions so they no longer require ``ctypes``
    * Expanded documentation of ``display_matches`` list to clarify its purpose. See cmd2.py for this documentation.
    * Adding opening quote to tab completion if any of the completion suggestions have a space.

* **Python 2 EOL notice**
    * This is the last release where new features will be added to ``cmd2`` for Python 2.7
    * The 0.9.0 release of ``cmd2`` will support Python 3.4+ only
    * Additional 0.8.x releases may be created to supply bug fixes for Python 2.7 up until August 31, 2018
    * After August 31, 2018 not even bug fixes will be provided for Python 2.7

## 0.8.4 (April 10, 2018)
* Bug Fixes
    * Fixed conditional dependency issue in setup.py that was in 0.8.3.

## 0.8.3 (April 09, 2018)
* Bug Fixes
    * Fixed ``help`` command not calling functions for help topics
    * Fixed not being able to use quoted paths when redirecting with ``<`` and ``>``

* Enhancements
    * Tab completion has been overhauled and now supports completion of strings with quotes and spaces.
    * Tab completion will automatically add an opening quote if a string with a space is completed.
    * Added ``delimiter_complete`` function for tab completing delimited strings
    * Added more control over tab completion behavior including the following flags. The use of these flags is documented in cmd2.py
        * ``allow_appended_space``
        * ``allow_closing_quote``
    * Due to the tab completion changes, non-Windows platforms now depend on [wcwidth](https://pypi.python.org/pypi/wcwidth).
    * An alias name can now match a command name.
    * An alias can now resolve to another alias.

* Attribute Changes (Breaks backward compatibility)
    * ``exclude_from_help`` is now called ``hidden_commands`` since these commands are hidden from things other than help, including tab completion
        * This list also no longer takes the function names of commands (``do_history``), but instead uses the command names themselves (``history``)
    * ``excludeFromHistory`` is now called ``exclude_from_history``
    * ``cmd_with_subs_completer()`` no longer takes an argument called ``base``. Adding tab completion to subcommands has been simplified to declaring it in the
    subcommand parser's default settings. This easily allows arbitrary completers like path_complete to be used.
    See [subcommands.py](https://github.com/python-cmd2/cmd2/blob/master/examples/subcommands.py) for an example of how to use
    tab completion in subcommands. In addition, the docstring for ``cmd_with_subs_completer()`` offers more details.


## 0.8.2 (March 21, 2018)

* Bug Fixes
    * Fixed a bug in tab completion of command names within sub-menus
    * Fixed a bug when using persistent readline history in Python 2.7
    * Fixed a bug where the ``AddSubmenu`` decorator didn't work with a default value for ``shared_attributes``
    * Added a check to ``ppaged()`` to only use a pager when running in a real fully functional terminal
* Enhancements
    * Added [quit_on_sigint](http://cmd2.readthedocs.io/en/latest/settingchanges.html#quit-on-sigint) attribute to enable canceling current line instead of quitting when Ctrl+C is typed
    * Added possibility of having readline history preservation in a SubMenu
    * Added [table_display.py](https://github.com/python-cmd2/cmd2/blob/master/examples/table_display.py) example to demonstrate how to display tabular data
    * Added command aliasing with ``alias`` and ``unalias`` commands
    * Added the ability to load an initialization script at startup
        * See [alias_startup.py](https://github.com/python-cmd2/cmd2/blob/master/examples/alias_startup.py) for an example
    * Added a default SIGINT handler which terminates any open pipe subprocesses and re-raises a KeyboardInterrupt
    * For macOS, will load the ``gnureadline`` module if available and ``readline`` if not

## 0.8.1 (March 9, 2018)

* Bug Fixes
    * Fixed a bug if a non-existent **do_*** method was added to the ``exclude_from_help`` list
    * Fixed a bug in a unit test which would fail if your home directory was empty on a Linux system
    * Fixed outdated help text for the **edit** command
    * Fixed outdated [remove_unused.py](https://github.com/python-cmd2/cmd2/blob/master/examples/remove_unused.py)
* Enhancements
    * Added support for sub-menus.
        * See [submenus.py](https://github.com/python-cmd2/cmd2/blob/master/examples/submenus.py) for an example of how to use it
    * Added option for persistent readline history
        * See [persistent_history.py](https://github.com/python-cmd2/cmd2/blob/master/examples/persistent_history.py) for an example
        * See the [Searchable command history](http://cmd2.readthedocs.io/en/latest/freefeatures.html#searchable-command-history) section of the documentation for more info
    * Improved PyPI packaging by including unit tests and examples in the tarball
    * Improved documentation to make it more obvious that **poutput()** should be used instead of **print()**
    * ``exclude_from_help`` and ``excludeFromHistory`` are now instance instead of class attributes
    * Added flag and index based tab completion helper functions
        * See [tab_completion.py](https://github.com/python-cmd2/cmd2/blob/master/examples/tab_completion.py)
    * Added support for displaying output which won't fit on the screen via a pager using ``ppaged()``
        * See [paged_output.py](https://github.com/python-cmd2/cmd2/blob/master/examples/paged_output.py)
* Attributes Removed (**can cause breaking changes**)
    * ``abbrev`` - Removed support for abbreviated commands
        * Good tab completion makes this unnecessary and its presence could cause harmful unintended actions
    * ``case_insensitive`` - Removed support for case-insensitive command parsing
        * Its presence wasn't very helpful and could cause harmful unintended actions

## 0.8.0 (February 1, 2018)
* Bug Fixes
    * Fixed unit tests on Python 3.7 due to changes in how re.escape() behaves in Python 3.7
    * Fixed a bug where unknown commands were getting saved in the history
* Enhancements
    * Three new decorators for **do_*** commands to make argument parsing easier
        * **with_argument_list** decorator to change argument type from str to List[str]
            * **do_*** commands get a single argument which is a list of strings, as pre-parsed by shlex.split()
        * **with_arparser** decorator for strict argparse-based argument parsing of command arguments
            * **do_*** commands get a single argument which is the output of argparse.parse_args()
        * **with_argparser_and_unknown_args** decorator for argparse-based argument parsing, but allows unknown args
            * **do_*** commands get two arguments, the output of argparse.parse_known_args()
    *  See the [Argument Processing](http://cmd2.readthedocs.io/en/latest/argument_processing.html) section of the documentation for more information on these decorators
        * Alternatively, see the [argparse_example.py](https://github.com/python-cmd2/cmd2/blob/master/examples/argparse_example.py)
        and [arg_print.py](https://github.com/python-cmd2/cmd2/blob/master/examples/arg_print.py) examples
    * Added support for Argparse subcommands when using the **with_argument_parser** or **with_argparser_and_unknown_args** decorators
        * See [subcommands.py](https://github.com/python-cmd2/cmd2/blob/master/examples/subcommands.py) for an example of how to use subcommands
        * Tab completion of subcommand names is automatically supported
    * The **__relative_load** command is now hidden from the help menu by default
        * This command is not intended to be called from the command line, only from within scripts
    * The **set** command now has an additional **-a/--all** option to also display read-only settings
    * The **history** command can now run, edit, and save prior commands, in addition to displaying prior commands.
    * The **history** command can now automatically generate a transcript file for regression testing
        * This makes creating regression tests for your ``cmd2`` application trivial
* Commands Removed
    * The **cmdenvironment** has been removed and its functionality incorporated into the **-a/--all** argument to **set**
    * The **show** command has been removed.  Its functionality has always existing within **set** and continues to do so
    * The **save** command has been removed. The capability to save commands is now part of the **history** command.
    * The **run** command has been removed. The capability to run prior commands is now part of the **history** command.
* Other changes
    * The **edit** command no longer allows you to edit prior commands. The capability to edit prior commands is now part of the **history** command. The **edit** command still allows you to edit arbitrary files.
    * the **autorun_on_edit** setting has been removed.
    * For Python 3.4 and earlier, ``cmd2`` now has an additional dependency on the ``contextlib2`` module
* Deprecations
    * The old **options** decorator for optparse-based argument parsing is now *deprecated*
        * The old decorator is still present for now, but will be removed in a future release
        * ``cmd2`` no longer includes **optparse.make_option**, so if your app needs it import directly from optparse

## 0.7.9 (January 4, 2018)

* Bug Fixes
    * Fixed a couple broken examples
* Enhancements
    * Improved documentation for modifying shortcuts (command aliases)
    * Made ``pyreadline`` a dependency on Windows to ensure tab completion works
* Other changes
    * Abandoned official support for Python 3.3.  It should still work, just don't have an easy way to test it anymore.

## 0.7.8 (November 8, 2017)

* Bug Fixes
    * Fixed ``poutput()`` so it can print an integer zero and other **falsy** things
    * Fixed a bug which was causing autodoc to fail for building docs on Readthedocs
    * Fixed bug due to ``pyperclip`` dependency radically changing its project structure in latest version
* Enhancements
    * Improved documentation for user-settable environment parameters
    * Improved documentation for overriding the default supported comment styles
    * Added ``runcmds_plus_hooks()`` method to run multiple commands w/o a cmdloop

## 0.7.7 (August 25, 2017)

* Bug Fixes
    * Added workaround for bug which occurs in Python 2.7 on Linux when ``pygtk`` is installed
    * ``pfeedback()`` now honors feedback_to_output setting and won't redirect when it is ``False``
    * For ``edit`` command, both **editor** and **filename** can now have spaces in the name/path
    * Fixed a bug which occurred when stdin was a pipe instead of a tty due to input redirection
* Enhancements
    * ``feedback_to_output`` now defaults to ``False`` so info like command timing won't redirect
    * Transcript regular expressions now have predictable, tested, and documented behavior
        * This makes a breaking change to the format and expectations of transcript testing
        * The prior behavior removed whitespace before making the comparison, now whitespace must match exactly
        * Prior version did not allow regexes with whitespace, new version allows any regex
    * Improved display for ``load`` command and input redirection when **echo** is ``True``

## 0.7.6 (August 11, 2017)

* Bug Fixes
    * Case-sensitive command parsing was completely broken and has been fixed
    * ``<Ctrl>+d`` now properly quits when case-sensitive command parsing is enabled
    * Fixed some pyperclip clipboard interaction bugs on Linux
    * Fixed some timing bugs when running unit tests in parallel by using monkeypatch
* Enhancements
    * Enhanced tab completion of cmd2 command names to support case-insensitive completion
    * Added an example showing how to remove unused commands
    * Improved how transcript testing handles prompts with ANSI escape codes by stripping them
    * Greatly improved implementation for how command output gets piped to a shell command

## 0.7.5 (July 8, 2017)

* Bug Fixes
    * `case_insensitive` is no longer a runtime-settable parameter, but it was still listed as such
    * Fixed a recursive loop bug when abbreviated commands are enabled and it could get stuck in the editor forever
        * Added additional command abbreviations to the "exclude from history" list
    * Fixed argparse_example.py and pirate.py examples and transcript_regex.txt transcript
    * Fixed a bug in a unit test which occurred under unusual circumstances
* Enhancements
    * Organized all attributes used to configure the ParserManager into a single location
    * Set the default value of `abbrev` to `False` (which controls whether or not abbreviated commands are allowed)
        * With good tab completion of command names, using abbreviated commands isn't particularly useful
        * And it can create complications if you are't careful
    * Improved implementation of `load` to use command queue instead of nested inner loop

## 0.7.4 (July 3, 2017)

* Bug fixes
    * Fixed a couple bugs in interacting with pastebuffer/clipboard on macOS and Linux
    * Fixed a couple bugs in edit and save commands if called when history is empty
    * Ability to pipe ``cmd2`` command output to a shell command is now more reliable, particularly on Windows
    * Fixed a bug in ``pyscript`` command on Windows related to ``\`` being interpreted as an escape
* Enhancements
    * Ensure that path and shell command tab completion results are alphabetically sorted
    * Removed feature for load command to load scripts from URLS
        * It didn't work, there were no unit tests, and it felt out of place
    * Removed presence of a default file name and default file extension
        * These also strongly felt out of place
        * ``load`` and ``_relative_load`` now require a file path
        * ``edit`` and ``save`` now use a temporary file if a file path isn't provided
    * ``load`` command has better error checking and reporting
    * Clipboard copy and paste functionality is now handled by the **pyperclip** module
    * ``shell`` command now supports redirection and piping of output
    * Added a lot of unit tests
* Other changes
    * Removed pause command
    * Added a dependency on the **pyperclip** module

## 0.7.3 (June 23, 2017)

* Bug fixes
    * Fixed a bug in displaying a span of history items when only an end index is supplied
    * Fixed a bug which caused transcript test failures to display twice
* Enhancements
    * Added the ability to exclude commands from the help menu (**eof** included by default)
    * Redundant **list** command removed and features merged into **history** command
    * Added **pyscript** command which supports tab completion and running Python scripts with arguments
    * Improved tab completion of file system paths, command names, and shell commands
        * Thanks to Kevin Van Brunt for all of the help with debugging and testing this
    * Changed default value of USE_ARG_LIST to True - this affects the beavhior of all **@options** commands
        * **WARNING**: This breaks backwards compatibility, to restore backwards compatibility, add this to the
          **__init__()** method in your custom class derived from cmd2.Cmd:
            * cmd2.set_use_arg_list(False)
        * This change improves argument parsing for all new applications
    * Refactored code to encapsulate most of the pyparsing logic into a ParserManager class

## 0.7.2 (May 22, 2017)

* Added a MANIFEST.ini file to make sure a few extra files get included in the PyPI source distribution

## 0.7.1 (May 22, 2017)

* Bug fixes
    * ``-`` wasn't being treated as a legal character
    * The allow_cli_args attribute wasn't properly disabling parsing of args at invocation when False
    * py command wasn't allowing scripts which used *cmd* function prior to entering an interactive Python session
    * Don't throw exception when piping output to a shell command
    * Transcript testing now properly calls ``preloop`` before and ``postloop`` after
    * Fixed readline bug related to ANSI color escape codes in the prompt
* Added CONTRIBUTING.md and CODE_OF_CONDUCT.md files
* Added unicode parsing unit tests and listed unicode support as a feature when using Python 3
* Added more examples and improved documentation
    * Example for how use cmd2 in a way where it doesn't own the main loop so it can integrate with external event loops
    * Example for how to use argparse for parsing command-line args at invocation
    * Example for how to use the **py** command to run Python scripts which use conditional control flow
    * Example of how to use regular expressions in a transcript test
* Added CmdResult namedtumple for returning and storing results
* Added local file system path completion for ``edit``, ``load``, ``save``, and ``shell`` commands
* Add shell command completion for ``shell`` command or ``!`` shortcut
* Abbreviated multiline commands are no longer allowed (they never worked correctly anyways)

## 0.7.0 (February 23, 2017)

* Refactored to use six module for a unified codebase which supports both Python 2 and Python 3
* Stabilized on all platforms (Windows, Mac, Linux) and all supported Python versions (2.7, 3.3, 3.4, 3.5, 3.6, PyPy)
* Added lots of unit tests and fixed a number of bugs
* Improved documentation and moved it to cmd2.readthedocs.io


## 0.6.9 (October 3, 2016)

* Support Python 3 input()
* Fix subprocess.mswindows bug
* Add Python3.6 support
* Drop distutils from setup.py


## 0.6.8 (December 9, 2014)

* better editor checking (by Ian Cordascu)


## 0.6.6.1 (August 14, 2013)

* No changes to code trunk.  Generated sdist from Python 2.7 to avoid 2to3 changes being applied to source.  (Issue https://bitbucket.org/catherinedevlin/cmd2/issue/6/packaging-bug)


## 0.6.6 (August 6, 2013)

* Added fix by bitbucket.org/desaintmartin to silence the editor check.  bitbucket.org/catherinedevlin/cmd2/issue/1/silent-editor-check


## 0.6.5.1 (March 18, 2013)

* Bugfix for setup.py version check for Python 2.6, contributed by Tomaz Muraus (https://bitbucket.org/kami)


## 0.6.5 (February 29, 2013)

* Belatedly began a NEWS.txt
* Changed pyparsing requirement for compatibility with Python version (2 vs 3)
