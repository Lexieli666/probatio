"""The pytest surface: options, markers, fixtures and the session hooks.

Because this module is loaded by pytest in every session of every project that installs Probatio,
it imports cleanly and does nothing until an option is used or a fixture is requested. What it
owns is spec §3.12's list: the flags, the two markers, the three fixtures, and the four hooks that
push a run state, refuse an unusable configuration, print the report and fail a session that spent
more than its ceiling.

Three positions are fixed here.

**The run state is a stack, not a global.** ``pytester`` nests a whole pytest session inside a
running one, so ``pytest_configure`` pushes and ``pytest_unconfigure`` pops; the inner session
fills its own report and leaves the outer one alone.

**A live provider must be told its model.** ``--probatio-provider claude-cli`` with no
``--probatio-model`` is refused at configure time, because a tape whose model is the literal
string ``claude-cli`` cannot tell two models apart, and a cassette that cannot is worse than none.

**A configuration Probatio refuses is a usage error, not a crash.** Every check below raises
``ProbatioConfigError``, and the two hooks that run them re-raise it as ``pytest.UsageError`` with
the original as its cause: pytest prints a usage error as one sentence and exits 4, where an
uncaught exception in ``pytest_configure`` prints ``INTERNALERROR`` and a traceback of Probatio's
own frames. The message text is the same either way (DECISIONS 67, 69).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final

import pytest

from .budget import PriceTable, SuiteBudget
from .cassette import (
    CASSETTE_MODES,
    CassetteMode,
    CassetteProvider,
    CassetteStore,
    record_command,
)
from .collector import RunReport, RunState, pop_state, push_state
from .errors import ProbatioConfigError
from .metamorphic import RELATION_MARKER, Relation
from .providers import Provider
from .reporters import (
    SECTION_TITLE,
    render_terminal,
    write_junit,
    write_markdown,
    write_results,
)
from .session import Probatio, ProbatioSettings
from .stability import FLAKY_MARKER, read_flaky_tolerance

__all__ = [
    "FLAKY_MARKER",
    "PROVIDER_CHOICES",
    "RELATION_MARKER",
    "RUNS_DEST",
    "Probatio",
    "as_usage_error",
    "pytest_addoption",
    "pytest_configure",
    "pytest_sessionfinish",
    "pytest_terminal_summary",
    "pytest_unconfigure",
    "write_artefacts",
]

PROVIDER_CHOICES: Final = ("fake", "anthropic", "claude-cli")
"""The adapters ``--probatio-provider`` accepts; spec §3.12's list, and only Anthropic is live."""

RUNS_DEST: Final = "probatio_runs"
"""The destination ``--runs`` stores under, so the fallback flag name reads the same value."""

DEFAULT_CASSETTE_DIR: Final = "cassettes"
"""Spec §3.12's default for ``--cassette-dir``, relative to rootdir."""

DEFAULT_BASELINE_DIR: Final = ".probatio/baseline"
"""Spec §3.12's default for ``--baseline-dir``, relative to rootdir."""

_MODEL_REQUIRED: Final = (
    "--probatio-provider {name} needs --probatio-model: without one every cassette this run "
    "records is keyed on the literal string {name!r} instead of a model, so a tape recorded "
    "against one model would replay silently against another"
)
"""Requirement 5's message, shared by the system under test and the judge."""

_runs_flag = "--runs"
"""Which flag name ``--runs`` was actually registered under; see :func:`_add_runs_option`."""


@contextmanager
def as_usage_error() -> Iterator[None]:
    """Re-raise a configuration error as the usage error pytest knows how to print.

    ``pytest_addoption`` and ``pytest_configure`` run before any test does, and an exception
    escaping either of them is reported as ``INTERNALERROR`` with a traceback through Probatio's
    own frames — which reads as a bug in the plugin rather than as a flag the user got wrong.
    ``pytest.UsageError`` is the same non-zero exit with one sentence instead.

    Yields:
        Nothing; this wraps a block.

    Raises:
        pytest.UsageError: The block raised :class:`~probatio.errors.ProbatioConfigError`. Its
            message is carried through unchanged and the original is kept as ``__cause__``, so a
            test may assert on either.
    """
    try:
        yield
    except ProbatioConfigError as exc:
        raise pytest.UsageError(str(exc)) from exc


