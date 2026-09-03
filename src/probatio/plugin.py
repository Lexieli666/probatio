"""The pytest plugin entry point, registered as the ``pytest11`` plugin ``probatio``.

Because this module is loaded by pytest in every session of every project that installs Probatio,
it must import cleanly, quickly and without side effects. Options, markers, fixtures and the
session hooks are added by the later phases; until then this module exists so that the declared
entry point resolves and an installed Probatio is a no-op for the host suite.
"""

__all__: list[str] = []
