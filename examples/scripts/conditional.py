"""This is a Python script intended to be used with the "python_scripting.py" cmd2 example application.

To run it you should do the following:
    ./python_scripting.py
    run_pyscript scripts/conditional.py directory_path

Note: The "app" function is defined within the cmd2 embedded Python environment and in there "self" is your cmd2
application instance. Note: self only exists in this environment if self_in_py is True.
"""

import os
import sys

if len(sys.argv) > 1:
    directory = sys.argv[1]
    print(f'Using specified directory: {directory!r}')
else:
    directory = 'foobar'
    print(f'Using default directory: {directory!r}')

# Keep track of where we stared
original_dir = os.getcwd()

# Try to change to the specified directory
result = app(f'cd {directory}')

# Conditionally do something based on the results of the last command
if result:
    print(f"STDOUT: {result.stdout}\n")
    print(f"STDERR: {result.stderr}\n")

    print(f'\nContents of directory {directory!r}:')
    result = app('dir -l')

    print(f"STDOUT: {result.stdout}\n")
    print(f"STDERR: {result.stderr}\n")

    print(f'{result.data}\n')

    # Change back to where we were
    print(f'Changing back to original directory: {original_dir!r}')
    app(f'cd {original_dir}')
else:
    # cd command failed, print a warning
    print(f'Failed to change directory to {directory!r}')

    print(f"STDOUT: {result.stdout}\n")
    print(f"STDERR: {result.stderr}\n")
