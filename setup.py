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
Programming Language :: Python :: 3.5
Programming Language :: Python :: 3.6
Programming Language :: Python :: 3.7
Programming Language :: Python :: 3.8
Programming Language :: Python :: 3.9
Programming Language :: Python :: Implementation :: CPython
Topic :: Software Development :: Libraries :: Python Modules
""".splitlines())))  # noqa: E128

SETUP_REQUIRES = ['setuptools_scm >= 3.0']

INSTALL_REQUIRES = [
    'attrs >= 16.3.0',
    'colorama >= 0.3.7',
    'importlib_metadata>=1.6.0;python_version<"3.8"',
    'pyperclip >= 1.6',
    'setuptools >= 34.4',
    'wcwidth >= 0.1.7',
]

EXTRAS_REQUIRE = {
    # Windows also requires pyreadline to ensure tab completion works
    ":sys_platform=='win32'": ['pyreadline'],
    # Extra dependencies for running unit tests
    'test': [
        "gnureadline; sys_platform=='darwin'",  # include gnureadline on macOS to ensure it is available in nox env
        "mock ; python_version<'3.6'",  # for python 3.5 we need the third party mock module
        'codecov',
        'coverage',
        'pytest',
        'pytest-cov',
        'pytest-mock',
    ],
    # development only dependencies:  install with 'pip install -e .[dev]'
    'dev': ["mock ; python_version<'3.6'",  # for python 3.5 we need the third party mock module
            'pytest', 'codecov', 'pytest-cov', 'pytest-mock', 'nox', 'flake8',
            'sphinx', 'sphinx-rtd-theme', 'sphinx-autobuild', 'doc8',
            'invoke', 'twine>=1.11',
            ]
}

setup(
    name="cmd2",
    use_scm_version={
        'git_describe_command': 'git describe --dirty --tags --long --exclude plugin-*'
    },
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
    python_requires='>=3.5',
    setup_requires=SETUP_REQUIRES,
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
)
