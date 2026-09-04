"""Phase 2: the error hierarchy and the three parts of an error message."""

from __future__ import annotations

import pytest

from probatio import errors


def test_every_error_is_catchable_as_one_family() -> None:
    subclasses = [
        errors.ProbatioConfigError,
        errors.MissingCassetteError,
        errors.StaleCassetteError,
        errors.MissingVariantsError,
        errors.BaselineDriftError,
        errors.BudgetExceededError,
        errors.JudgeOutputError,
    ]
    assert sorted(errors.__all__) == sorted(
        [cls.__name__ for cls in subclasses] + ["ProbatioError"]
    )
    for cls in subclasses:
        assert issubclass(cls, errors.ProbatioError)
        with pytest.raises(errors.ProbatioError):
            raise cls("something went wrong")


def test_message_carries_the_case_id_and_the_fix() -> None:
    exc = errors.MissingCassetteError(
        "no cassette for this case",
        case_id="htn-definition",
        fix="pytest --cassette=record",
    )
    assert str(exc) == (
        "[htn-definition] no cassette for this case; fix it with: pytest --cassette=record"
    )
    assert (exc.message, exc.case_id, exc.fix) == (
        "no cassette for this case",
        "htn-definition",
        "pytest --cassette=record",
    )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, "broken"),
        ({"case_id": "c1"}, "[c1] broken"),
        ({"fix": "probatio freeze-variants"}, "broken; fix it with: probatio freeze-variants"),
    ],
)
def test_optional_parts_are_left_out_when_absent(kwargs: dict[str, str], expected: str) -> None:
    assert str(errors.ProbatioError("broken", **kwargs)) == expected
