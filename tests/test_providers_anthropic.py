"""Phase 2: the Anthropic adapter, exercised entirely against an injected stub.

Nothing here installs, imports or calls the real SDK. The module under test imports ``anthropic``
dynamically, so a stub module in ``sys.modules`` is enough to exercise every line of the mapping,
and ``None`` in ``sys.modules`` is enough to prove the missing-extra message — whether or not the
extra happens to be installed on the machine running the suite.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from probatio import Completion, ProbatioConfigError
from probatio.budget import ModelPrice, PriceTable

MODULE = "probatio.providers.anthropic"


ABSENT = object()


@pytest.fixture(autouse=True)
def _isolate_sdk() -> Iterator[None]:
    """Import the adapter fresh in every test here, and leave no stub behind in ``sys.modules``."""
    saved = sys.modules.get("anthropic", ABSENT)
    sys.modules.pop(MODULE, None)
    yield
    sys.modules.pop(MODULE, None)
    if saved is ABSENT:
        sys.modules.pop("anthropic", None)
    else:
        sys.modules["anthropic"] = saved


class StubMessages:
    """Records requests and answers them from a canned response."""

    def __init__(self, response: Any) -> None:
        self.response = response
        self.requests: list[dict[str, Any]] = []

    def create(self, **request: Any) -> Any:
        self.requests.append(request)
        return self.response


class StubClient:
    """What the SDK's ``Anthropic()`` looks like from the adapter's point of view."""

    def __init__(self, response: Any) -> None:
        self.messages = StubMessages(response)


def response(
    *,
    text: str = "an answer",
    model: str = "claude-opus-5",
    tokens: tuple[int, int] | None = (469, 14),
    dump: object = None,
    blocks: list[Any] | None = None,
) -> SimpleNamespace:
    """A stand-in for a Messages response, shaped like the SDK's pydantic model."""
    content = blocks if blocks is not None else [SimpleNamespace(type="text", text=text)]
    fields: dict[str, Any] = {"model": model, "content": content}
    if tokens is not None:
        fields["usage"] = SimpleNamespace(input_tokens=tokens[0], output_tokens=tokens[1])
    if dump is not None:
        fields["model_dump"] = lambda mode="python": dump
    return SimpleNamespace(**fields)


def load(sdk: object) -> Any:
    """Import the adapter with ``sdk`` standing in for the ``anthropic`` package."""
    sys.modules["anthropic"] = sdk
    return importlib.import_module(MODULE)


def stub_sdk(client: object | None = None) -> ModuleType:
    """A stub ``anthropic`` module whose ``Anthropic()`` returns ``client``."""
    module = ModuleType("anthropic")
    module.Anthropic = lambda *args, **kwargs: client
    return module


def provider_with(client: StubClient, **kwargs: Any) -> Any:
    """Load the adapter against a stub SDK and build a provider on the given client."""
    return load(stub_sdk()).AnthropicProvider(client=client, **kwargs)


def test_importing_without_the_package_names_the_extra_to_install() -> None:
    """``None`` in ``sys.modules`` is how CPython represents a module that cannot be imported."""
    with pytest.raises(ProbatioConfigError) as caught:
        load(None)
    assert "probatio-llm[anthropic]" in str(caught.value)
    assert caught.value.fix == "pip install 'probatio-llm[anthropic]'"
    assert "anthropic" in caught.value.message
    assert MODULE not in sys.modules


def test_the_import_helper_is_what_raises() -> None:
    module = load(stub_sdk())
    assert module.sdk is sys.modules["anthropic"]
    sys.modules["anthropic"] = None
    with pytest.raises(ProbatioConfigError, match="probatio-llm.anthropic."):
        module.import_sdk()


def test_a_prompt_becomes_one_user_message_with_the_system_prompt_alongside() -> None:
    client = StubClient(response())
    provider = provider_with(client, model="claude-opus-5")
    completion = provider.complete("the prompt", system="the system prompt", temperature=0)

    assert client.messages.requests == [
        {
            "model": "claude-opus-5",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "the prompt"}],
            "system": "the system prompt",
            "temperature": 0,
        }
    ]
    assert isinstance(completion, Completion)
    assert completion.text == "an answer"
    assert completion.model == "claude-opus-5"
    assert (completion.tokens_in, completion.tokens_out) == (469, 14)
    assert completion.latency_ms >= 0.0
    assert provider.name == "anthropic"


def test_no_system_key_is_sent_when_the_case_declares_none() -> None:
    client = StubClient(response())
    provider_with(client, model="m").complete("the prompt")
    assert "system" not in client.messages.requests[0]


