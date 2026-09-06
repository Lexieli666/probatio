"""``cassette.py``: record once, replay for nothing, and say so when the tape no longer fits.

A cassette is what makes an LLM suite runnable in CI. The recording is a deliberate act by a human
with a model behind them (`CLAUDE.md`: ``pytest --cassette=record --probatio-provider claude-cli``);
every run after that reads the tape, calls nobody, costs nothing and produces the same answers on
every machine. :class:`CassetteProvider` wraps the configured adapter and satisfies the same
:class:`~probatio.providers.Provider` protocol, so the system under test and the judge cannot tell
which side of the tape they are on.

Four positions hold this module together.

**A tape holds a list of samples, not one answer.** Spec §3.8's ``interactions[].completions`` is
a list because Probatio's headline feature is a pass rate: recording under ``--runs 5`` appends
five samples and replay hands back ``completions[run_index % len(completions)]``, so the same
nondeterminism the recording saw is reproduced at zero cost. A tape with one sample replayed under
several runs can only report a pass rate of 0 or 1, which is a true statement about a one-sample
measurement and a misleading one to print without a caveat, so the store records a note
(:data:`SINGLE_SAMPLE_NOTE`) that Phase 9's reporter surfaces — for the system under test only,
since a judge's prompt carries the answer it grades and so keys one interaction per run by
construction (DECISIONS 106).

**A miss is never a call.** Replay never touches ``inner``. A key the tape does not carry is
:class:`~probatio.errors.StaleCassetteError` and a case with no file is
:class:`~probatio.errors.MissingCassetteError`; both name the case and the command that re-records
it. Falling through to the live provider would turn one edited prompt in a pull request into a
silent bill and a CI run that needs an API key.

**The judge marks its calls through the store, not through the parameters.** Spec §3.5 puts the
judge prompt template's hash in the key, so that a tape recorded under one wrapper does not replay
under another. That hash cannot travel as a parameter of ``complete``: the protocol has no field
for it, and a reserved keyword would reach a live adapter, which would either forward it to a model
API or reject the call. Instead the store owns the active context — the case, the run index, and
whether a judge is speaking — and :class:`CassetteProvider` exposes :meth:`~CassetteProvider.
judge_calls` for :class:`~probatio.judge.Judge` to enter when the provider it was handed offers it
(DECISIONS 42). An adapter that is not cassette-wrapped has no such method and receives exactly
the arguments its caller passed.

**Bytes are stable.** Files are written with sorted keys, an indent and a trailing newline, and
the only non-content field, ``recorded``, comes from an injectable clock
(:mod:`probatio.artefacts`). Two recordings of the same calls with the same clock are byte-
identical, because these files are committed to the user's repository and a re-record that did not
change anything must not produce a diff.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .artefacts import Clock, check_path_segment, display_path, timestamp, utc_now, write_json
from .errors import MissingCassetteError, ProbatioConfigError, StaleCassetteError
from .hashing import stable_hash
from .providers import Completion, Provider

__all__ = [
    "CASSETTE_MODES",
    "IMPORT_PROVIDER",
    "RECORD_COMMAND",
    "record_command",
    "SINGLE_SAMPLE_NOTE",
    "ActiveCase",
    "Cassette",
    "CassetteMode",
    "CassetteProvider",
    "CassetteStore",
    "ImportedCall",
    "Interaction",
    "default_cassette_dir",
    "import_cassettes",
    "interaction_key",
    "parse_trace_line",
    "read_trace",
    "resolve_model",
]

CassetteMode = Literal["replay", "record", "off"]
"""What a :class:`CassetteProvider` does with a call; spec §3.8's three modes."""

CASSETTE_MODES: Final[tuple[CassetteMode, ...]] = ("replay", "record", "off")
"""The modes in the order the ``--cassette`` flag lists them; ``replay`` is the default."""

RECORD_COMMAND: Final = "pytest --cassette=record"
"""What every missing or stale tape tells the reader to run, with the provider of their choice."""


