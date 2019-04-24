# flake8: noqa F821
# This script demonstrates when output of a command finalization hook is captured by a pyscript app() call
import sys

# The unit test framework passes in the string being printed by the command finalization hook
hook_output = sys.argv[1]

# Run a help command which results in 1 call to onecmd_plus_hooks
res = app('help')

# hook_output will not be captured because there are no nested calls to onecmd_plus_hooks
if hook_output not in res.stdout:
    print("PASSED")
else:
    print("FAILED")

# Run the last command in the history
res = app('history -r -1')

# All output of the history command will be captured. This includes all output of the commands
# started in do_history() using onecmd_plus_hooks(), including any output in those commands' hooks.
# Therefore we expect the hook_output to show up this time.
if hook_output in res.stdout:
    print("PASSED")
else:
    print("FAILED")
