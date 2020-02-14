#!/usr/bin/env python
# coding=utf-8
# flake8: noqa F821
"""
Example demonstrating that calling run_pyscript recursively inside another Python script isn't allowed
"""
import os
import sys

app.cmd_echo = True
my_dir = (os.path.dirname(os.path.realpath(sys.argv[0])))
app('run_pyscript {}'.format(os.path.join(my_dir, 'stop.py')))
