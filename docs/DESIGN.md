# docs/DESIGN.md — rationale for non-obvious choices

One paragraph per choice, each naming the alternative it rejects. Ordered by the phase that made
the choice.

## Phase 0

**The version lives in `src/probatio/__init__.py`, not in `pyproject.toml`.** `pyproject.toml`
declares `dynamic = ["version"]` and points hatchling at the module attribute, so
`probatio.__version__` and the distribution metadata cannot drift apart. The rejected alternative
is a literal `version = "0.1.0.dev0"` in `pyproject.toml` plus a duplicate constant in the package,
which is the arrangement that produces a release whose installed metadata disagrees with what the
package reports at runtime. The smoke test asserts the constant, so a bump that forgets the module
fails the gate rather than shipping.

**The plugin module is loaded by every host suite, so it stays inert until it has work to do.**
Declaring the `pytest11` entry point in Phase 0 means `probatio.plugin` is imported by pytest in
every project that installs Probatio, including projects that never write an `LLMCase`. The module
therefore carries no imports beyond the standard library, registers no options and has no
import-time side effects; later phases add hooks that guard on the plugin's own flags. The rejected
alternative is deferring the entry point until Phase 9, when the hooks exist, which would leave the
declared console script and the declared plugin out of step with the packaging metadata for nine
phases and hide entry-point resolution bugs until late.

**Coverage is measured on `src/probatio` by path, not on the installed package.** The
`[tool.coverage.run]` section sets `source = ["src/probatio"]`, so a module that no test imports
is reported at 0% and drags the number down, instead of being silently absent from the report.
The rejected alternative, `source = ["probatio"]`, resolves through the editable install and
measures only what was imported, which reports a suite that never touches a module as fully
covered.
