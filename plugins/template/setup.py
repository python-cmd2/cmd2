#
# coding=utf-8

import os

import setuptools

#
# get the long description from the README file
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setuptools.setup(
    name='cmd2-myplugin',
    # use_scm_version=True,  # use_scm_version doesn't work if setup.py isn't in the repository root
    version='2.0.0',
    description='A template used to build plugins for cmd2',
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords='cmd2 plugin',
    author='Kotfu',
    author_email='kotfu@kotfu.net',
    url='https://github.com/python-cmd2/cmd2-plugin-template',
    license='MIT',
    packages=['cmd2_myplugin'],
    python_requires='>=3.6',
    install_requires=['cmd2 >= 2, <3'],
    setup_requires=['setuptools_scm'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
    # dependencies for development and testing
    # $ pip install -e .[dev]
    extras_require={
        'test': [
            'codecov',
            'coverage',
            'pytest',
            'pytest-cov',
        ],
        'dev': ['setuptools_scm', 'pytest', 'codecov', 'pytest-cov', 'pylint', 'invoke', 'wheel', 'twine'],
    },
)
