"""Generated application identity and release metadata.

Regenerate this file with ``scripts/generate_version.py`` during a build.
"""

import sys

APP_NAME = 'PLC Universal Simulator'
APP_VERSION = '2.2.4'
APP_RELEASE = 'Stable'
APP_GIT_COMMIT = '1a017c2'
APP_GIT_BRANCH = 'main'
APP_BUILD_DATE = '2026-07-13 12:06 UTC'
BUILD_TYPE = 'Source development build'


def get_build_type() -> str:
    """Return the effective build type for source or PyInstaller execution."""
    if getattr(sys, "frozen", False):
        return "Packaged desktop build"
    return BUILD_TYPE
