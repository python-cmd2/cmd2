# flake8: noqa F821
# Tests how much a pyscript can affect cmd2.Cmd.py_locals

del [locals()["test_var"]]
my_list.append(2)
