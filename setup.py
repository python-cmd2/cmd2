#!/usr/bin/python
# coding=utf-8
"""
Setuptools setup file, used to install or test 'cmd2'
"""
import codecs
from setuptools import setup

DESCRIPTION = "cmd2 - quickly build feature-rich and user-friendly interactive command line applications in Python"

with codecs.open('README.md', encoding='utf8') as f:
    LONG_DESCRIPTION = f.read()

CLASSIFIERS = list(filter(None, map(str.strip,
"""
Development Status :: 5 - Production/Stable
Environment :: Console
Operating System :: OS Independent
Intended Audience :: Developers
Intended Audience :: System Administrators
License :: OSI Approved :: MIT License
Programming Language :: Python
Programming Language :: Python :: 3
Programming Language :: Python :: 3.4
Programming Language :: Python :: 3.5
Programming Language :: Python :: 3.6
Programming Language :: Python :: 3.7
Programming Language :: Python :: Implementation :: CPython
Topic :: Software Development :: Libraries :: Python Modules
""".splitlines())))  # noqa: E128

SETUP_REQUIRES = ['setuptools_scm']

INSTALL_REQUIRES = ['pyperclip >= 1.5.27', 'colorama', 'attrs >= 16.3.0', 'wcwidth >= 0.1.7']

EXTRAS_REQUIRE = {
    # Windows also requires pyreadline to ensure tab completion works
    ":sys_platform=='win32'": ['pyreadline'],
    # Python 3.4 and earlier require contextlib2 for temporarily redirecting stderr and stdout
    ":python_version<'3.5'": ['contextlib2', 'typing'],
    # Extra dependencies for running unit tests
    'test': ["gnureadline; sys_platform=='darwin'",  # include gnureadline on macOS to ensure it is available in tox env
             "mock ; python_version<'3.6'",  # for python 3.5 and earlier we need the third party mock module
             'codecov', 'pytest', 'pytest-cov', 'pytest-mock'],
    # development only dependencies:  install with 'pip install -e .[dev]'
    'dev': ["mock ; python_version<'3.6'",  # for python 3.5 and earlier we need the third party mock module
            'pytest', 'codecov', 'pytest-cov', 'pytest-mock', 'tox', 'pylint',
            'sphinx', 'sphinx-rtd-theme', 'sphinx-autobuild', 'invoke', 'twine>=1.11',
            ]
}

setup(
    name="cmd2",
    use_scm_version=True,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    classifiers=CLASSIFIERS,
    author='Catherine Devlin',
    author_email='catherine.devlin@gmail.com',
    url='https://github.com/python-cmd2/cmd2',
    license='MIT',
    platforms=['any'],
    packages=['cmd2'],
    keywords='command prompt console cmd',
    python_requires='>=3.4',
    setup_requires=SETUP_REQUIRES,
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
)
