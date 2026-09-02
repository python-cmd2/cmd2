<h1 align="center">cmd2: build feature-rich command-line applications in Python</h1>

[![Latest Version](https://img.shields.io/pypi/v/cmd2.svg?style=flat-square&label=latest%20stable%20version)](https://pypi.python.org/pypi/cmd2/)
[![Tests](https://github.com/python-cmd2/cmd2/actions/workflows/tests.yml/badge.svg)](https://github.com/python-cmd2/cmd2/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/python-cmd2/cmd2/branch/main/graph/badge.svg)](https://codecov.io/gh/python-cmd2/cmd2)
[![Documentation Status](https://readthedocs.org/projects/cmd2/badge/?version=latest)](http://cmd2.readthedocs.io/en/latest/?badge=latest)
<a href="https://discord.gg/RpVG6tk"><img src="https://img.shields.io/badge/chat-on%20discord-7289da.svg" alt="Chat"></a>

<p align="center">
  <a href="#quick-start">Quick start</a> •
  <a href="#why-cmd2">Why cmd2?</a> •
  <a href="#installation">Installation</a> •
  <a href="#documentation">Documentation</a> •
  <a href="#projects-using-cmd2">Projects using cmd2</a>
</p>

`cmd2` makes it quick to build powerful, polished command-line applications and REPLs in Python.
Start with a subclass of the standard library's
[`cmd.Cmd`](https://docs.python.org/3/library/cmd.html), then add commands while `cmd2` handles the
details that make an application pleasant to build and use: argument parsing, generated help, tab
completion, command history, scripting, output styling, and much more.

You can use `cmd2` for a small internal tool and grow the same application into an extensible,
scriptable interface without replacing the framework or writing the usual CLI boilerplate.

## Quick start

Install `cmd2`:

```bash
pip install cmd2
```

Then create `app.py`:

```python
from typing import Annotated

import cmd2
from cmd2.annotated import Argument, Option


class App(cmd2.Cmd):
    """A small interactive application."""

    @cmd2.with_annotated
    def do_greet(
        self,
        name: Annotated[str, Argument(help_text="person to greet")],
        count: Annotated[int, Option(help_text="number of greetings")] = 1,
    ) -> None:
        """Greet a person."""
        for _ in range(count):
            self.poutput(f"Hello, {name}!")


if __name__ == "__main__":
    App().cmdloop()
```

`cmd2` supports [Typer](https://typer.tiangolo.com/)-style syntax for specifying command arguments
with type annotations. In this example, `@cmd2.with_annotated` turns `name` and `count` into a
positional argument and an option.

Run it with `python app.py`. Your new `greet` command already has input validation, generated help,
and tab completion for its options. The application also includes discoverable help, command
history, aliases, macros, scripting, shell integration, and other built-in commands.

```console
(Cmd) help greet
Usage: greet [-h] [--count COUNT] name

(Cmd) greet --count 2 Ada
Hello, Ada!
Hello, Ada!
```

[![Animated demonstration of the cmd2 quick-start application](https://raw.githubusercontent.com/python-cmd2/cmd2/main/docs/assets/cmd2-readme-demo.gif)](https://raw.githubusercontent.com/python-cmd2/cmd2/main/docs/assets/cmd2-readme-demo.gif)

See the [getting started tutorial](https://cmd2.readthedocs.io/en/latest/examples/getting_started/)
to build a more complete application.

## Why cmd2?

### Build more with less code

- Define commands as Python methods and use familiar
  [`argparse`](https://cmd2.readthedocs.io/en/latest/features/argument_processing/) parsers for
  arguments and subcommands. A single parser definition drives validation, help, and completion.
- Render Rich tables and other styled objects, with consistent helpers for
  [normal output, errors, warnings, and paging](https://cmd2.readthedocs.io/en/latest/features/generating_output/).
- Organize large applications into independently testable and dynamically loadable
  [CommandSets](https://cmd2.readthedocs.io/en/latest/features/modular_commands/), and customize the
  command lifecycle with [hooks](https://cmd2.readthedocs.io/en/latest/features/hooks/).
- Integrate existing Python code, shell tools, or asynchronous work instead of restructuring your
  application around the framework.
- Run on Windows, macOS, and Linux with a pure-Python package and a small dependency footprint.

### Give users a capable interface from day one

- **Tab completion:** provide context-aware completion for commands, subcommands, options, choices,
  file paths, and custom data sources, with descriptive hints for completion candidates. Learn more
  about [completion](https://cmd2.readthedocs.io/en/latest/features/completion/).
- **History:** search, edit, rerun, save, and optionally persist previously entered commands. Users
  also get familiar navigation and reverse search such as <kbd>Ctrl</kbd>+<kbd>R</kbd>. Learn more
  about [history](https://cmd2.readthedocs.io/en/latest/features/history/).
- **Unicode:** accept Unicode in commands, arguments, file names, and output, and run UTF-8 command
  scripts for applications used in any language. Learn more about
  [command scripts](https://cmd2.readthedocs.io/en/latest/features/scripting/#command-scripts).
- **Shell shortcuts and hotkeys:** use familiar Readline-style keyboard shortcuts for navigating and
  editing the command line, including Emacs-style bindings provided by `prompt-toolkit`. Learn more
  about [keyboard shortcuts](https://cmd2.readthedocs.io/en/latest/features/history/#for-users).
- **Help:** generate discoverable, categorized help for commands, subcommands, and arguments
  directly from their argument parsers. Learn more about
  [help](https://cmd2.readthedocs.io/en/latest/features/help/).
- **Rich UI/UX:** offer syntax highlighting, Fish-style history suggestions, multiline input,
  configurable prompts, completion menus, themes, and an optional bottom toolbar. Learn more about
  [prompts and toolbars](https://cmd2.readthedocs.io/en/latest/features/prompt/) and
  [themes](https://cmd2.readthedocs.io/en/latest/features/theme/).

### Grow from exploration to automation

- **Shell scripting:** automate the same commands users run interactively by passing them as command
  arguments or standard input from shell scripts. Learn more about
  [automating cmd2 applications](https://cmd2.readthedocs.io/en/latest/features/os/#automating-cmd2-apps-from-other-cliclu-tools).
- **Python scripting:** run Python scripts inside the application for loops, branching, complex
  control flow, and integration with the application's commands and data. Learn more about
  [Python scripts](https://cmd2.readthedocs.io/en/latest/features/scripting/#python-scripts).
- **Run shell commands:** execute operating-system commands without leaving the application, using
  the built-in `shell` command or its `!` shortcut. Learn more about
  [OS integration](https://cmd2.readthedocs.io/en/latest/features/os/#executing-os-commands-from-within-cmd2).
- **Redirect output:** send command output to files or the clipboard, or pipe it through one or more
  shell commands. Learn more about
  [output redirection and pipes](https://cmd2.readthedocs.io/en/latest/features/redirection/).
- **Aliases, macros, and shortcuts:** let users customize names, parameterized commands, and terse
  shortcuts for repetitive workflows without changing the application. Learn more about
  [aliases, macros, and shortcuts](https://cmd2.readthedocs.io/en/latest/features/shortcuts_aliases_macros/).
- **Startup scripts:** initialize an application consistently by running saved commands every time
  it starts. Learn more about
  [startup commands and scripts](https://cmd2.readthedocs.io/en/latest/features/startup_commands/).
- **Embedded Python and IPython shells:** drop into an interactive Python or IPython session for
  experimentation, debugging, object introspection, and access to application state. Learn more
  about
  [embedded Python shells](https://cmd2.readthedocs.io/en/latest/features/embedded_python_shells/).
- **Color, style, and tables:** produce readable output with Rich colors and styles, custom themes,
  paging, and flexible table layouts. Learn more about
  [generating output](https://cmd2.readthedocs.io/en/latest/features/generating_output/) and
  [creating tables](https://cmd2.readthedocs.io/en/latest/features/table_creation/).

## Installation

On all operating systems, the latest stable version of `cmd2` can be installed using pip:

```bash
pip install -U cmd2
```

cmd2 works with Python 3.11+ on Windows, macOS, and Linux. It is pure Python code with few 3rd-party
dependencies. It works with both conventional CPython and free-threaded variants.

For information on other installation options, see
[Installation Instructions](https://cmd2.readthedocs.io/en/latest/overview/installation/) in the
cmd2 documentation.

<!-- prettier-ignore -->
> [!IMPORTANT]
> Upgrading from an older release? Versions 3.x and 4.x include significant
> backwards-incompatible changes. Review the [changelog](https://github.com/python-cmd2/cmd2/blob/main/CHANGELOG.md)
> and [migration guide](https://cmd2.readthedocs.io/en/latest/upgrades/) before upgrading.

## Documentation

Read the [latest documentation](https://cmd2.readthedocs.io/en/latest/) online or download it in
HTML, PDF, and ePub formats. The
[`examples`](https://github.com/python-cmd2/cmd2/tree/main/examples) directory contains focused,
runnable demonstrations of individual features.

## Tutorials

- [cmd2 example applications](https://github.com/python-cmd2/cmd2/tree/main/examples)
    - Basic cmd2 examples to demonstrate how to use various features
- [Advanced Examples](https://github.com/jayrod/cmd2-example-apps)
    - More complex examples that demonstrate more features about how to put together a complete
      application
- [Cookiecutter](https://github.com/cookiecutter/cookiecutter) Templates from community
    - Basic cookiecutter template for cmd2 application :
      https://github.com/jayrod/cookiecutter-python-cmd2
    - Advanced cookiecutter template with external plugin support :
      https://github.com/jayrod/cookiecutter-python-cmd2-ext-plug

## Found a bug?

If you think you've found a bug, please first read through the open
[Issues](https://github.com/python-cmd2/cmd2/issues). If you're confident it's a new bug, go ahead
and create a new GitHub issue. Be sure to include as much information as possible so we can
reproduce the bug. At a minimum, please state the following:

- `cmd2` version
- Python version
- OS name and version
- What you did to cause the bug to occur
- Include any traceback or error message associated with the bug

## Projects using cmd2

| Application Name                                                | Description                                                                                                                      | Organization or Author                                                |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| [CephFS Shell](https://github.com/ceph/ceph)                    | The Ceph File System, or CephFS, is a POSIX-compliant file system built on top of Ceph’s distributed object store                | [ceph](https://ceph.com/)                                             |
| [garak](https://github.com/NVIDIA/garak)                        | LLM vulnerability scanner that checks if an LLM can be made to fail in a way we don't want                                       | [NVIDIA](https://github.com/NVIDIA)                                   |
| [Argus](https://github.com/jasonxtn/argus)                      | The Ultimate Information Gathering Toolkit                                                                                       | [JASON13](https://github.com/jasonxtn)                                |
| [medusa](https://github.com/Ch0pin/medusa)                      | Binary instrumentation framework that that automates processes for the dynamic analysis of Android and iOS Applications          | [Ch0pin](https://github.com/Ch0pin)                                   |
| [InternalBlue](https://github.com/seemoo-lab/internalblue)      | Bluetooth experimentation framework for Broadcom and Cypress chips                                                               | [Secure Mobile Networking Lab](https://github.com/seemoo-lab)         |
| [SCCMHunter](https://github.com/garrettfoster13/sccmhunter)     | A post-ex tool built to streamline identifying, profiling, and attacking SCCM related assets in an Active Directory domain       | [Garret Foster](https://github.com/garrettfoster13)                   |
| [Unipacker](https://github.com/unipacker/unipacker)             | Automatic and platform-independent unpacker for Windows binaries based on emulation                                              | [unipacker](https://github.com/unipacker)                             |
| [Frankenstein](https://github.com/seemoo-lab/frankenstein)      | Broadcom and Cypress firmware emulation for fuzzing and further full-stack debugging                                             | [Secure Mobile Networking Lab](https://github.com/seemoo-lab)         |
| [Poseidon](https://github.com/faucetsdn/poseidon)               | Leverages software-defined networks (SDNs) to acquire and then feed network traffic to a number of machine learning techniques.  | [Faucet SDN](https://github.com/faucetsdn)                            |
| [DFTimewolf](https://github.com/log2timeline/dftimewolf)        | A framework for orchestrating forensic collection, processing and data export                                                    | [log2timeline](https://github.com/log2timeline)                       |
| [LazyOwn](https://github.com/grisuno/LazyOwn)                   | The first RedTeam/APT Framework with an AI-powered C&C, featuring rootkits to conceal campaigns, undetectable malleable implants | [Grisuno](https://github.com/grisuno)                                 |
| [GAP SDK](https://github.com/GreenWaves-Technologies/gap_sdk)   | SDK for Greenwaves Technologies' GAP8 IoT Application Processor                                                                  | [GreenWaves Technologies](https://github.com/GreenWaves-Technologies) |
| [REW Sploit](https://github.com/REW-sploit/REW-sploit)          | Emulate and Dissect Metasploit Framework (MSF) and other attacks                                                                 | [REW-sploit](https://github.com/REW-sploit)                           |
| [tomcatmanager](https://github.com/tomcatmanager/tomcatmanager) | A command line tool and python library for managing a tomcat server                                                              | [tomcatmanager](https://github.com/tomcatmanager)                     |
| [Falcon Toolkit](https://github.com/CrowdStrike/Falcon-Toolkit) | Unleash the power of the CrowdStrike Falcon Platform at the CLI                                                                  | [CrowdStrike](https://github.com/CrowdStrike)                         |
| [EXPLIoT](https://gitlab.com/expliot_framework/expliot)         | Internet of Things Security Testing and Exploitation framework                                                                   | [expliot_framework](https://gitlab.com/expliot_framework/)            |
| [Pobshell](https://github.com/pdalloz/pobshell)                 | A Bash‑like shell for live Python objects: `cd`, `ls`, `cat`, `find` and _CLI piping_ for object code, str values & more         | [Peter Dalloz](https://www.linkedin.com/in/pdalloz)                   |

Possibly defunct but still good examples

| Application Name                                                              | Description                                                                            | Organization or Author                                         |
| ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| [Katana](https://github.com/JohnHammond/katana)                               | Automatic CTF Challenge Solver                                                         | [John Hammond](https://github.com/JohnHammond)                 |
| [SatanSword](https://github.com/Lucifer1993/SatanSword) (in Chinese)          | Comprehensive Penetration Framework for Red Teaming                                    | [Lucifer1993](https://github.com/Lucifer1993)                  |
| [Jok3r](http://www.jok3r-framework.com)                                       | Network & Web Pentest Automation Framework                                             | [Koutto](https://github.com/koutto)                            |
| [Counterfit](https://github.com/Azure/counterfit)                             | a CLI that provides a generic automation layer for assessing the security of ML models | [Microsoft Azure](https://github.com/Azure)                    |
| [Overlord](https://github.com/qsecure-labs/overlord)                          | Red Teaming Infrastructure Automation                                                  | [QSecure Labs](https://github.com/qsecure-labs)                |
| [Automated Reconnaissance Pipeline](https://github.com/epi052/recon-pipeline) | An automated target reconnaissance pipeline                                            | [epi052](https://github.com/epi052)                            |
| [JSShell](https://github.com/Den1al/JSShell)                                  | An interactive multi-user web JavaScript (JS) shell                                    | [Den1al](https://github.com/Den1al)                            |
| [RedShell](https://github.com/Verizon/redshell)                               | An interactive command prompt for red teaming and pentesting                           | [Verizon](https://github.com/Verizon)                          |
| [FLASHMINGO](https://github.com/mandiant/flashmingo)                          | Automatic analysis of SWF files based on some heuristics. Extensible via plugins.      | [Mandiant](https://github.com/mandiant)                        |
| [psiTurk](https://github.com/NYUCCL/psiTurk)                                  | An open platform for science on Amazon Mechanical Turk                                 | [NYU Computation and Cognition Lab](https://github.com/NYUCCL) |

Note: If you have created an application based on `cmd2` that you would like us to mention here,
please get in touch.
