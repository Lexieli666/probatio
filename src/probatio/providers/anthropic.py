"""``AnthropicProvider``: the Anthropic Python SDK, behind the provider protocol.

The SDK is an optional extra, so this module is imported dynamically rather than declared: a user
who never sets ``--probatio-provider anthropic`` does not install ``anthropic``, and one who does
without the extra gets a :class:`~probatio.errors.ProbatioConfigError` naming the install command
instead of a bare ``ModuleNotFoundError`` from an import line they did not write.

Importing the SDK is not the same as calling it. Import happens when this module is imported;
network calls happen only in :meth:`AnthropicProvider.complete`, and the constructor takes a
``client``, so Probatio's own tests exercise every line of the mapping below against an injected
stub with no API key in the environment.
"""

from __future__ import annotations

import importlib
import time
from typing import Any, Final

from ..errors import ProbatioConfigError
from .base import Completion

__all__ = ["ANTHROPIC_EXTRA", "DEFAULT_MAX_TOKENS", "AnthropicProvider", "import_sdk"]

ANTHROPIC_EXTRA: Final = "probatio-llm[anthropic]"
"""The extra to install to get the SDK; named in the error raised when it is missing."""

DEFAULT_MAX_TOKENS: Final = 1024
"""``max_tokens`` is required by the Messages API, so an unset case gets this."""


def import_sdk() -> Any:
    """Import the ``anthropic`` SDK, or explain how to install it.

    Every import failure is reported the same way, because the actionable answer is the same:
    a missing package, a half-removed one and one whose own dependencies are broken all mean the
    extra needs installing. The original exception text is included so a genuinely odd failure is
    still diagnosable.

    Returns:
        The imported ``anthropic`` module.

    Raises:
        ProbatioConfigError: The package could not be imported.
    """
    try:
        return importlib.import_module("anthropic")
    except ImportError as exc:
        raise ProbatioConfigError(
            "the 'anthropic' package is not installed or failed to import "
            f"({exc}), so probatio.providers.anthropic cannot be used",
            fix=f"pip install '{ANTHROPIC_EXTRA}'",
        ) from exc


sdk: Any = import_sdk()
"""The ``anthropic`` module. Bound at import time so a missing extra fails here, once."""


class AnthropicProvider:
    """Calls the Anthropic Messages API through the official SDK.

    Cost is always ``None``: the Messages API reports token counts, not money, and Probatio does
    not ship a price list. A case with a cost ceiling therefore reports that ceiling as
    unenforceable rather than as passed until a price table is configured.

    Attributes:
        name: ``"anthropic"``.
    """

    name: str = "anthropic"

    def __init__(
        self,
        *,
        model: str | None = None,
        client: Any | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        """Build the provider, constructing a client from the environment unless one is given.

        Args:
            model: The default model, used for calls whose ``params`` name none.
            client: An object with a ``messages.create(...)`` method. When ``None``, the SDK's
                own ``anthropic.Anthropic()`` is constructed, which reads the API key from the
                environment. Probatio's tests always pass one.
            max_tokens: The default ``max_tokens`` for calls whose ``params`` name none.
        """
        self.model = model
        self.max_tokens = max_tokens
        self._client: Any = sdk.Anthropic() if client is None else client

    def complete(self, prompt: str, *, system: str | None = None, **params: Any) -> Completion:
        """Send one user-turn message and map the response onto a :class:`Completion`.

        Every parameter other than ``model`` is forwarded to ``messages.create`` unchanged, so
        ``temperature``, ``top_p``, ``stop_sequences`` and anything else the SDK accepts work
        without Probatio maintaining a list of them.

        Args:
            prompt: The user-turn text.
            system: The system prompt, when the case declares one.
            **params: The case's parameters. ``model`` overrides the constructor's.

        Returns:
            The completion, with ``cost_usd`` of ``None``.

        Raises:
            ProbatioConfigError: No model was configured, here or on the case.
        """
        request: dict[str, Any] = dict(params)
        model = request.pop("model", None) or self.model
        if not model:
            raise ProbatioConfigError(
                "AnthropicProvider has no model; set one on the case's params or on the provider",
                fix="pytest --probatio-model <model>",
            )
        request["model"] = model
        request.setdefault("max_tokens", self.max_tokens)
        request["messages"] = [{"role": "user", "content": prompt}]
        if system is not None:
            request["system"] = system

        started = time.perf_counter()
        response = self._client.messages.create(**request)
        latency_ms = (time.perf_counter() - started) * 1000.0

        usage = getattr(response, "usage", None)
        return Completion(
            text=_text_of(response),
            model=str(getattr(response, "model", None) or model),
            tokens_in=_int_or_none(getattr(usage, "input_tokens", None)),
            tokens_out=_int_or_none(getattr(usage, "output_tokens", None)),
            cost_usd=None,
            latency_ms=latency_ms,
            raw=_raw_of(response),
        )


def _text_of(response: Any) -> str:
    """Concatenate the text blocks of a Messages response, ignoring blocks of other types."""
    blocks = getattr(response, "content", None) or []
    return "".join(str(text) for block in blocks if (text := getattr(block, "text", None)))


def _int_or_none(value: Any) -> int | None:
    """Coerce a reported token count to ``int``, or to ``None`` when it is absent."""
    return None if value is None else int(value)


def _raw_of(response: Any) -> dict[str, Any]:
    """Dump a response to JSON-safe data, tolerating a stub that is not a pydantic model."""
    dump = getattr(response, "model_dump", None)
    if callable(dump):
        dumped = dump(mode="json")
        if isinstance(dumped, dict):
            return {str(key): value for key, value in dumped.items()}
    return {}
