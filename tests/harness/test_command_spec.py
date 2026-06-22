"""Tests for CommandSpec and COMMAND_REGISTRY (Task B1).

Verifies the transitory command registry mirrors PIPELINE_MAP and Phase 0
registrations with correct state policies, stage requirements, and types.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import get_type_hints

import pytest

from cli.paper.dispatch import PIPELINE_MAP
from harness.domain.command_spec import COMMAND_REGISTRY, CommandSpec
from harness.domain.state import ManuscriptState

_VALID_OPERATIONS = {"create", "audit", "revise", "unknown"}
_VALID_HANDLER_KINDS = {"orchestrated", "callback_direct"}
_VALID_OWNER_KINDS = {"core", "integration", "local_subproject"}
_VALID_STATE_POLICIES = {
    "pipeline_initializer",
    "pipeline_governed",
    "standalone_allowed",
}


class TestCommandSpecStructure:
    """B1: CommandSpec is a frozen dataclass with tuple fields."""

    def test_command_spec_frozen(self) -> None:
        spec = COMMAND_REGISTRY["init"]
        with pytest.raises(FrozenInstanceError):
            spec.id = "mutated"  # type: ignore[misc]

    def test_command_spec_tuples(self) -> None:
        """required_gates and requires_args MUST be tuples, not lists."""
        for spec in COMMAND_REGISTRY.values():
            assert isinstance(spec.required_gates, tuple), (
                f"{spec.id}.required_gates must be tuple, got {type(spec.required_gates).__name__}"
            )
            assert isinstance(spec.requires_args, tuple), (
                f"{spec.id}.requires_args must be tuple, got {type(spec.requires_args).__name__}"
            )
            assert isinstance(spec.cli_path, tuple), (
                f"{spec.id}.cli_path must be tuple, got {type(spec.cli_path).__name__}"
            )


class TestCommandRegistryClassification:
    """B1: classification fields have valid values."""

    def test_operation_is_valid(self) -> None:
        for spec in COMMAND_REGISTRY.values():
            assert spec.operation in _VALID_OPERATIONS, (
                f"{spec.id}.operation '{spec.operation}' not in {_VALID_OPERATIONS}"
            )

    def test_handler_kind_is_valid(self) -> None:
        for spec in COMMAND_REGISTRY.values():
            assert spec.handler_kind in _VALID_HANDLER_KINDS, (
                f"{spec.id}.handler_kind '{spec.handler_kind}' not in {_VALID_HANDLER_KINDS}"
            )

    def test_owner_kind_is_valid(self) -> None:
        for spec in COMMAND_REGISTRY.values():
            assert spec.owner_kind in _VALID_OWNER_KINDS, (
                f"{spec.id}.owner_kind '{spec.owner_kind}' not in {_VALID_OWNER_KINDS}"
            )

    def test_state_policy_is_valid(self) -> None:
        for spec in COMMAND_REGISTRY.values():
            assert spec.state_policy in _VALID_STATE_POLICIES, (
                f"{spec.id}.state_policy '{spec.state_policy}' not in {_VALID_STATE_POLICIES}"
            )


class TestCommandRegistryStageGates:
    """B1: stage and gate values are valid."""

    def test_minimum_stage_is_valid(self) -> None:
        for spec in COMMAND_REGISTRY.values():
            assert spec.minimum_stage in ManuscriptState.STAGE_ORDER, (
                f"{spec.id}.minimum_stage '{spec.minimum_stage}' not in STAGE_ORDER"
            )

    def test_required_gates_are_valid(self) -> None:
        valid_gates = ManuscriptState.REQUIRED_GATES | ManuscriptState.SOFT_GATES
        for spec in COMMAND_REGISTRY.values():
            for gate in spec.required_gates:
                assert gate in valid_gates, (
                    f"{spec.id}.required_gates contains unknown gate '{gate}'"
                )

    def test_produced_gates_are_valid(self) -> None:
        valid_gates = ManuscriptState.REQUIRED_GATES | ManuscriptState.SOFT_GATES
        for spec in COMMAND_REGISTRY.values():
            for gate in spec.produced_gates:
                assert gate in valid_gates, (
                    f"{spec.id}.produced_gates contains unknown gate '{gate}'"
                )


class TestCommandRegistryStatePolicy:
    """B1: state_policy rules for standalone / pipeline_initializer / governed."""

    def test_standalone_commands_have_empty_gates(self) -> None:
        for spec in COMMAND_REGISTRY.values():
            if spec.state_policy == "standalone_allowed":
                assert spec.required_gates == (), (
                    f"Standalone command '{spec.id}' has non-empty required_gates: "
                    f"{spec.required_gates}"
                )

    def test_pipeline_initializer_commands_have_empty_gates(self) -> None:
        for spec in COMMAND_REGISTRY.values():
            if spec.state_policy == "pipeline_initializer":
                assert spec.required_gates == (), (
                    f"Pipeline initializer '{spec.id}' has non-empty required_gates: "
                    f"{spec.required_gates}"
                )

    def test_standalone_commands_have_state_policy(self) -> None:
        for cmd_id in ("audit:prose", "audit:claims", "gate:method"):
            assert cmd_id in COMMAND_REGISTRY, f"{cmd_id} missing from COMMAND_REGISTRY"
            assert COMMAND_REGISTRY[cmd_id].state_policy == "standalone_allowed", (
                f"{cmd_id} should be standalone_allowed"
            )

    def test_init_has_pipeline_initializer_policy(self) -> None:
        assert "init" in COMMAND_REGISTRY
        assert COMMAND_REGISTRY["init"].state_policy == "pipeline_initializer"


class TestCommandRegistryParity:
    """B1: COMMAND_REGISTRY mirrors PIPELINE_MAP keys (parity test)."""

    def test_command_registry_has_all_orchestrated_commands(self) -> None:
        for key in PIPELINE_MAP:
            assert key in COMMAND_REGISTRY, (
                f"PIPELINE_MAP key '{key}' missing from COMMAND_REGISTRY"
            )

    def test_command_registry_parity_with_pipeline_map(self) -> None:
        """Every PIPELINE_MAP dispatch_key must have a matching dispatch_key."""
        registry_dispatch_keys = {
            spec.dispatch_key
            for spec in COMMAND_REGISTRY.values()
            if spec.dispatch_key is not None
        }
        for key in PIPELINE_MAP:
            assert key in registry_dispatch_keys, (
                f"PIPELINE_MAP key '{key}' has no matching dispatch_key in COMMAND_REGISTRY"
            )

    def test_command_registry_has_all_phase0_commands(self) -> None:
        phase0_ids = {
            "doctor",
            "gate:method",
            "trace",
            "graph-overview",
            "audit:prose",
            "audit:claims",
            "audit:citations",
            "audit:ethics",
            "audit:writing-quality",
            "audit:code-health",
            "audit:factuality",
            "audit:tables",
            "audit:quality-appraisal",
        }
        for cmd_id in phase0_ids:
            assert cmd_id in COMMAND_REGISTRY, f"Phase 0 command '{cmd_id}' missing"

    def test_command_registry_has_all_zotero_commands(self) -> None:
        zotero_ids = {
            "zotero:collections",
            "zotero:search",
            "zotero:get",
            "zotero:create",
            "zotero:template",
            "zotero:update",
            "zotero:delete",
            "zotero:upload",
        }
        for cmd_id in zotero_ids:
            assert cmd_id in COMMAND_REGISTRY, f"Zotero command '{cmd_id}' missing"

    def test_command_registry_has_all_thesaurus_commands(self) -> None:
        thesaurus_ids = {
            "thesaurus:import",
            "thesaurus:search",
            "thesaurus:list",
            "thesaurus:audit",
            "thesaurus:rebuild",
        }
        for cmd_id in thesaurus_ids:
            assert cmd_id in COMMAND_REGISTRY, f"Thesaurus command '{cmd_id}' missing"

    def test_command_registry_has_all_mesh_commands(self) -> None:
        mesh_ids = {
            "mesh:import",
            "mesh:resolve",
            "mesh:expand",
            "mesh:export",
        }
        for cmd_id in mesh_ids:
            assert cmd_id in COMMAND_REGISTRY, f"MeSH command '{cmd_id}' missing"

    def test_semantic_parity_chain_minimum_stage(self) -> None:
        """chain must require stage 'screen' (verified against Orchestrator)."""
        assert COMMAND_REGISTRY["chain"].minimum_stage == "screen"


class TestCommandRegistryWorkflowRank:
    """B1: commands with workflow_rank have produced_gates and recommended_when."""

    def test_workflow_rank_fields(self) -> None:
        for spec in COMMAND_REGISTRY.values():
            if spec.workflow_rank is not None:
                assert spec.produced_gates, (
                    f"{spec.id} has workflow_rank but no produced_gates"
                )
                assert spec.recommended_when_gates_missing, (
                    f"{spec.id} has workflow_rank but no recommended_when_gates_missing"
                )


class TestCommandSpecTypeAnnotations:
    """B1: Literal type for state_policy includes all three values."""

    def test_state_policy_literal_has_three_values(self) -> None:
        hints = get_type_hints(CommandSpec)
        # The annotation is a Literal — extract its args
        state_policy_hint = hints["state_policy"]
        args = set(getattr(state_policy_hint, "__args__", ()))
        assert args == _VALID_STATE_POLICIES, (
            f"state_policy Literal must include {_VALID_STATE_POLICIES}, got {args}"
        )
