# flake8: noqa F821
import os

app.cmd_echo = True
my_dir = (os.path.dirname(os.path.realpath(sys.argv[0])))
run(os.path.join(my_dir, 'to_run.py'))
