#!/usr/bin/env python
# coding=utf-8
import os
import sys

print("Running Python script {!r} which was called with {} arguments".format(os.path.basename(sys.argv[0]),
                                                                             len(sys.argv) - 1))
for i, arg in enumerate(sys.argv[1:]):
    print("arg {}: {!r}".format(i + 1, arg))
