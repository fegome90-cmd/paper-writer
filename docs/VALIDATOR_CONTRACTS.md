# paper-writer - Validator Contracts

Defines the result contract that is actually enforced for wrapper-based validation, and distinguishes that from broader validator architecture intent.

## Quick path

1. The canonical enforced result contract in the harness is `ValidatorResult` from `harness/ports/tool_wrapper.py`.
2. The orchestrator consumes that contract by converting `ValidatorResult.to_dict()` into `GateResult` via `validate_validator_gate()`.
3. Not every validator-like surface in this repository flows through that path; some `validators/*.py` classes/functions are called directly from the CLI and emit different shapes.

## Scope

This document separates two layers:

1. Canonical wrapper result contract
Applies to tool wrappers implementing `ToolWrapper.run(...) -> ValidatorResult`.

2. Broader validator architecture intent
Applies to the wider `validators/*.py` ecosystem as a design direction, but not as a universal enforced runtime schema today.

## Canonical Wrapper Result Contract

Observed shape from `ValidatorResult` in `harness/ports/tool_wrapper.py`:

```yaml
validator: refs
status: fail          # pass | warn | fail
summary: DOI missing in 2 entries
findings:
  - code: missing_identifier
    severity: error   # commonly interpreted by gate conversion
    message: Entry lacks DOI or URL
    artifact: templates/references.bib
    location: smith2024voice
artifacts_checked:
  - templates/references.bib
```

Required fields enforced by `ValidatorResult`:
- `validator`
- `status`
- `summary`
- `findings`
- `artifacts_checked`

Enforced invariants:
- `status` must be one of `pass`, `warn`, `fail`
- the object can be serialized via `to_dict()` with the same five fields

What is not enforced by `ValidatorResult` itself:
- a strict schema for each finding object
- a universal list of allowed severities
- any guarantee that all validators receive the same normalized input shape

## Wrapper Wiring Observed In The Orchestrator

Observed in `harness/services/orchestrator.py`:
- The orchestrator builds an `artifacts_input` dict per command.
- The orchestrator passes `context = {"cwd": ...}` to wrappers.
- The wrapper returns `ValidatorResult`.
- The orchestrator converts that result into `GateResult` using `validate_validator_gate()`.

This supports a narrower claim than "validators receive normalized inputs from the orchestrator":
- registered tool wrappers do receive orchestrator-built `artifacts` and `context`
- direct CLI validators such as `CitationVerifyValidator`, `EthicsValidator`, and `WritingQualityValidator` do not use this wrapper path

## Broader Validator Architecture Intent

Conceptual architecture intent retained for documentation value:
- domain validators in `validators/*.py` generally produce structured findings instead of raw subprocess text
- wrappers are the normalization boundary for external tools used by the orchestrator
- the harness, not individual validators, is responsible for gate mutation in the wrapper-based pipeline

This section is architectural intent, not a claim that every validator module currently conforms to one identical runtime contract.

## Severity Handling In Gate Conversion

Observed in `validate_validator_gate()`:

| Finding severity in wrapper result | Gate conversion effect |
|---|---|
| `error` | becomes blocker; gate forced to `fail` |
| `warning` | becomes warning; may produce `warn` if there are no blockers |
| other / missing | ignored for blocker-warning bucketing unless the wrapper status already indicates failure |

Important nuance:
- This severity handling belongs to wrapper-result to gate conversion.
- It does not describe the full severity systems used by all validators in `validators/*.py`; several direct CLI validators use severities like `P0`, `P1`, `P2`.

## Gate Mapping

The table below keeps only mappings strongly supported by orchestrator wiring, and labels broader mappings as conceptual or extension paths.

| Surface | Gate mapping status | Evidence level |
|---|---|---|
| `lint_bib` wrapper | `bib_normalized` | strong: wired in `Orchestrator._run_gate_verification()` |
| `check_refs` wrapper | `citations_resolved` | strong: wired with gate override |
| `check_refs_metadata` wrapper | `refs_validated` | strong: wired with gate override |
| `lint_style` wrapper | `style_passed` | strong: wired in orchestrator |
| `audit_reporting` wrapper | `reporting_passed` | strong: wired in orchestrator |
| render wrapper | `render_passed` | strong: wired in orchestrator |
| `validators.refs.validate_refs_metadata()` | conceptual domain logic likely feeding `refs_validated`, but not directly wired here | conceptual |
| `validators.citations.validate_citation_consistency()` | conceptual domain logic likely feeding `citations_resolved`, but not directly wired here | conceptual |
| `validators.style.validate_style()` | conceptual domain logic likely feeding `style_passed`, but not directly wired here | conceptual |
| `validators.reporting.validate_reporting()` | conceptual domain logic likely feeding `reporting_passed`, but not directly wired here | conceptual |
| `validators.structure.validate_section_structure()` | possible future/extension path; no current dedicated gate wiring | extension |
| `validators.citation_verify.CitationVerifyValidator` | aligns naturally with soft gate `citation_verified`, but current evidence is CLI/direct-validator usage rather than orchestrator gate wiring | soft gate path / conceptual |
| `validators.ethics.EthicsValidator` | aligns naturally with soft gate `ethics_passed`, but current evidence is CLI/direct-validator usage rather than orchestrator gate wiring | soft gate path / conceptual |
| `validators.claim_alignment.ClaimAlignmentValidator` | no audited orchestrator gate mapping | conceptual |
| `validators.writing_quality.WritingQualityValidator` | no audited orchestrator gate mapping | conceptual |

## Rules

- Wrappers used by the orchestrator do not mutate `outputs/state.yaml` directly; the orchestrator/state manager own gate persistence.
- `tests/skills/test_adapters.py` also asserts that skill adapters do not write `outputs/state.yaml`.
- The orchestrator does not consume raw subprocess text as business output; it consumes `ValidatorResult` from wrappers.
- Direct CLI validators may still build their own structured report payloads outside the wrapper contract.
- The harness decides final gate mutation from wrapper-derived output in the orchestrated pipeline.

## Audit Checklist

- [ ] Claims labeled as enforced are backed by `ValidatorResult` or orchestrator wiring
- [ ] Direct CLI validator paths are not overstated as using the wrapper contract
- [ ] Gate mappings without strong wiring evidence are labeled conceptual, extension, or soft-gate path
