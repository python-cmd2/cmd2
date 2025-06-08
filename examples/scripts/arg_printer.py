#!/usr/bin/env python
from __future__ import annotations

import os
import sys

print(f"Running Python script {os.path.basename(sys.argv[0])!r} which was called with {len(sys.argv) - 1} arguments")
for i, arg in enumerate(sys.argv[1:]):
    print(f"arg {i + 1}: {arg!r}")
