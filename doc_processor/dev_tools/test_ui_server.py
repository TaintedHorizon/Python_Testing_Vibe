#!/usr/bin/env python3
"""
Simple test server to preview the intake analysis page changes.
This bypasses the import issues in the main app for quick UI testing.
"""

import pytest

# This module provides a tiny flask test server for manual UI checks. It is
# skipped during automated pytest runs to avoid collecting route handler
# return values (which previously caused PytestReturnNotNoneWarning).
pytest.skip("UI test server module - skip during automated test runs", allow_module_level=True)