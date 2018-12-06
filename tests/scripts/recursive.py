#!/usr/bin/env python
# coding=utf-8
# flake8: noqa F821
"""
Example demonstrating that running a Python script recursively inside another Python script isn't allowed
"""
app.cmd_echo = True
app('pyscript ../script.py')
