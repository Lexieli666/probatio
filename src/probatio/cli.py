"""The ``probatio`` console script.

The subcommands (``validate-judge``, ``freeze-variants``, ``import-cassettes``) are added by the
phases that implement them. This module exists so that the console script declared in
``pyproject.toml`` resolves to a callable that returns a process exit status.
"""

__all__ = ["main"]


def main() -> int:
    """Run the ``probatio`` command-line interface and return a process exit status.

    Returns:
        ``0``. No subcommand is implemented yet, so there is nothing to fail.
    """
    return 0
