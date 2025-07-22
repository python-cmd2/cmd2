# This script demonstrates that cmd2 can capture sys.stdout and self.stdout when both point to the same stream.
# Set base_app.self_in_py to True before running this script.
print("print")
self.poutput("poutput")
