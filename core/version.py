"""Generated application identity and release metadata.

Regenerate this file with ``scripts/generate_version.py`` during a build.
"""

import sys

APP_NAME = 'PLC Universal Simulator'
APP_VERSION = '2.2.5-rc1+2.g370c8be'
APP_RELEASE = 'Development'
APP_GIT_COMMIT = '370c8be'
APP_GIT_BRANCH = 'main'
APP_BUILD_DATE = '2026-07-17 08:54 UTC'
BUILD_TYPE = 'Source development build'


def get_build_type() -> str:
    """Return the effective build type for source or PyInstaller execution."""
    if getattr(sys, "frozen", False):
        return "Packaged desktop build"
    return BUILD_TYPE
