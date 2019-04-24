# flake8: noqa F821
# This script demonstrates when output of a command finalization hook is captured by a pyscript app() call
import sys

# The unit test framework passes in the string being printed by the command finalization hook
hook_output = sys.argv[1]

# hook_output will not be captured because there are no nested calls to onecmd_plus_hooks
res = app('help')
if hook_output not in res.stdout:
    print("PASSED")
else:
    print("FAILED")

# hook_output will be captured in the nested call to onecmd_plus_hooks that occurs in do_history()
res = app('history -r -1')
if hook_output in res.stdout:
    print("PASSED")
else:
    print("FAILED")
