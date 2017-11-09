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
    * Enhanced tab-completion of cmd2 command names to support case-insensitive completion
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
        * With good tab-completion of command names, using abbreviated commands isn't particularly useful
        * And it can create complications if you are't careful
    * Improved implementation of `load` to use command queue instead of nested inner loop

## 0.7.4 (July 3, 2017)

* Bug fixes
    * Fixed a couple bugs in interacting with pastebuffer/clipboard on macOS and Linux
    * Fixed a couple bugs in edit and save commands if called when history is empty
    * Ability to pipe ``cmd2`` command output to a shell command is now more reliable, particularly on Windows
    * Fixed a bug in ``pyscript`` command on Windows related to ``\`` being interpreted as an escape
* Enhancements
    * Ensure that path and shell command tab-completion results are alphabetically sorted
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
    * Added **pyscript** command which supports tab-completion and running Python scripts with arguments
    * Improved tab-completion of file system paths, command names, and shell commands
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
