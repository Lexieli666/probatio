"""Shared test configuration: enable pytest's own ``pytester`` fixture for plugin-level tests."""

from __future__ import annotations

pytest_plugins = ["pytester"]
