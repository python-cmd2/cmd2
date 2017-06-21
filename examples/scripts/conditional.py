# coding=utf-8
"""
This is a Python script intended to be used with the "python_scripting.py" cmd2 example application.

To run it you should do the following:
    ./python_scripting.py
    pyscript scripts/conditional.py directory_path

Note: The "cmd" function is defined within the cmd2 embedded Python environment and in there "self" is your cmd2
application instance.
"""
import os
import sys


if len(sys.argv) > 1:
    directory = sys.argv[1]
    print('Using specified directory: {!r}'.format(directory))
else:
    directory = 'foobar'
    print('Using default directory: {!r}'.format(directory))

# Keep track of where we stared
original_dir = os.getcwd()

# Try to change to the specified directory
cmd('cd {}'.format(directory))

# Conditionally do something based on the results of the last command
if self._last_result:
    print('\nContents of directory {!r}:'.format(directory))
    cmd('dir -l')

    # Change back to where we were
    print('Changing back to original directory: {!r}'.format(original_dir))
    cmd('cd {}'.format(original_dir))
else:
    # cd command failed, print a warning
    print('Failed to change directory to {!r}'.format(directory))
