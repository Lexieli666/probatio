"""The provider protocol and the adapters that satisfy it.

Only the protocol and the offline fakes are imported here. The two live adapters are imported
from their own modules on purpose:

- ``probatio.providers.anthropic`` raises :class:`~probatio.errors.ProbatioConfigError` at import
  when the optional ``anthropic`` extra is not installed, which must not happen to a user who
  merely imported ``probatio``.
- ``probatio.providers.claude_cli`` shells out to somebody else's program, so it is asked for by
  name rather than being one attribute lookup away from every suite.

Adding a provider is one class with a ``name`` attribute and a ``complete`` method; it does not
have to subclass anything, and it does not have to live in this package. See ``docs/providers.md``.
"""

from __future__ import annotations

from .base import Completion, Provider
from .fake import DEFAULT_MODEL, FakeCall, FakeProvider, ScriptedProvider

__all__ = [
    "DEFAULT_MODEL",
    "Completion",
    "FakeCall",
    "FakeProvider",
    "Provider",
    "ScriptedProvider",
]
