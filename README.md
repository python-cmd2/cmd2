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
import argparse

import cmd2


greet_parser = cmd2.Cmd2ArgumentParser()
greet_parser.add_argument("name", help="person to greet")
greet_parser.add_argument("--count", type=int, default=1, help="number of greetings")


class App(cmd2.Cmd):
    """A small interactive application."""

    @cmd2.with_argparser(greet_parser)
    def do_greet(self, args: argparse.Namespace) -> None:
        """Greet a person."""
        for _ in range(args.count):
            self.poutput(f"Hello, {args.name}!")


if __name__ == "__main__":
    App().cmdloop()
```

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

- Context-aware [tab completion](https://cmd2.readthedocs.io/en/latest/features/completion/) for
  commands, subcommands, options, choices, file paths, and custom data sources.
- Generated, categorized [help](https://cmd2.readthedocs.io/en/latest/features/help/) that stays in
  sync with each command's argument parser.
- Editable and optionally persistent
  [history](https://cmd2.readthedocs.io/en/latest/features/history/), multiline commands,
  configurable prompts, runtime settings, and built-in editor support.
- [Aliases, macros, and shortcuts](https://cmd2.readthedocs.io/en/latest/features/shortcuts_aliases_macros/)
  that let users adapt repetitive workflows without application changes.
- [Pipes and output redirection](https://cmd2.readthedocs.io/en/latest/features/redirection/), shell
  commands, clipboard integration, and styled terminal output.

### Grow from exploration to automation

An interactive session does not have to become a dead end. Users can replay commands from history,
save and run command scripts, execute Python scripts, pass startup commands from the shell, or use a
Python API exposed by the application. The commands they discover interactively become the same
commands they automate later. See the
[scripting guide](https://cmd2.readthedocs.io/en/latest/features/scripting/) for the available
approaches.

## Installation

On all operating systems, the latest stable version of `cmd2` can be installed using pip:

```bash
pip install -U cmd2
```

cmd2 works with Python 3.11+ on Windows, macOS, and Linux. It is pure Python code with few 3rd-party
dependencies. It works with both conventional CPython and free-threaded variants.

For information on other installation options, see
[Installation Instructions](https://cmd2.readthedocs.io/en/latest/overview/installation.html) in the
cmd2 documentation.

> [!IMPORTANT] Upgrading from an older release? Versions 3.x and 4.x include significant
> backwards-incompatible changes. Review the [changelog](./CHANGELOG.md) and
> [migration guide](https://cmd2.readthedocs.io/en/latest/upgrades/) before upgrading.

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
