"""Stable public application identity and release metadata adapter.

Builds provide metadata through the Git-ignored
``core.generated.build_metadata`` module.  Source checkouts without generated
metadata continue to use the committed fallback values below.
"""

import sys

APP_NAME = 'PLC Universal Simulator'
BUILD_TYPE = 'Source development build'

try:
    from core.generated.build_metadata import (
        APP_BUILD_DATE,
        APP_GIT_BRANCH,
        APP_GIT_COMMIT,
        APP_RELEASE,
        APP_VERSION,
    )
except ImportError:
    APP_VERSION = '2.2.5-rc1+2.g370c8be'
    APP_RELEASE = 'Development'
    APP_GIT_COMMIT = '370c8be'
    APP_GIT_BRANCH = 'main'
    APP_BUILD_DATE = '2026-07-17 08:54 UTC'


def get_build_type() -> str:
    """Return the effective build type for source or PyInstaller execution."""
    if getattr(sys, "frozen", False):
        return "Packaged desktop build"
    return BUILD_TYPE