# -- options -------------------------------------------------------------------------------


def _add_runs_option(group: Any) -> str:
    """Register ``--runs``, falling back to ``--probatio-runs`` when it is already taken.

    Args:
        group: The ``probatio`` option group.

    Returns:
        The flag name that was registered, so messages and help name the one that works.
    """
    help_text = "run each case N times and report a pass rate with a Wilson interval (default 1)"
    for flag in ("--runs", "--probatio-runs"):
        try:
            group.addoption(flag, dest=RUNS_DEST, type=int, default=1, metavar="N", help=help_text)
        except ValueError:
            continue
        return flag
    raise ProbatioConfigError(
        "neither --runs nor --probatio-runs could be registered; another plugin has taken both"
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register every Probatio flag in a ``probatio`` option group.

    Args:
        parser: pytest's option parser.
    """
    global _runs_flag
    group = parser.getgroup("probatio", "probatio: regression testing for LLM applications")
    group.addoption(
        "--probatio-provider",
        default="fake",
        choices=PROVIDER_CHOICES,
        help="provider the 'provider' fixture builds (default: fake)",
    )
    group.addoption("--probatio-model", metavar="NAME", help="model the provider is asked for")
    group.addoption(
        "--probatio-judge-provider",
        default=None,
        choices=PROVIDER_CHOICES,
        help="provider judge assertions grade through (default: same as --probatio-provider)",
    )
    group.addoption(
        "--probatio-judge-model", metavar="NAME", help="model the judge provider is asked for"
    )
    group.addoption(
        "--probatio-prices",
        metavar="PATH",
        help="YAML price table making cost ceilings enforceable",
    )
    group.addoption(
        "--cassette",
        default="replay",
        choices=CASSETTE_MODES,
        help="replay committed tapes, record new ones, or call the provider (default: replay)",
    )
    group.addoption(
        "--cassette-dir",
        default=DEFAULT_CASSETTE_DIR,
        metavar="PATH",
        help=f"where tapes live, relative to rootdir (default: {DEFAULT_CASSETTE_DIR})",
    )
    with as_usage_error():
        _runs_flag = _add_runs_option(group)
    group.addoption(
        "--update-baseline",
        action="store_true",
        help="overwrite every snapshot baseline this run compares against",
    )
    group.addoption(
        "--baseline-dir",
        default=DEFAULT_BASELINE_DIR,
        metavar="PATH",
        help=f"where baselines live, relative to rootdir (default: {DEFAULT_BASELINE_DIR})",
    )
    group.addoption(
        "--max-cost", type=float, metavar="USD", help="fail the session if it spends more than this"
    )
    group.addoption(
        "--max-latency",
        type=float,
        metavar="MS",
        help="default per-case latency ceiling for cases that declare none",
    )
    group.addoption(
        "--probatio-report", metavar="PATH", help="write the markdown report to this file"
    )
    group.addoption("--probatio-junit", metavar="PATH", help="write JUnit XML to this file")
    group.addoption(
        "--probatio-results",
        metavar="PATH",
        help="write the full run report to this file as JSON",
    )


# -- configuration ---------------------------------------------------------------------------


def _resolve_path(config: pytest.Config, value: str) -> Path:
    """Resolve an option's path against rootdir, as spec §0 says every relative path resolves."""
    path = Path(value)
    return path if path.is_absolute() else Path(config.rootpath) / path


def check_model_is_named(config: pytest.Config) -> None:
    """Refuse a live provider that was not told which model to use.

    Args:
        config: The session's configuration.

    Raises:
        ProbatioConfigError: A non-fake provider was chosen with no model for it.
    """
    provider = str(config.getoption("--probatio-provider"))
    model = config.getoption("--probatio-model")
    if provider != "fake" and not model:
        raise ProbatioConfigError(_MODEL_REQUIRED.format(name=provider))
    judge = config.getoption("--probatio-judge-provider") or provider
    if judge != "fake" and not (config.getoption("--probatio-judge-model") or model):
        raise ProbatioConfigError(_MODEL_REQUIRED.format(name=judge))


def build_settings(config: pytest.Config) -> ProbatioSettings:
    """Resolve every option ``check`` needs into one frozen object.

    Args:
        config: The session's configuration.

    Returns:
        The settings.

    Raises:
        ProbatioConfigError: ``--probatio-prices`` names a file that cannot be loaded.
    """
    prices_option = config.getoption("--probatio-prices")
    prices = PriceTable.load(_resolve_path(config, str(prices_option))) if prices_option else None
    return ProbatioSettings(
        rootdir=Path(config.rootpath),
        runs=int(config.getoption(RUNS_DEST)),
        cassette_mode=_cassette_mode(config),
        update_baseline=bool(config.getoption("--update-baseline")),
        baseline_dir=_resolve_path(config, str(config.getoption("--baseline-dir"))),
        prices=prices,
        max_latency_ms=_optional_float(config.getoption("--max-latency")),
        provider_name=str(config.getoption("--probatio-provider")),
    )


def _cassette_mode(config: pytest.Config) -> CassetteMode:
    """Read ``--cassette`` back as the literal type the store expects."""
    mode = str(config.getoption("--cassette"))
    if mode not in CASSETTE_MODES:  # pragma: no cover - argparse restricts the choices
        raise ProbatioConfigError(f"{mode!r} is not a cassette mode; choose {CASSETTE_MODES}")
    return mode


def _optional_float(value: Any) -> float | None:
    """Read an optional numeric option, keeping ``None`` as "not given"."""
    return None if value is None else float(value)


def pytest_configure(config: pytest.Config) -> None:
    """Register the markers, refuse an unusable configuration and push this session's state.

    Args:
        config: The session's configuration.

    Raises:
        pytest.UsageError: An option is unusable; see :func:`check_model_is_named` and
            :func:`build_settings`. The offending :class:`~probatio.errors.ProbatioConfigError`
            is its cause and its message is unchanged.
    """
    config.addinivalue_line("markers", RELATION_MARKER_HELP)
    config.addinivalue_line("markers", FLAKY_MARKER_HELP)
    with as_usage_error():
        check_model_is_named(config)
        settings = build_settings(config)
    store = CassetteStore(
        _resolve_path(config, str(config.getoption("--cassette-dir"))),
        root=Path(config.rootpath),
    )
    model = config.getoption("--probatio-model")
    store.record_command = record_command(settings.provider_name, str(model) if model else None)
    state = RunState(
        runs=settings.runs,
        store=store,
        budget=SuiteBudget(_optional_float(config.getoption("--max-cost"))),
    )
    config.stash[_SETTINGS] = settings
    config.stash[_STATE] = state
    push_state(state)


def pytest_unconfigure(config: pytest.Config) -> None:
    """Pop this session's state, so a nested ``pytester`` run cannot clobber its parent's.

    Args:
        config: The session's configuration.
    """
    if _STATE in config.stash:
        pop_state()


RELATION_MARKER_HELP = (
    f"{RELATION_MARKER}(relation): a probatio metamorphic relation to evaluate on every case "
    "this test runs. Applied by the order_invariant, distractor_robust, format_jitter and "
    "paraphrase_invariant decorators; violation rates are reported alongside the case and never "
    "change its verdict."
)
"""The one-line description ``pytest --markers`` prints for the relation marker."""

FLAKY_MARKER_HELP = (
    f"{FLAKY_MARKER}(p, n): run this test's case n times and pass it when the pass rate reaches "
    "p. Applied by the flaky_tolerant decorator; n overrides --runs for this test."
)
"""The one-line description ``pytest --markers`` prints for the tolerance marker."""

_SETTINGS: Final[pytest.StashKey[ProbatioSettings]] = pytest.StashKey()
"""Where the resolved settings live, so a fixture reads the ones its own session built."""

_STATE: Final[pytest.StashKey[RunState]] = pytest.StashKey()
"""Where the session's run state lives, alongside its place on the stack."""


# -- fixtures ---------------------------------------------------------------------------------


def _session(config: pytest.Config) -> tuple[ProbatioSettings, RunState]:
    """Return this session's settings and state.

    Raises:
        ProbatioConfigError: The session was never configured, which means the plugin is not
            installed in the interpreter running the test.
    """
    if _SETTINGS not in config.stash or _STATE not in config.stash:
        raise ProbatioConfigError(
            "probatio was not configured for this session; is the plugin installed?"
        )
    return config.stash[_SETTINGS], config.stash[_STATE]


class _ObservingProvider:
    """A provider that reports every completion to the run state before returning it.

    This is how a budget ceiling sees the calls a system under test made: the ``provider`` fixture
    hands out this wrapper, and ``check`` collects whatever it reported while the system under
    test was running. A suite that builds its own provider is measured from what its system under
    test returns instead, which is why returning a ``Completion`` is worth doing.

    Attributes:
        name: The wrapped provider's name, so a tape records the adapter and not the wrapper.
        inner: The provider being watched, which is what ``name`` and ``model`` come from.
        state: The run state the completions are reported to.
    """

    def __init__(self, inner: Provider, state: RunState) -> None:
        """Wrap a provider.

        Args:
            inner: The provider to watch.
            state: The run state to report to.
        """
        self.name = inner.name
        self.inner = inner
        self.state = state

    @property
    def model(self) -> str | None:
        """The wrapped provider's model, which the cassette key falls back to (DECISIONS 43)."""
        model: str | None = getattr(self.inner, "model", None)
        return model

    def judge_calls(self, template_hash: str) -> Any:
        """Forward the judge's marker to the wrapped provider when it offers one.

        Args:
            template_hash: The judge prompt template's hash.

        Returns:
            The wrapped provider's context manager.

        Raises:
            AttributeError: The wrapped provider is not cassette-wrapped, which is what
                :class:`~probatio.judge.Judge` tests for before calling this.
        """
        marker: Any = getattr(self.inner, "judge_calls")  # noqa: B009
        return marker(template_hash)

    def complete(self, prompt: str, *, system: str | None = None, **params: Any) -> Any:
        """Complete a prompt through the wrapped provider and report the call.

        Args:
            prompt: The user-turn text.
            system: The system prompt.
            **params: The case's parameters.

        Returns:
            The wrapped provider's completion, unchanged.
        """
        completion = self.inner.complete(prompt, system=system, **params)
        self.state.observe(completion)
        return completion


def _build_provider(config: pytest.Config, *, judge: bool) -> Provider:
    """Build one configured adapter, cassette-wrapped and instrumented."""
    from .cli import build_provider

    settings, state = _session(config)
    name = str(config.getoption("--probatio-provider"))
    model = config.getoption("--probatio-model")
    if judge:
        name = str(config.getoption("--probatio-judge-provider") or name)
        model = config.getoption("--probatio-judge-model") or model
    inner = build_provider(name, str(model) if model else None)
    taped = CassetteProvider(inner, state.store, settings.cassette_mode)
    return _ObservingProvider(taped, state)


@pytest.fixture
def provider(request: pytest.FixtureRequest) -> Provider:
    """Return the configured provider, wrapped for cassettes and for budget accounting.

    Args:
        request: The requesting test.

    Returns:
        A :class:`~probatio.providers.Provider`. The system under test cannot tell it from a bare
        adapter; a suite that wants its own may override this fixture and take it as an argument.
    """
    return _build_provider(request.config, judge=False)


@pytest.fixture
def judge_provider(request: pytest.FixtureRequest) -> Provider:
    """Return the provider ``judge`` assertions grade through.

    Args:
        request: The requesting test.

    Returns:
        The same adapter as :func:`provider` unless ``--probatio-judge-provider`` or
        ``--probatio-judge-model`` names a different one.
    """
    return _build_provider(request.config, judge=True)


def _relations(node: pytest.Item) -> list[Relation]:
    """Read the relation instances off a test's markers, outermost decorator first."""
    found: list[Relation] = []
    for mark in node.iter_markers(RELATION_MARKER):
        if not mark.args or not isinstance(mark.args[0], Relation):
            raise ProbatioConfigError(
                f"@pytest.mark.{RELATION_MARKER} takes one Relation instance; apply it with the "
                "order_invariant, distractor_robust, format_jitter or paraphrase_invariant "
                "decorator rather than by hand"
            )
        found.append(mark.args[0])
    return list(reversed(found))


def _rubric_dirs(request: pytest.FixtureRequest, settings: ProbatioSettings) -> list[Path]:
    """Return rootdir's ``rubrics/`` first, then the requesting module's own (DECISIONS 23)."""
    module_dir = Path(str(request.node.path)).parent
    dirs = [settings.rootdir / "rubrics", module_dir / "rubrics"]
    return list(dict.fromkeys(dirs))


@pytest.fixture
def probatio(request: pytest.FixtureRequest, judge_provider: Provider) -> Probatio:
    """Build the object a test calls ``check`` on.

    Args:
        request: The requesting test, whose markers say which relations to evaluate and how many
            runs the case gets.
        judge_provider: The provider ``judge`` assertions grade through.

    Returns:
        A :class:`~probatio.session.Probatio` configured for this test.
    """
    settings, state = _session(request.config)
    return Probatio(
        settings=settings,
        state=state,
        suite=Path(str(request.node.path)).stem,
        node_id=request.node.nodeid,
        judge_provider=judge_provider,
        relations=_relations(request.node),
        tolerance=read_flaky_tolerance(request.node.iter_markers(FLAKY_MARKER)),
        rubric_dirs=_rubric_dirs(request, settings),
    )


# -- the end of the session ---------------------------------------------------------------------


def _option_path(config: pytest.Config, flag: str) -> Path | None:
    """Return the rootdir-resolved path an option names, or ``None`` when it was not given."""
    value = config.getoption(flag)
    return _resolve_path(config, str(value)) if value else None


def write_artefacts(report: RunReport, config: pytest.Config) -> list[Path]:
    """Write every file this session's flags asked for.

    The markdown reporter also writes itself into ``$GITHUB_STEP_SUMMARY`` when the environment
    sets one; the other two are written only where a flag names a file. A file that was asked for
    is written even when the session checked no case at all, because a pipeline told to collect
    it has to find it — an empty ``<testsuite tests="0">`` and a report with no cases both say
    "nothing ran", and a missing file says nothing.

    Args:
        report: The finished run.
        config: The session's configuration.

    Returns:
        The paths written, in the order they were written.
    """
    written = list(write_markdown(report, path=_option_path(config, "--probatio-report")))
    junit = _option_path(config, "--probatio-junit")
    if junit is not None:
        written.append(write_junit(report, junit))
    results = _option_path(config, "--probatio-results")
    if results is not None:
        written.append(write_results(report, results))
    return written


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: pytest.Config) -> None:
    """Print the ``probatio`` section, and write every report file the flags asked for.

    Args:
        terminalreporter: pytest's reporter.
        exitstatus: The session's exit status so far, unused here.
        config: The session's configuration.
    """
    if _STATE not in config.stash:
        return
    report = config.stash[_STATE].report()
    lines = render_terminal(report)
    if lines:
        terminalreporter.write_sep("=", SECTION_TITLE)
        for line in lines:
            terminalreporter.write_line(line)
    for written in write_artefacts(report, config):
        terminalreporter.write_line(f"{SECTION_TITLE}: wrote {written}")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail the session when it spent more than ``--max-cost``.

    Args:
        session: The finished session.
        exitstatus: The status so far; replaced with ``TESTS_FAILED`` on an overrun.
    """
    config = session.config
    if _STATE not in config.stash:
        return
    message = config.stash[_STATE].budget.overrun_message()
    if message is not None:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        print(f"probatio: {message}")
