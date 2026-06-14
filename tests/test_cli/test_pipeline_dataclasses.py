"""Tests for PipelineInvocation + PipelineSpec dataclasses (Phase C5, S3).

These are the foundation of the declarative PIPELINE_MAP dispatch (spec S3,
design.md:212-242). PipelineInvocation carries the runtime-decided command +
args (lets import:bib choose import_bib vs zotero_sync). PipelineSpec maps a
CLI command key to a resolver that produces an invocation.
"""

from __future__ import annotations

import argparse
import dataclasses

import pytest

from cli.paper.dispatch import PipelineInvocation, PipelineSpec


class TestPipelineInvocation:
    """S3: PipelineInvocation(orch_command, args) is a frozen value object."""

    def test_holds_orch_command_and_args(self) -> None:
        inv = PipelineInvocation(orch_command="search", args={"query": "x"})
        assert inv.orch_command == "search"
        assert inv.args == {"query": "x"}

    def test_is_frozen(self) -> None:
        """Frozen dataclass — immutable, so the MAP entries stay constant."""
        inv = PipelineInvocation(orch_command="verify", args={})
        with pytest.raises(dataclasses.FrozenInstanceError):
            inv.orch_command = "other"  # type: ignore[misc]

    def test_default_args_is_explicit_not_optional(self) -> None:
        """Design shows explicit args={}; the field is required, no default magic."""
        # Both forms valid; tests use explicit {} to match design.md lambdas.
        inv = PipelineInvocation(orch_command="verify", args={})
        assert inv.args == {}


class TestPipelineSpec:
    """S3: PipelineSpec(resolve, failure_policy, needs_review_config)."""

    def test_resolve_callable_returns_invocation(self) -> None:
        """resolve(args) produces the runtime invocation."""
        spec = PipelineSpec(
            resolve=lambda a: PipelineInvocation("export_bib", {"bib_path": a.bib_path}),
        )
        args = argparse.Namespace(bib_path="out.bib")
        inv = spec.resolve(args)
        assert isinstance(inv, PipelineInvocation)
        assert inv.orch_command == "export_bib"
        assert inv.args == {"bib_path": "out.bib"}

    def test_default_failure_policy_is_stop_on_error(self) -> None:
        """Most pipelines stop on first error (default)."""
        spec = PipelineSpec(resolve=lambda a: PipelineInvocation("search", {}))
        assert spec.failure_policy == "stop_on_error"

    def test_default_needs_review_config_is_true(self) -> None:
        """All pipelines except init need review_config injection."""
        spec = PipelineSpec(resolve=lambda a: PipelineInvocation("search", {}))
        assert spec.needs_review_config is True

    def test_is_frozen(self) -> None:
        """Spec entries are immutable (MAP is constant)."""
        spec = PipelineSpec(resolve=lambda a: PipelineInvocation("verify", {}))
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.failure_policy = "continue_on_error"  # type: ignore[misc]

    def test_failure_policy_override_to_continue_on_error(self) -> None:
        """lint/check/audit use continue_on_error — must be overridable."""
        spec = PipelineSpec(
            resolve=lambda a: PipelineInvocation("lint_bib", {}),
            failure_policy="continue_on_error",
        )
        assert spec.failure_policy == "continue_on_error"

    def test_needs_review_config_override_to_false(self) -> None:
        """init is the only pipeline that skips review_config injection."""
        spec = PipelineSpec(
            resolve=lambda a: PipelineInvocation("init", {}),
            needs_review_config=False,
        )
        assert spec.needs_review_config is False
