#
# coding=utf-8

import os

import setuptools

#
# get the long description from the README file
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# scm_version = {
#     'root': '../..',
#     'git_describe_command': "git describe --dirty --tags --long --match plugin-ext-test*",
# }

PACKAGE_DATA = {
    'cmd2_ext_test': ['py.typed'],
}

setuptools.setup(
    name='cmd2-ext-test',
    version='2.0.0',
    description='External test plugin for cmd2. Allows for external invocation of commands as if from a cmd2 pyscript',
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords='cmd2 test plugin',
    author='Eric Lin',
    author_email='anselor@gmail.com',
    url='https://github.com/python-cmd2/cmd2/tree/master/plugins/ext_test',
    license='MIT',
    package_data=PACKAGE_DATA,
    packages=['cmd2_ext_test'],
    python_requires='>=3.6',
    install_requires=['cmd2 >= 2, <3'],
    setup_requires=['setuptools >= 42', 'setuptools_scm >= 3.4'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
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
        'test': ['codecov', 'coverage', 'pytest', 'pytest-cov'],
        'dev': ['setuptools_scm', 'pytest', 'codecov', 'pytest-cov', 'pylint', 'invoke', 'wheel', 'twine'],
    },
)
