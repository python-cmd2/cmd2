# Tests how much a pyscript can affect cmd2.Cmd.py_locals
from __future__ import annotations

del [locals()["test_var"]]
my_list.append(2)
