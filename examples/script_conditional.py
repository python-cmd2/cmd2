# coding=utf-8
"""
This is a Python script intended to be used with the "python_scripting.py" cmd2 example application.

To run it you should do the following:
    ./python_scripting.py
    py run('script_conditional.py')

Note: The "cmd" function is defined within the cmd2 embedded Python environment and in there "self" is your cmd2
application instance.
"""

# Try to change to a non-existent directory
cmd('cd foobar')

# Conditionally do something based on the results of the last command
if self._last_result:
    print('Contents of foobar directory:')
    cmd('dir')

    # Change back to where we were
    cmd('cd ..')
else:
    # Change to parent directory
    cmd('cd ..')
    print('Contents of parent directory:')
    cmd('dir')

    # Change back to where we were
    cmd('cd examples')
