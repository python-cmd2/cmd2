#!/usr/bin/python
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup
    def find_packages():
        return ['sqlpython']
import sys

if sys.version_info[:2] == (2, 5):
    install_requires = ['pyparsing == 1.5.7']
else:
    install_requires = ['pyparsing >= 2.0.1']

setup(
    name="cmd2",
    version="0.6.8",
    py_modules=["cmd2"],
    use_2to3=True,
    
    # metadata for upload to PyPI
    author = 'Catherine Devlin',
    author_email = 'catherine.devlin@gmail.com',
    description = "Extra features for standard library's cmd module",
    license = 'MIT',
    keywords = 'command prompt console cmd',
    url = 'http://packages.python.org/cmd2/',
    install_requires = install_requires,
    long_description = """Enhancements for standard library's cmd module.

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

Running `2to3 <http://docs.python.org/library/2to3.html>` against ``cmd2.py`` 
generates working, Python3-based code.

See docs at http://packages.python.org/cmd2/
""",

    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Programming Language :: Python',
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.0',
        'Programming Language :: Python :: 3.1',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',

    ],
    )

