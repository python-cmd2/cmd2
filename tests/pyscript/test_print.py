"""
This script is used to test the py_print() wrapper that cmd2 provides as a replacement
for the built-in print() function in the embedded Python environment.
"""

import sys

from rich.text import Text

# Test multiple objects and sep
print("hello", "world", sep="-")

# Test end
print("no newline", end=" ")
print("here")

# Test multiple objects with custom sep and end
print(1, 2, 3, sep=":", end=".")
print()  # to get a newline

# Test printing a Rich object
text = Text("I am Rich Text", style="blue")
print(text)

# Test file=sys.stdout
print("this goes to sys.stdout", file=sys.stdout)

# Test file=sys.stderr
print("this goes to sys.stderr", file=sys.stderr)
