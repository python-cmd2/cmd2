# flake8: noqa F821
# Tests that cmd2 populates __name__, __file__, and sets sys.path[0] to our directory
import os
import sys

app.cmd_echo = True

if __name__ != '__main__':
    print("Error: __name__ is: {}".format(__name__))
    quit()

if __file__ != sys.argv[0]:
    print("Error: __file__ is: {}".format(__file__))
    quit()

our_dir = os.path.dirname(os.path.abspath(__file__))
if our_dir != sys.path[0]:
    print("Error: our_dir is: {}".format(our_dir))
    quit()

print("PASSED")
