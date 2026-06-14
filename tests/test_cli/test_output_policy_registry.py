"""Structural test: every Phase 0 callback declares output_policy (P2.8.22).

Fail-closed enforcement: every callback parser MUST attach output_policy
metadata via set_defaults(). Missing metadata would raise RuntimeError at
validation time (per _validate_output_policy fail-closed contract).
"""

from __future__ import annotations

import pytest

from cli.paper.parser import build_parser


def _all_callback_subcommands() -> list[tuple[list[str], str]]:
    """Return (argv_prefix, description) for every Phase 0 callback."""
    return [
        (["audit", "prose", "dummy.md"], "audit prose"),
        (["audit", "claims", "dummy.md"], "audit claims"),
        (["audit", "code-health"], "audit code-health"),
        (["audit", "citations", "dummy.md"], "audit citations"),
        (["audit", "ethics", "dummy.md"], "audit ethics"),
        (["audit", "writing-quality", "dummy.md"], "audit wq"),
        (["audit", "factuality", "dummy.md", "--evidence", "ev.json"], "audit factuality"),
        (["audit", "tables", "draft/"], "audit tables"),
        (["audit", "quality-appraisal", "--evidence", "ev.json"], "audit qa"),
        (["trace", "MyClass.method"], "trace"),
        (["graph-overview"], "graph-overview"),
        (["gate", "method", "dummy.md"], "gate method"),
        (["doctor"], "doctor"),
    ]


@pytest.mark.parametrize(
    "argv,desc",
    _all_callback_subcommands(),
    ids=[desc for _, desc in _all_callback_subcommands()],
)
def test_every_callback_has_output_policy(argv: list[str], desc: str) -> None:
    """P2.8.22: every Phase 0 callback MUST have output_policy metadata."""
    parser = build_parser()
    args = parser.parse_args(argv)
    policy = getattr(args, "output_policy", None)
    assert policy is not None, f"{desc}: callback missing output_policy (fail-closed violation)"


def test_doctor_is_text_only() -> None:
    """Registration Table: doctor is text-only (rejects --output-format json)."""
    parser = build_parser()
    args = parser.parse_args(["doctor"])
    assert args.output_policy == "text-only"


def test_audit_subcommands_are_json_capable() -> None:
    """Registration Table: all audit subcommands are json-capable."""
    parser = build_parser()
    for sub in ["prose", "claims", "citations", "ethics", "writing-quality"]:
        args = parser.parse_args(["audit", sub, "dummy.md"])
        assert args.output_policy == "json-capable", f"audit {sub} should be json-capable"
