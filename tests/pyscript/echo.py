# Tests echo argument to app()
from __future__ import annotations

app.cmd_echo = False

# echo defaults to current setting which is False, so this help text should not be echoed to pytest's stdout
app('help alias')

# pytest's stdout should have this help text written to it
app('help edit', echo=True)
