#!/usr/bin/python
# coding=utf-8
"""
Setuptools setup file, used to install or test 'cmd2'
"""
from setuptools import setup

VERSION = '0.7.0'
DESCRIPTION = "Extra features for standard library's cmd module"

LONG_DESCRIPTION = """cmd2 is an enhancement to the standard library's cmd module for Python 2.7
and Python 3.3+.   It is pure Python code with dependencies only on the six and pyparsing modules.

The latest documentation for cmd2 can be read online here:
https://cmd2.readthedocs.io/

Drop-in replacement adds several features for command-prompt tools:

    * Searchable command history (commands: "hi", "li", "run")
    * Load commands from file, save to file, edit commands in file
    * Multi-line commands
    * Case-insensitive commands
    * Special-character shortcut commands (beyond cmd's "@" and "!")
    * Settable environment parameters
    * Parsing commands with flags
    * > (filename), >> (filename) redirect output to file
    * < (filename) gets input from file
    * bare >, >>, < redirect to/from paste buffer
    * accepts abbreviated commands when unambiguous
    * `py` enters interactive Python console
    * test apps against sample session transcript (see example/example.py)

Useable without modification anywhere cmd is used; simply import cmd2.Cmd in place of cmd.Cmd.
"""

CLASSIFIERS = list(filter(None, map(str.strip,
"""
Development Status :: 5 - Production/Stable
Environment :: Console
Operating System :: OS Independent
Intended Audience :: Developers
Intended Audience :: System Administrators
License :: OSI Approved :: MIT License
Programming Language :: Python
Programming Language :: Python :: 2
Programming Language :: Python :: 2.7
Programming Language :: Python :: 3
Programming Language :: Python :: 3.3
Programming Language :: Python :: 3.4
Programming Language :: Python :: 3.5
Programming Language :: Python :: 3.6
Programming Language :: Python :: Implementation :: CPython
Programming Language :: Python :: Implementation :: PyPy
Topic :: Software Development :: Libraries :: Python Modules
""".splitlines())))

INSTALL_REQUIRES = ['pyparsing >= 2.0.1', 'six']
# unitest.mock was added in Python 3.3.  mock is a backport of unittest.mock to all versions of Python
TESTS_REQUIRE = ['mock', 'pytest']
DOCS_REQUIRE = ['sphinx', 'sphinx_rtd_theme', 'pyparsing', 'six']

setup(
    name="cmd2",
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    classifiers=CLASSIFIERS,
    author='Catherine Devlin',
    author_email='catherine.devlin@gmail.com',
    url='https://github.com/python-cmd2/cmd2',
    license='MIT',
    platforms=['any'],
    py_modules=["cmd2"],
    keywords='command prompt console cmd',
    install_requires=INSTALL_REQUIRES,
    tests_require=TESTS_REQUIRE,
    docs_require=DOCS_REQUIRE,
)
