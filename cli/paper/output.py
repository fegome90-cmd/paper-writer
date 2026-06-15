"""CLI output contract: stdout for results, stderr for diagnostics.

Five-channel output contract:
- emit_result: requested results to stdout (NEVER suppressed by --quiet)
- emit_json: structured JSON to stdout (NEVER suppressed)
- emit_info: progress/secondary info to stderr (suppressed by --quiet)
- emit_warning: warnings to stderr (suppressed by --quiet)
- emit_error: errors to stderr (NEVER suppressed)

Uses OutputConfig as single source of truth for quiet + output_format.
summary() reads _config.output_format to decide text vs JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from cli.paper.errors import UserInputError

if TYPE_CHECKING:
    from harness.services.orchestrator import OrchestratorResult

OutputFormat = Literal["text", "json"]
OutputPolicy = Literal["json-capable", "text-only", "external"]
JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


@dataclass(frozen=True)
class OutputConfig:
    quiet: bool = False
    output_format: OutputFormat = "text"


_config = OutputConfig()


def configure(*, quiet: bool = False, output_format: OutputFormat = "text") -> None:
    """Configure output state. Replaces _config cleanly across repeated invocations."""
    global _config
    _config = OutputConfig(quiet=quiet, output_format=output_format)


def effective_output_format(args: argparse.Namespace) -> OutputFormat:
    """Resolve output format: subcommand --output overrides root --output-format.

    NOTE: Phase 0 callback subcommands (audit/gate/graph) have per-handler --output.
    In PR2, its default changes from "terminal" to None so root --output-format
    can take effect. Zotero has a legacy --json flag handled separately.
    """
    specific = getattr(args, "output", None)
    if specific == "json":
        return "json"
    if specific == "terminal":
        return "text"
    return cast(OutputFormat, getattr(args, "output_format", "text"))


def emit_result(msg: str) -> None:
    """Write requested result to stdout. NEVER suppressed by --quiet."""
    print(msg)


def emit_json(data: object) -> None:
    """Write structured JSON to stdout. NEVER suppressed (data consumers need it)."""
    print(json.dumps(to_json_value(data), indent=2, ensure_ascii=False))


def emit_info(message: str) -> None:
    """Write progress/secondary info to stderr. Suppressed by --quiet."""
    if not _config.quiet:
        print(message, file=sys.stderr)


def emit_warning(message: str) -> None:
    """Write warning to stderr. Suppressed by --quiet.

    NOTE: The message should NOT include a 'Warning:' prefix —
    emit_warning() adds it.
    """
    if not _config.quiet:
        print(f"Warning: {message}", file=sys.stderr)


def emit_error(msg: str) -> None:
    """Write error to stderr. NEVER suppressed."""
    print(f"Error: {msg}", file=sys.stderr)


def summary(result: OrchestratorResult) -> None:
    """Write structured pipeline summary. Reads format from _config."""
    if _config.output_format == "json":
        emit_json(_serialize_result(result))
        return
    # text mode
    for step in result.steps:
        status = step.get("status")
        step_id = step.get("step_id")
        error = step.get("error")
        if status == "succeeded":
            emit_info(f"[ok] Step: {step_id}")
        elif status == "failed":
            emit_info(f"[!!] Step: {step_id} - FAILED")
            if error:
                emit_info(f"     Error: {error}")
        else:
            emit_info(f"[--] Step: {step_id} - {status.upper() if status else 'UNKNOWN'}")
    if result.success:
        emit_result(
            f"Success: Stage progressed from '{result.stage_before}' to '{result.stage_after}'."
        )
    else:
        emit_result("Pipeline Blocked:")
        for blocker in result.blockers:
            emit_result(f"  - {blocker}")
    if result.warnings:
        for warning in result.warnings:
            emit_warning(warning)
    if result.artifacts:
        emit_result("Artifacts:")
        for artifact in result.artifacts:
            emit_result(f"  - {artifact}")


def _serialize_result(result: OrchestratorResult) -> dict[str, JSONValue]:
    """Normalize OrchestratorResult to JSON-safe dict."""
    return {
        "command": to_json_value(result.command),
        "success": to_json_value(result.success),
        "stage_before": to_json_value(result.stage_before),
        "stage_after": to_json_value(result.stage_after),
        "steps": to_json_value(result.steps),
        "blockers": to_json_value(result.blockers),
        "warnings": to_json_value(result.warnings),
        "artifacts": to_json_value(result.artifacts),
        "exit_code": to_json_value(result.exit_code),
    }


def to_json_value(value: object) -> JSONValue:
    """Explicit normalization of arbitrary objects to JSONValue.

    NEVER use default=str — it hides contract errors. Raises TypeError on
    circular references (self-referential dataclasses) instead of RecursionError.
    """
    return _to_json_value(value, set())


def _to_json_value(value: object, seen: set[int]) -> JSONValue:
    """Recursive normalizer. ``seen`` tracks id() of mutable containers to detect cycles."""
    # NOTE: check bool BEFORE int (bool is a subclass of int in Python)
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    # Cycle detection for compound types (list/dict/dataclass). Primitives are
    # immutable and cannot participate in cycles, so they skip the guard.
    if isinstance(value, (list, tuple, dict)):
        obj_id = id(value)
        if obj_id in seen:
            raise TypeError(
                f"Circular reference detected in {type(value).__name__} "
                f"(JSON cannot represent cycles)"
            )
        seen.add(obj_id)
    if isinstance(value, list):
        return [_to_json_value(v, seen) for v in value]
    if isinstance(value, tuple):
        return [_to_json_value(v, seen) for v in value]
    if isinstance(value, dict):
        result: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"JSON object key must be str, got {type(key).__name__}")
            result[key] = _to_json_value(item, seen)
        return result
    # Path, Enum, dataclass, datetime -> explicit normalization (NO default=str per spec S9)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return _to_json_value(value.value, seen)
    if is_dataclass(value) and not isinstance(value, type):
        # Detect cycle on the dataclass INSTANCE before recursing into its fields.
        # NOTE: asdict() recurses internally and would stack-overflow on cycles
        # BEFORE our seen-guard runs. So we iterate fields manually and delegate
        # each field value to _to_json_value, letting the seen-set catch cycles.
        obj_id = id(value)
        if obj_id in seen:
            raise TypeError(
                f"Circular reference detected in dataclass {type(value).__name__} "
                f"(JSON cannot represent cycles)"
            )
        seen.add(obj_id)
        result_dc: dict[str, JSONValue] = {}
        for f in fields(value):
            result_dc[f.name] = _to_json_value(getattr(value, f.name), seen)
        return result_dc
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"No JSON normalization defined for {type(value).__name__}")


def validate_output_policy(args: argparse.Namespace, output_format: OutputFormat) -> None:
    """Reject --output-format json for text-only callbacks. Fail-closed (P2.5.3).

    Policies (per design.md Registration Table):
    - 'json-capable': accepts --output-format json
    - 'text-only': rejects json with UserInputError (exit 2 path)
    - 'external': ignores global format (module controls its own output)

    Fail-closed: a callback WITHOUT output_policy metadata raises RuntimeError
    (config error), NOT an implicit json-capable default.
    Pipelines (func=None) skip validation — they are orchestrator-driven.
    """
    # Pipelines (no func callback) skip policy validation
    if getattr(args, "func", None) is None:
        return

    policy: OutputPolicy | None = getattr(args, "output_policy", None)
    if policy is None:
        raise RuntimeError(f"Missing output_policy for callback command: {args.command}")

    if output_format == "json" and policy == "text-only":
        # No "Error:" prefix — emit_error() adds it at the boundary
        raise UserInputError(f"--output-format json is not supported for '{args.command}'")
    # 'external' and 'json-capable' fall through: no rejection