def record_command(provider: str | None = None, model: str | None = None) -> str:
    """Compose the command that records a missing tape, naming the provider that would answer.

    Args:
        provider: The configured provider's name, or ``None`` to leave the flag out. ``fake`` is
            left out too: a tape recorded from a fake is not what a reader is being told to make.
        model: The configured model, named alongside a live provider because Phase 9's plugin
            refuses a live provider that has none.

    Returns:
        A runnable command line.
    """
    if not provider or provider == "fake":
        return RECORD_COMMAND
    command = f"{RECORD_COMMAND} --probatio-provider {provider}"
    return f"{command} --probatio-model {model}" if model else command


SINGLE_SAMPLE_NOTE: Final = "1 recorded sample"
"""The phrase spec §3.8 asks a report to carry when a tape is replayed for more runs than it has."""

IMPORT_PROVIDER: Final = "imported"
"""The ``provider`` field of a tape built by ``probatio import-cassettes`` from a trace."""


def default_cassette_dir() -> Path:
    """Return the directory cassettes are read from and written to by default.

    Returns:
        ``Path.cwd() / "cassettes"``, which is spec §5's location relative to rootdir. Phase 9's
        plugin passes a rootdir-based path, or ``--cassette-dir``, explicitly.
    """
    return Path.cwd() / "cassettes"


def resolve_model(params: Mapping[str, Any], fallback: str | None = None) -> str | None:
    """Return the model a call will actually be answered by.

    This is the precedence both shipped live adapters already implement — each computes
    ``params.pop("model") or self.model`` — restated here so that a cassette key can be worked
    out *before* the call, which is what replay has to do (DECISIONS 43, amended).

    Args:
        params: The call's parameters.
        fallback: The model the adapter would use when the call names none, which for a live
            adapter is whatever ``--probatio-model`` put in its constructor.

    Returns:
        ``params["model"]`` when the call names one, otherwise ``fallback``, as a string; or
        ``None`` when neither says.
    """
    resolved = params.get("model")
    if resolved is None:
        resolved = fallback
    return None if resolved is None else str(resolved)


def interaction_key(
    *,
    prompt: str,
    system: str | None,
    params: Mapping[str, Any],
    model: str | None = None,
    template: str | None = None,
) -> str:
    """Return the key that identifies one call on a tape.

    Spec §3.8 names five parts. ``model`` is lifted out of ``params`` rather than counted twice,
    so the key has one field per thing that can change and a tape recorded on one model reports
    itself stale on another (DECISIONS 43).

    Args:
        prompt: The user-turn text.
        system: The system prompt, or ``None``.
        params: The call's parameters. A ``model`` entry becomes the key's ``model`` field; every
            other entry is hashed under ``params``.
        model: The model the answering adapter would use when ``params`` names none. Most cases
            name no model — none of the demo suite's ten do — so without this the key's ``model``
            would be blank for all of them and a tape recorded against one model would replay
            silently against another.
        template: The judge prompt template's hash when a judge made the call, otherwise
            ``None``, so that a judge call and a system-under-test call carrying the same text are
            different interactions.

    Returns:
        The :func:`~probatio.hashing.stable_hash` of those five parts.
    """
    rest = dict(params)
    rest.pop("model", None)
    return stable_hash(
        {
            "prompt": prompt,
            "system": system,
            "model": resolve_model(params, model),
            "params": rest,
            "template": template,
        }
    )


class Interaction(BaseModel):
    """One distinct call, and every sample recorded for it.

    Attributes:
        key: :func:`interaction_key` of the call this replays.
        prompt: The user-turn text, kept verbatim so a human can read the tape.
        system: The system prompt, or ``None``.
        params: The call's parameters, exactly as the caller passed them.
        model: The model the key was computed from — the call's own, or the adapter's when the
            call named none. Recorded so a human reading a stale tape can see which model it
            belongs to; replay is decided by the key, never by this field.
        completions: One entry per recorded run, in the order they were recorded.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    prompt: str
    system: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    model: str | None = None
    completions: list[Completion] = Field(default_factory=list)

    def sample(self, run_index: int) -> Completion:
        """Return the sample a given run replays.

        Args:
            run_index: The zero-based run number, which ``--runs N`` counts from 0 to ``N - 1``.

        Returns:
            ``completions[run_index % len(completions)]``, so a tape shorter than the run count
            cycles rather than running out.

        Raises:
            ValueError: The interaction holds no samples, which a written tape never does.
        """
        if not self.completions:
            raise ValueError(f"interaction {self.key} holds no recorded completion")
        return self.completions[run_index % len(self.completions)]


class Cassette(BaseModel):
    """One case's tape, exactly as spec §3.8 lays it out on disk.

    Attributes:
        case_id: The case this tape belongs to; also the file's stem.
        recorded: When it was written, as an ISO 8601 instant in UTC.
        provider: The ``name`` of the adapter that produced the samples.
        model: The model of the first sample recorded, for the reader's benefit; the model that
            decides replay is the one inside each interaction's key.
        interactions: The distinct calls, in the order they were first recorded.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    recorded: str
    provider: str
    model: str
    interactions: list[Interaction] = Field(default_factory=list)

    def find(self, key: str) -> Interaction | None:
        """Return the interaction with a given key, if the tape carries one.

        Args:
            key: The key to look for.

        Returns:
            The interaction, or ``None``.
        """
        return next((item for item in self.interactions if item.key == key), None)