def test_the_cases_params_override_the_providers_defaults() -> None:
    client = StubClient(response(model="claude-sonnet-5"))
    provider = provider_with(client, model="claude-opus-5", max_tokens=256)
    completion = provider.complete("p", model="claude-sonnet-5", max_tokens=8, top_p=0.9)
    request = client.messages.requests[0]
    assert (request["model"], request["max_tokens"], request["top_p"]) == (
        "claude-sonnet-5",
        8,
        0.9,
    )
    assert completion.model == "claude-sonnet-5"


def test_the_providers_max_tokens_is_used_when_the_case_names_none() -> None:
    client = StubClient(response())
    provider_with(client, model="m", max_tokens=256).complete("p")
    assert client.messages.requests[0]["max_tokens"] == 256


def test_a_call_with_no_model_anywhere_is_a_configuration_error() -> None:
    client = StubClient(response())
    with pytest.raises(ProbatioConfigError) as caught:
        provider_with(client).complete("p")
    assert "has no model" in str(caught.value)
    assert caught.value.fix == "pytest --probatio-model <model>"
    assert client.messages.requests == []


def test_cost_is_unknown_because_the_api_reports_tokens_not_money() -> None:
    assert provider_with(StubClient(response()), model="m").complete("p").cost_usd is None


def test_text_blocks_are_concatenated_and_other_blocks_ignored() -> None:
    blocks = [
        SimpleNamespace(type="thinking", thinking="hidden"),
        SimpleNamespace(type="text", text="first "),
        SimpleNamespace(type="text", text="second"),
    ]
    client = StubClient(response(blocks=blocks))
    assert provider_with(client, model="m").complete("p").text == "first second"


def test_an_empty_response_is_empty_text_not_a_crash() -> None:
    client = StubClient(response(blocks=[]))
    assert provider_with(client, model="m").complete("p").text == ""


def test_tokens_are_none_when_the_response_reports_no_usage() -> None:
    client = StubClient(response(tokens=None))
    completion = provider_with(client, model="m").complete("p")
    assert (completion.tokens_in, completion.tokens_out) == (None, None)


def test_the_model_falls_back_to_the_one_that_was_asked_for() -> None:
    client = StubClient(response(model=""))
    assert provider_with(client, model="claude-opus-5").complete("p").model == "claude-opus-5"


@pytest.mark.parametrize("dump", [None, {"id": "msg_1", "role": "assistant"}, ["not a dict"]])
def test_raw_carries_the_dump_when_there_is_one_and_nothing_when_there_is_not(
    dump: object,
) -> None:
    client = StubClient(response(dump=dump))
    raw = provider_with(client, model="m").complete("p").raw
    assert raw == (dump if isinstance(dump, dict) else {})


def test_a_client_is_constructed_from_the_sdk_when_none_is_injected() -> None:
    """The only path that would read an API key; it is exercised against the stub, not the SDK."""
    client = StubClient(response())
    module = load(stub_sdk(client))
    provider = module.AnthropicProvider(model="m")
    assert provider.complete("p").text == "an answer"
    assert client.messages.requests[0]["messages"][0]["content"] == "p"


# --- Phase 6: the optional price table (spec §3.3, §3.7) ----------------------------------------


def price_table(**models: tuple[float, float]) -> Any:
    """A ``PriceTable`` over the given ``model: (input_per_mtok, output_per_mtok)`` pairs."""
    return PriceTable(
        {
            model: ModelPrice(input_per_mtok=prices[0], output_per_mtok=prices[1])
            for model, prices in models.items()
        }
    )


def test_a_price_table_prices_the_reported_tokens_at_completion_time() -> None:
    """469 prompt tokens at $10/Mtok is $0.00469; 14 completion tokens at $100/Mtok is $0.0014."""
    client = StubClient(response(model="priced-1", tokens=(469, 14)))
    prices = price_table(**{"priced-1": (10.0, 100.0)})
    completion = provider_with(client, model="priced-1", prices=prices).complete("p")
    assert completion.cost_usd == pytest.approx(0.00469 + 0.0014)


def test_a_table_that_does_not_price_this_model_leaves_the_cost_unknown() -> None:
    client = StubClient(response(model="claude-opus-5"))
    prices = price_table(**{"some-other-model": (10.0, 100.0)})
    assert provider_with(client, model="m", prices=prices).complete("p").cost_usd is None


def test_a_response_with_no_usage_cannot_be_priced_and_says_so_with_none() -> None:
    client = StubClient(response(model="priced-1", tokens=None))
    prices = price_table(**{"priced-1": (10.0, 100.0)})
    completion = provider_with(client, model="priced-1", prices=prices).complete("p")
    assert (completion.tokens_in, completion.tokens_out, completion.cost_usd) == (None, None, None)
