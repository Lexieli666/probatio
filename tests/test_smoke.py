"""Phase 0 smoke tests: the package, the plugin module and the console script all import."""

from __future__ import annotations

import importlib

import probatio


def test_version_string() -> None:
    assert probatio.__version__ == "0.1.0.dev0"


def test_plugin_module_imports_cleanly() -> None:
    plugin = importlib.import_module("probatio.plugin")
    assert callable(plugin.pytest_configure)


def test_cli_module_imports_cleanly() -> None:
    cli = importlib.import_module("probatio.cli")
    assert callable(cli.main)


def test_cli_main_returns_zero_exit_status() -> None:
    from probatio.cli import main

    assert main([]) == 0
