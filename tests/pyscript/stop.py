# flake8: noqa F821
app.cmd_echo = True
app('help')

# This will set stop to True in the PyBridge
app('quit')

# Exercise py_quit() in unit test
quit()
