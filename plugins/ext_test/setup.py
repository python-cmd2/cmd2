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
    name='cmd2-ext-test',
    version='0.2.0',
    # TODO: Figure out why this doesn't work on CI Server
    # use_scm_version={
    #     'root': '../..',
    #     'relative_to': __file__,
    #     'git_describe_command': 'git describe --dirty --tags --long --match plugin-ext-test*'
    # },

    description='External test plugin for cmd2. Allows for external invocation of commands as if from a cmd2 pyscript',
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords='cmd2 test plugin',

    author='Eric Lin',
    author_email='anselor@gmail.com',
    url='https://github.com/python-cmd2/cmd2-ext-test',
    license='MIT',

    packages=['cmd2_ext_test'],

    python_requires='>=3.4',
    install_requires=['cmd2 >= 0.9.4, <=2'],
    setup_requires=['setuptools_scm >= 3.0'],

    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
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
        'dev': ['setuptools_scm', 'pytest', 'codecov', 'pytest-cov',
                'pylint', 'invoke', 'wheel', 'twine']
    },
)
