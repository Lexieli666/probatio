"""Repository-level pytest configuration.

The only thing here is the other half of the demo suite's import guard, and it is temporary.

``examples/demo_suite/conftest.py`` (frozen since Phase 1, gate condition 5) sets
``collect_ignore = ["test_demo.py"]`` when ``from probatio import FakeProvider`` raises. That
probe stops working the moment Phase 2 exports ``FakeProvider``, which spec §3.3 and §6 both
require: from Phase 2 to Phase 8 the guard no longer fires, and ``test_demo.py`` fails to import
on the relation decorators that are still to come, which is a collection error in the repository's
own ``pytest -q``.

The frozen file cannot be edited to strengthen its probe, so the exclusion is repeated here, where
it can be. Phase 9 deletes this file in the same commit that deletes the guard in the frozen
``conftest.py``; ``tests/test_demo_spec.py`` fails if this line outlives the missing exports.
See ``DECISIONS.md`` entry 16.
"""

from __future__ import annotations

collect_ignore = ["examples/demo_suite/test_demo.py"]
