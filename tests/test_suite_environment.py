"""Guards that the suite renders output independently of the developer's environment.

Rich and cmd2 both consult environment variables when deciding whether to emit styling.
Inheriting them makes large numbers of unrelated tests fail depending on who runs them,
which is expensive to diagnose because the failures look like product regressions.
"""

import os

import pytest

#: Variables that change how output is rendered. Rich reads all of these; cmd2 reads
#: NO_COLOR directly. Tests that exercise them set them explicitly instead.
COLOR_ENVIRONMENT = ("NO_COLOR", "FORCE_COLOR", "TTY_COMPATIBLE", "TTY_INTERACTIVE")


@pytest.mark.parametrize("name", COLOR_ENVIRONMENT)
def test_color_environment_does_not_leak_into_tests(name: str) -> None:
    """A developer exporting any of these must not change the suite's results."""
    assert name not in os.environ, (
        f"{name} leaked into the test environment; output-rendering assertions would depend on who is running the suite"
    )