class ActiveCase(BaseModel):
    """Which case a store's calls currently belong to, and which run of it is going on.

    Attributes:
        suite: The suite name, which is the test module's stem (spec §3.6).
        case_id: The case's id.
        run_index: The zero-based run number under ``--runs N``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    suite: str
    case_id: str
    run_index: int = 0


class CassetteStore:
    """The tapes under one directory, plus the active context every call is attributed to.

    The store, not the provider, owns the context: Phase 9's ``probatio`` fixture calls
    :meth:`begin_case` before the system under test runs, and the judge enters
    :meth:`judge_calls` around its own call. That is what lets :class:`CassetteProvider` stay a
    four-line pass-through with no arguments beyond the ones the protocol declares.

    Attributes:
        cassette_dir: The root the tapes live under.
        clock: The clock a recording's ``recorded`` field is read from.
        notes: Observations a reporter should surface, in the order they were first made.
        record_command: The command a missing or stale tape tells the reader to run.
    """

    def __init__(
        self,
        cassette_dir: Path | None = None,
        *,
        clock: Clock = utc_now,
        root: Path | None = None,
    ) -> None:
        """Open a store over a directory.

        Args:
            cassette_dir: Where tapes live. Defaults to :func:`default_cassette_dir`.
            clock: A callable returning the instant written into a tape's ``recorded`` field.
                Defaults to the current UTC time; tests inject a fixed one, so nothing in this
                repository's suite depends on the wall clock.
            root: What the paths in this store's messages are rendered relative to. A missing or
                stale tape's message reaches the report's warnings and the case's failure text
                (DECISIONS 72), both of which are persisted, so it names a path in the repository
                rather than one on the machine. Defaults to the current directory; Phase 9's
                plugin passes rootdir.

        The store also carries a :attr:`record_command`, the fix clause every missing-tape and
        stale-tape error names. Phase 9's plugin replaces it with one naming the configured
        provider and model, because ``pytest --cassette=record`` alone would re-record a tape
        from whatever provider happened to be the default.
        """
        self.cassette_dir = cassette_dir if cassette_dir is not None else default_cassette_dir()
        self.clock = clock
        self.root = root if root is not None else Path.cwd()
        self.record_command = RECORD_COMMAND
        self.notes: list[str] = []
        self._active: ActiveCase | None = None
        self._template: str | None = None
        self._cache: dict[tuple[str, str], Cassette] = {}
        self._recorded: set[tuple[str, str, str]] = set()

    def display(self, path: Path) -> str:
        """Render a path for a message that will be persisted.

        Args:
            path: The path to render.

        Returns:
            It relative to :attr:`root`, with POSIX separators
            (:func:`~probatio.artefacts.display_path`).
        """
        return display_path(path, self.root)

    # -- the active context ------------------------------------------------------------------

    @property
    def active(self) -> ActiveCase | None:
        """The case calls are currently attributed to, or ``None`` outside a case."""
        return self._active

    @property
    def template(self) -> str | None:
        """The judge template hash entering the key, or ``None`` outside :meth:`judge_calls`."""
        return self._template

    def begin_case(self, suite: str, case_id: str, run_index: int = 0) -> ActiveCase:
        """Attribute every following call to one run of one case.

        Args:
            suite: The suite name, which is the test module's stem.
            case_id: The case's id.
            run_index: The zero-based run number; ``--runs N`` calls this N times.

        Returns:
            The context that was set.

        Raises:
            ProbatioConfigError: Either name would escape the cassette directory, or the run
                index is negative.
        """
        self.path_for(suite, case_id)
        if run_index < 0:
            raise ProbatioConfigError(
                f"run index {run_index} is not a run of case {case_id!r}; runs count from 0",
                case_id=case_id,
            )
        self._active = ActiveCase(suite=suite, case_id=case_id, run_index=run_index)
        return self._active

    def end_case(self) -> None:
        """Forget the active case, so a call made outside one is reported rather than misfiled."""
        self._active = None

    def require_active(self) -> ActiveCase:
        """Return the active case, or explain that nobody set one.

        Returns:
            The active case.

        Raises:
            ProbatioConfigError: No case is active, so the call belongs to no tape.
        """
        if self._active is None:
            raise ProbatioConfigError(
                "a cassette call was made outside a case: call CassetteStore.begin_case before "
                "the system under test runs, which the 'probatio' fixture does for you"
            )
        return self._active

    @contextmanager
    def judge_calls(self, template_hash: str) -> Iterator[None]:
        """Mark every call made inside the block as a judge call.

        The judge prompt template's hash enters the interaction key for the duration, so a judge
        call and a system-under-test call whose prompt text happens to be identical are two
        interactions, and a tape recorded under one template reports itself stale under another
        (spec §3.5, §3.8).

        Args:
            template_hash: :func:`~probatio.judge.judge_template_hash`.

        Yields:
            Nothing; the mark is the effect.
        """
        previous = self._template
        self._template = template_hash
        try:
            yield
        finally:
            self._template = previous

    # -- files -------------------------------------------------------------------------------

    def path_for(self, suite: str, case_id: str) -> Path:
        """Return the file one case's tape lives in.

        Args:
            suite: The suite name.
            case_id: The case's id.

        Returns:
            ``<cassette_dir>/<suite>/<case_id>.json``.

        Raises:
            ProbatioConfigError: Either name would escape the cassette directory.
        """
        check_path_segment(suite, label="suite")
        check_path_segment(case_id, label="case id")
        return self.cassette_dir / suite / f"{case_id}.json"

    def load(self, suite: str, case_id: str) -> Cassette | None:
        """Read one case's tape, from the cache when it has already been read.

        Args:
            suite: The suite name.
            case_id: The case's id.

        Returns:
            The cassette, or ``None`` when there is no file.

        Raises:
            ProbatioConfigError: The file exists but cannot be read or does not parse. A
                corrupted tape is a broken artefact, not a missing recording, for the reason a
                corrupted baseline is (DECISIONS 33).
        """
        cached = self._cache.get((suite, case_id))
        if cached is not None:
            return cached
        path = self.path_for(suite, case_id)
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProbatioConfigError(
                f"the cassette at {path} cannot be read: {exc}",
                case_id=case_id,
                fix=self.record_command,
            ) from exc
        try:
            cassette = Cassette.model_validate_json(text)
        except ValidationError as exc:
            raise ProbatioConfigError(
                f"the cassette at {path} is not a readable cassette file: {exc.errors()[0]['msg']}",
                case_id=case_id,
                fix=self.record_command,
            ) from exc
        self._cache[(suite, case_id)] = cassette
        return cassette

    def write(self, suite: str, cassette: Cassette) -> Path:
        """Write one tape, creating its directory if needed, and cache it.

        Args:
            suite: The suite the case belongs to.
            cassette: The tape to persist.

        Returns:
            The path written.
        """
        self._cache[(suite, cassette.case_id)] = cassette
        return write_json(self.path_for(suite, cassette.case_id), cassette.model_dump(mode="json"))

    # -- the two things a provider asks for --------------------------------------------------

    def key_for(
        self,
        prompt: str,
        system: str | None,
        params: Mapping[str, Any],
        model: str | None = None,
    ) -> str:
        """Return the interaction key for one call in the store's current context.

        Args:
            prompt: The user-turn text.
            system: The system prompt, or ``None``.
            params: The call's parameters.
            model: The answering adapter's own model, used when ``params`` names none.

        Returns:
            :func:`interaction_key`, carrying the judge template hash when a judge is speaking.
        """
        return interaction_key(
            prompt=prompt, system=system, params=params, model=model, template=self._template
        )

    def replay(
        self,
        *,
        prompt: str,
        system: str | None,
        params: Mapping[str, Any],
        model: str | None = None,
    ) -> Completion:
        """Return the recorded answer to one call, without calling anybody.

        Args:
            prompt: The user-turn text.
            system: The system prompt, or ``None``.
            params: The call's parameters.
            model: The answering adapter's own model, used when ``params`` names none.

        Returns:
            The sample this run replays, with the latency the tape recorded.

            A one-sample interaction replayed under a later run adds
            :data:`SINGLE_SAMPLE_NOTE` to :attr:`notes` — unless a judge is speaking. A judge
            prompt carries the answer it is grading, so a suite recorded under ``--runs N`` whose
            answers differed leaves one judge interaction *per run*, each with one sample and each
            replayed only at its own run index. Noting those would tell the reader that a case's
            pass rate can only be 0 or 1 while the report beside it prints 0.90 (DECISIONS 106).

        Raises:
            MissingCassetteError: The case has no tape at all.
            StaleCassetteError: The tape exists but holds no interaction for this call.
            ProbatioConfigError: No case is active, or the tape does not parse.
        """
        case = self.require_active()
        path = self.path_for(case.suite, case.case_id)
        cassette = self.load(case.suite, case.case_id)
        if cassette is None:
            raise MissingCassetteError(
                f"there is no cassette at {self.display(path)} to replay",
                case_id=case.case_id,
                fix=self.record_command,
            )
        key = self.key_for(prompt, system, params, model)
        interaction = cassette.find(key)
        if interaction is None:
            raise StaleCassetteError(
                f"the cassette at {self.display(path)} has no recorded interaction {key}: "
                "the prompt, the model or the params changed since it was recorded, so it must "
                "be re-recorded",
                case_id=case.case_id,
                fix=self.record_command,
            )
        if len(interaction.completions) == 1 and case.run_index > 0 and self._template is None:
            self._note(
                f"{case.case_id}: {SINGLE_SAMPLE_NOTE} replayed for every run, so its pass rate "
                "can only be 0 or 1"
            )
        return interaction.sample(case.run_index)

    def record(
        self,
        completion: Completion,
        *,
        prompt: str,
        system: str | None,
        params: Mapping[str, Any],
        model: str | None = None,
        provider_name: str,
    ) -> Completion:
        """Add one live answer to the active case's tape and write the file.

        The first time a key is recorded through this store the interaction's samples are
        replaced; every later time they are appended, so re-recording a suite under ``--runs N``
        leaves exactly N samples rather than N added to whatever was there before (DECISIONS 44).

        Args:
            completion: What the inner provider returned.
            prompt: The user-turn text.
            system: The system prompt, or ``None``.
            params: The call's parameters.
            model: The answering adapter's own model, used when ``params`` names none.
            provider_name: The inner provider's ``name``, written into the tape.

        Returns:
            ``completion`` unchanged, so a caller can return the value of this call.

        Raises:
            ProbatioConfigError: No case is active, or an existing tape does not parse.
        """
        case = self.require_active()
        cassette = self.load(case.suite, case.case_id)
        if cassette is None:
            cassette = Cassette(
                case_id=case.case_id,
                recorded=timestamp(self.clock),
                provider=provider_name,
                model=completion.model,
            )
        else:
            cassette.recorded = timestamp(self.clock)
            cassette.provider = provider_name
        key = self.key_for(prompt, system, params, model)
        interaction = cassette.find(key)
        if interaction is None:
            interaction = Interaction(
                key=key,
                prompt=prompt,
                system=system,
                params=dict(params),
                model=resolve_model(params, model),
            )
            cassette.interactions.append(interaction)
        seen = (case.suite, case.case_id, key)
        if seen not in self._recorded:
            self._recorded.add(seen)
            interaction.completions = []
        interaction.completions.append(completion)
        self.write(case.suite, cassette)
        return completion

    def _note(self, text: str) -> None:
        """Record an observation once, however many calls make it."""
        if text not in self.notes:
            self.notes.append(text)


class CassetteProvider:
    """A provider that reads a tape, writes one, or gets out of the way.

    It satisfies :class:`~probatio.providers.Provider` and reports the inner adapter's ``name``,
    so a system under test cannot tell it is there and a tape records which real adapter made it.

    Attributes:
        inner: The adapter that would make the live call. Never called in ``replay`` mode.
        store: The tapes and the active context.
        mode: One of :data:`CASSETTE_MODES`.
        name: The inner adapter's name.
    """

    def __init__(
        self, inner: Provider, store: CassetteStore, mode: CassetteMode = "replay"
    ) -> None:
        """Wrap an adapter.

        Args:
            inner: The configured adapter.
            store: The store owning the tapes and the active case.
            mode: ``replay`` (the default), ``record`` or ``off``.

        Raises:
            ProbatioConfigError: ``mode`` is not one of :data:`CASSETTE_MODES`.
        """
        if mode not in CASSETTE_MODES:
            raise ProbatioConfigError(
                f"{mode!r} is not a cassette mode; choose one of {', '.join(CASSETTE_MODES)}"
            )
        self.inner = inner
        self.store = store
        self.mode: CassetteMode = mode
        self.name: str = inner.name

    @property
    def inner_model(self) -> str | None:
        """The model the inner adapter answers with when a call names none.

        Both shipped live adapters take their model from their constructor — which spec §3.12's
        ``--probatio-model`` fills in — and fall back to it whenever ``params`` carries no
        ``model``. Since most cases name no model, without this a tape recorded against one model
        would replay silently against another (DECISIONS 43, amended).

        Returns:
            ``inner.model`` when the adapter has one, otherwise ``None``. An adapter without the
            attribute is not interrogated further.
        """
        model = getattr(self.inner, "model", None)
        return None if model is None else str(model)

    def judge_calls(self, template_hash: str) -> AbstractContextManager[None]:
        """Return the context manager a judge enters to mark its own calls.

        :class:`~probatio.judge.Judge` looks for this method on whatever provider it was handed
        and uses it when it is there, which is how the judge template hash reaches the cassette
        key without a reserved parameter that a live adapter would have to know about
        (DECISIONS 42).

        Args:
            template_hash: :func:`~probatio.judge.judge_template_hash`.

        Returns:
            :meth:`CassetteStore.judge_calls`.
        """
        return self.store.judge_calls(template_hash)

    def complete(self, prompt: str, *, system: str | None = None, **params: Any) -> Completion:
        """Replay, record or pass through one call.

        Args:
            prompt: The user-turn text.
            system: The system prompt, when the case declares one.
            **params: The case's parameters. They reach ``inner`` exactly as they arrived; this
                wrapper adds nothing and removes nothing. The effective model it works out for the
                key is read off the adapter, never written into the call.

        Returns:
            The recorded completion in ``replay`` mode, and the live one in the other two.

        Raises:
            MissingCassetteError: ``replay`` mode and the case has no tape.
            StaleCassetteError: ``replay`` mode and the tape has no interaction for this call.
        """
        if self.mode == "off":
            return self.inner.complete(prompt, system=system, **params)
        if self.mode == "replay":
            return self.store.replay(
                prompt=prompt, system=system, params=params, model=self.inner_model
            )
        completion = self.inner.complete(prompt, system=system, **params)
        return self.store.record(
            completion,
            prompt=prompt,
            system=system,
            params=params,
            model=self.inner_model,
            provider_name=self.inner.name,
        )


class ImportedCall(BaseModel):
    """One line of the JSONL ``probatio import-cassettes`` reads.

    The fields are spec §3.8's list. Unknown keys are refused rather than dropped, because this
    file is produced by an exporter somebody wrote — Phase 11 turns Consilium traces into it — and
    a misspelled ``latency`` silently becoming a zero-latency tape is the kind of quiet loss a
    committed artefact should not absorb (DECISIONS 45).

    Attributes:
        case_id: The case the call belongs to.
        prompt: The user-turn text.
        text: What the model answered.
        model: The model that answered.
        system: The system prompt, or ``None``.
        params: The call's parameters.
        tokens_in: Prompt tokens, when the trace recorded them.
        tokens_out: Completion tokens, when the trace recorded them.
        cost_usd: Cost in US dollars, or ``None`` for unknown; never ``0.0`` as a stand-in.
        latency_ms: How long the call took.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    prompt: str
    text: str
    model: str
    system: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    latency_ms: float = 0.0

    def completion(self) -> Completion:
        """Return the completion this line records.

        Returns:
            A :class:`~probatio.providers.Completion` whose ``raw`` says the line was imported
            rather than recorded, so a reader of the tape knows where it came from.
        """
        return Completion(
            text=self.text,
            model=self.model,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            cost_usd=self.cost_usd,
            latency_ms=self.latency_ms,
            raw={"provider": IMPORT_PROVIDER},
        )


