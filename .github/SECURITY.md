# Security Policy

## Security Maintainer

The `cmd2` project has a single named Security Maintainer:

- **Todd Leonhardt** ([@tleonhardt](https://github.com/tleonhardt))

The Security Maintainer triages vulnerability reports, coordinates fixes, publishes security
advisories, and requests CVE identifiers when appropriate. Within the
[python-cmd2](https://github.com/python-cmd2) GitHub organization, the Security Maintainer holds the
**Security manager** organization role.

## Supported Versions

All `cmd2` releases are tagged and published from the `main` branch, and there are no long-lived
maintenance branches. Security fixes ship in a new release of the latest version.

| Version            | Supported          |
| ------------------ | ------------------ |
| Latest 4.x release | :white_check_mark: |
| Older releases     | :x:                |

If you are using an older release, please upgrade to the latest version from
[PyPI](https://pypi.org/project/cmd2/).

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues, pull requests, or
discussions.**

Report vulnerabilities privately using GitHub's private vulnerability reporting:

1. Go to the [Security tab](https://github.com/python-cmd2/cmd2/security) of this repository.
2. Click **Report a vulnerability**, or go directly to the
   [new advisory form](https://github.com/python-cmd2/cmd2/security/advisories/new).

Please include as much of the following as you can:

- The `cmd2` version, Python version, and operating system
- A description of the vulnerability and its impact
- Step-by-step instructions or a minimal proof of concept to reproduce it
- Any known workarounds or suggested fixes

## What to Expect

`cmd2` is maintained by volunteers, so these are good-faith targets rather than guarantees:

- **Acknowledgement** of your report within 7 days
- **Initial assessment** within 14 days, including whether the report is accepted as a vulnerability
  and its severity
- **Status updates** as a fix progresses

Once a fix is ready, we will release a patched version, publish a
[GitHub Security Advisory](https://github.com/python-cmd2/cmd2/security/advisories), and request a
CVE if appropriate. Reporters are credited in the advisory unless they prefer to remain anonymous.
Please keep the vulnerability confidential until the advisory is published.

## Scope

`cmd2` is a framework for building interactive command-line applications. Several of its builtin
features intentionally give the user of a `cmd2` application access to the operating system or to a
Python interpreter. Behavior of these features that is working as designed is not a vulnerability in
`cmd2`:

- The `shell` command (and its `!` shortcut) runs operating system commands.
- The `edit` command launches an external editor program.
- The `run_script` command (and its `@` shortcut) runs `cmd2` command scripts.
- The `run_pyscript` command, and the optional `py` and `ipy` commands, run Python code.
- Output redirection (`>`, `>>`) and pipes (`|`) write to files and run shell commands.

Developers who expose a `cmd2` application to untrusted users are responsible for removing or
disabling the features they do not want to offer. See
[Remove Builtin Commands](https://cmd2.readthedocs.io/en/latest/features/builtin_commands/#remove-builtin-commands),
[Disabling Commands](https://cmd2.readthedocs.io/en/latest/features/disable_commands/), and
[Disabling Redirection](https://cmd2.readthedocs.io/en/latest/features/redirection/#disabling-redirection).

A flaw in how these safeguards work is in scope. Examples include a way to perform redirection when
`allow_redirection` is `False`, or a way to run a command that was removed or disabled.
