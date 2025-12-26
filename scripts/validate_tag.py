#!/usr/bin/env python
"""A simple script to validate that a git tag matches a SemVer pattern."""

import re
import subprocess

SEMVER_SIMPLE = re.compile(r'(\d+)\.(\d+)\.(\d+)((a|b|rc)(\d+))?')
SEMVER_PATTERN = re.compile(
    r"""
        ^                                           # Start of the string
        v?                                          # Optional 'v' prefix (common in Git tags)
        (?P<major>0|[1-9]\d*)\.                     # Major version
        (?P<minor>0|[1-9]\d*)\.                     # Minor version
        (?P<patch>0|[1-9]\d*)                       # Patch version
        (?:-(?P<prerelease>                          # Optional pre-release section
            (?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*) #  Identifier
            (?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*
        ))?
        (?:\+(?P<build>                              # Optional build metadata section
            [0-9a-zA-Z-]+                           #  Identifier
            (?:\.[0-9a-zA-Z-]+)*
        ))?
        $                                           # End of the string
    """,
    re.VERBOSE,
)


def get_current_tag() -> str:
    """Get current git tag."""
    try:
        # Gets the name of the latest tag reachable from the current commit
        result = subprocess.run(
            ['git', 'describe', '--exact-match', '--tags', '--abbrev=0'], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("Could not find a reachable tag.")
        return ''


def is_semantic_version(tag_name: str) -> bool:
    """Check if a given string complies with the semantic versioning 2.0.0 specification.

    Args:
        tag_name: The name of the Git tag to validate.

    Returns:
        bool: True if the tag is a valid semantic version, False otherwise.

    """
    # The regex pattern for semantic versioning 2.0.0 (source: https://semver.org/)
    semver_pattern = re.compile(
        r"""
        ^                                           # Start of the string
        v?                                          # Optional 'v' prefix (common in Git tags)
        (?P<major>0|[1-9]\d*)\.                     # Major version
        (?P<minor>0|[1-9]\d*)\.                     # Minor version
        (?P<patch>0|[1-9]\d*)                       # Patch version
        (?:-(?P<prerelease>                          # Optional pre-release section
            (?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*) #  Identifier
            (?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*
        ))?
        (?:\+(?P<build>                              # Optional build metadata section
            [0-9a-zA-Z-]+                           #  Identifier
            (?:\.[0-9a-zA-Z-]+)*
        ))?
        $                                           # End of the string
    """,
        re.VERBOSE,
    )

    return bool(semver_pattern.match(tag_name))


if __name__ == '__main__':
    import sys

    git_tag = get_current_tag()
    if not git_tag:
        print('Git tag does not exist for current commit.')
        sys.exit(-1)

    if not is_semantic_version(git_tag):
        print(rf"Git tag '{git_tag}' is invalid according to SemVer.")
        sys.exit(-1)

    print(rf"Git tag '{git_tag}' is valid.")