def parse_trace_line(line: str, number: int, *, source: Path | None = None) -> ImportedCall | None:
    """Parse one line of an import JSONL.

    Args:
        line: The line, without its newline.
        number: Its one-based number in the file, named in every error message.
        source: The file, named in every error message when it is known.

    Returns:
        The parsed call, or ``None`` for a blank line, which is not an error.

    Raises:
        ProbatioConfigError: The line is not one JSON object with the fields spec §3.8 lists.
    """
    where = f"line {number}" + (f" of {source}" if source is not None else "")
    if not line.strip():
        return None
    try:
        loaded = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProbatioConfigError(f"{where} is not JSON: {exc.msg} at column {exc.colno}") from exc
    if not isinstance(loaded, dict):
        raise ProbatioConfigError(
            f"{where} is a JSON {type(loaded).__name__}, not an object with a 'case_id'"
        )
    try:
        return ImportedCall.model_validate(loaded)
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or "<record>"
        raise ProbatioConfigError(
            f"{where} is not a usable cassette record: {field}: {first['msg']}"
        ) from exc


def import_cassettes(
    lines: Iterable[str],
    *,
    suite: str,
    store: CassetteStore,
    provider: str = IMPORT_PROVIDER,
    source: Path | None = None,
) -> list[Path]:
    """Build cassette files from a JSONL of recorded interactions.

    Lines sharing a ``case_id`` land in one file, and lines sharing a case and an
    :func:`interaction_key` become one interaction with one sample per line, in file order — which
    is how a trace of N runs of the same prompt becomes a tape that replays a pass rate.

    Args:
        lines: The file's lines, in order.
        suite: The suite the cases belong to, which decides the directory.
        store: The store the files are written through; its clock stamps them.
        provider: The ``provider`` field written into each tape.
        source: The file the lines came from, named in error messages.

    Returns:
        The paths written, in the order the cases first appear.

    Raises:
        ProbatioConfigError: A line is malformed, or a case id or the suite would escape the
            cassette directory.
    """
    check_path_segment(suite, label="suite")
    recorded = timestamp(store.clock)
    cassettes: dict[str, Cassette] = {}
    for number, line in enumerate(lines, start=1):
        call = parse_trace_line(line, number, source=source)
        if call is None:
            continue
        cassette = cassettes.get(call.case_id)
        if cassette is None:
            check_path_segment(call.case_id, label="case id")
            cassette = Cassette(
                case_id=call.case_id,
                recorded=recorded,
                provider=provider,
                model=call.model,
            )
            cassettes[call.case_id] = cassette
        key = interaction_key(
            prompt=call.prompt, system=call.system, params=call.params, model=call.model
        )
        interaction = cassette.find(key)
        if interaction is None:
            interaction = Interaction(
                key=key,
                prompt=call.prompt,
                system=call.system,
                params=dict(call.params),
                model=resolve_model(call.params, call.model),
            )
            cassette.interactions.append(interaction)
        interaction.completions.append(call.completion())
    return [store.write(suite, cassette) for cassette in cassettes.values()]


def read_trace(path: Path) -> Sequence[str]:
    """Read an import JSONL's lines.

    Args:
        path: The file.

    Returns:
        Its lines, without their newlines.

    Raises:
        ProbatioConfigError: The file cannot be read.
    """
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ProbatioConfigError(f"cannot read trace file {str(path)!r}: {exc}") from exc
