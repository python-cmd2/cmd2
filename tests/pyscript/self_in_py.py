# Tests self_in_py in pyscripts
from __future__ import annotations

if 'self' in globals():
    print("I see self")
else:
    print("I do not see self")
