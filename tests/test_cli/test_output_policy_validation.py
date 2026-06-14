"""Tests for output._validate_output_policy (P2.5.3, P2.8.22).

Validates the output-policy contract per design.md:331-355:
- 'json-capable' (default): accepts --output-format json
- 'text-only': rejects --output-format json with UserInputError (exit 2 path)
- 'external': ignores global format (module controls its own output)
- fail-closed: a callback WITHOUT output_policy metadata raises RuntimeError
- pipelines (func=None) skip validation entirely
"""

from __future__ import annotations

import argparse

import pytest

from cli.paper.errors import UserInputError
from cli.paper.output import OutputFormat, OutputPolicy, _validate_output_policy


def _ns(**kwargs: object) -> argparse.Namespace:
    """Build an argparse.Namespace with output_policy + output_format defaults."""
    base: dict[str, object] = {
        "command": "test_cmd",
        "output_policy": None,
        "output_format": "text",
        "func": lambda _args: None,  # treat as a callback by default
    }
    base.update(kwargs)
    return argparse.Namespace(**base)


@pytest.mark.parametrize(
    "policy,fmt",
    [
        ("json-capable", "json"),
        ("json-capable", "text"),
        ("text-only", "text"),
        ("external", "json"),
        ("external", "text"),
    ],
    ids=[
        "json-capable+json",
        "json-capable+text",
        "text-only+text",
        "external+json",
        "external+text",
    ],
)
def test_validate_output_policy_accepts_valid_combinations(
    policy: OutputPolicy, fmt: OutputFormat
) -> None:
    """json-capable accepts json; text-only accepts text; external ignores global fmt."""
    args = _ns(output_policy=policy, output_format=fmt)
    # Should NOT raise — no return value to assert, just absence of exception.
    _validate_output_policy(args, fmt)


def test_validate_output_policy_rejects_json_on_text_only() -> None:
    """P2.8.22: text-only callback + --output-format json -> UserInputError (exit 2 path)."""
    args = _ns(output_policy="text-only", output_format="json")
    with pytest.raises(UserInputError, match="json is not supported"):
        _validate_output_policy(args, "json")


def test_validate_output_policy_fail_closed_on_missing_metadata() -> None:
    """P2.8.22: a callback with NO output_policy metadata -> RuntimeError (config error)."""
    args = _ns(output_policy=None, output_format="text")
    args.func = lambda _a: None  # is a callback (func set) but policy missing
    with pytest.raises(RuntimeError, match="Missing output_policy"):
        _validate_output_policy(args, "text")


def test_validate_output_policy_skips_pipelines() -> None:
    """Pipelines (func=None) skip validation — they are orchestrator-driven, not callbacks."""
    args = _ns(output_policy=None, output_format="json")
    args.func = None  # pipeline: no callback
    # Must NOT raise even though output_policy is None (pipeline skips validation).
    _validate_output_policy(args, "json")


def test_user_input_error_message_has_no_error_prefix() -> None:
    """P2.8.18: UserInputError message must NOT contain 'Error:' (emit_error adds it)."""
    args = _ns(output_policy="text-only", output_format="json")
    with pytest.raises(UserInputError) as exc_info:
        _validate_output_policy(args, "json")
    assert "Error:" not in str(exc_info.value)
