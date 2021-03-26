# flake8: noqa F821
# Tests self_in_py in pyscripts
if 'self' in globals():
    print("I see self")
else:
    print("I do not see self")
