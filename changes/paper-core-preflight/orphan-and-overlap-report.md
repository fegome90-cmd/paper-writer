# Orphan and Overlap Report: Paper Writer Repository

**Date:** 2026-06-19
**Status:** Reconciled with SDD artifacts (pass 7)
**Supersedes:** Previous version missing real overlaps

---

## Overlapping Capabilities (Duplicate Authorities)

### OV-1: Command Routing — PIPELINE_MAP vs COMMAND_REGISTRY
**Observation:** `PIPELINE_MAP` in `cli/paper/dispatch.py` maps command names to handlers and pipeline metadata. `COMMAND_REGISTRY` in `harness/domain/command_spec.py` maps command names to `CommandSpec` objects with stage requirements and progression metadata.
**Assessment:** TRUE OVERLAP — two authorities for command routing and metadata.
**Risk:** Divergence between the two registries could cause preflight to recommend commands that dispatch cannot execute, or vice versa.
**Mitigation:** Parity tests verify PIPELINE_MAP keys ⊆ COMMAND_REGISTRY keys. Semantic tests verify stage alignment. Dispatch remains authoritative for execution; COMMAND_REGISTRY is a policy mirror.
**Action:** Add parity tests in Task B1. Document that COMMAND_REGISTRY is a transitory mirror in v1.

### OV-2: Stage Requirements — _validate_preconditions.command_min_stages vs CommandSpec.minimum_stage
**Observation:** `Orchestrator._validate_preconditions()` in `harness/services/orchestrator.py` hardcodes `command_min_stages` dict mapping command names to minimum stages. `CommandSpec.minimum_stage` in `harness/domain/command_spec.py` declares the same information.
**Assessment:** TRUE OVERLAP — two authorities for command stage requirements.
**Risk:** Divergence could cause Orchestrator to accept commands at stages that preflight blocks, or vice versa.
**Mitigation:** Parity tests verify alignment. COMMAND_REGISTRY may be STRICTER than Orchestrator (policy augmentation). Full migration (Orchestrator reads from COMMAND_REGISTRY) is a v2 concern.
**Action:** Add semantic parity tests in Task B1. Document intentional strictness.

### OV-3: Command IDs — CLI Tokens vs Orchestrator Internal Names
**Observation:** CLI uses colon-separated IDs (`draft:section`, `lint:bib`). Orchestrator internally uses underscore-separated names (`draft_section`, `lint_bib`). PIPELINE_MAP keys use colons.
**Assessment:** TRUE OVERLAP — two naming conventions for the same commands.
**Risk:** Confusion when mapping between CLI and Orchestrator. Agents may use wrong ID format.
**Mitigation:** `CommandSpec` has three identity fields: `id` (canonical, colon-separated), `dispatch_key` (PIPELINE_MAP key, colon-separated), `cli_path` (tuple of CLI tokens). Parity tests verify alignment.
**Action:** Document naming conventions. Use `id` (colon-separated) as canonical in all SDD artifacts.

### OV-4: Provider Selection — Config Files vs Runtime Detection
**Observation:** Provider selection (search, LLM, MCP) is configured via `.envrc`, `review_config.yaml`, and environment variables. Runtime detection (which providers are available) is not implemented in v1.
**Assessment:** PARTIAL OVERLAP — config defines intent, runtime would verify availability.
**Risk:** Config may reference unavailable providers. Preflight cannot detect this in v1.
**Mitigation:** `network_policy` on `CommandSpec` is descriptive only. `CapabilityResolver` (runtime detection) is deferred to v2.
**Action:** Document as v2 concern. Preflight warns about missing config but cannot verify runtime availability.

### OV-5: Gate Validation — validators/ vs rules/ vs gate validators
**Observation:** `validators/` contains Python validation logic. `rules/` contains YAML rule definitions. Gate validators in `harness/services/gates.py` coordinate validation.
**Assessment:** NOT a true overlap — correct separation of concerns. Rules are data, validators are code, gates coordinate.
**Action:** None needed. Document the relationship.

### OV-6: Search — clients/ vs integrations/tools/
**Observation:** `clients/` contains HTTP API clients (crossref, semantic_scholar, openalex, arxiv). `integrations/tools/` contains MCP-based search providers.
**Assessment:** Partial overlap. `clients/` are low-level HTTP wrappers; `integrations/tools/` are MCP/search providers.
**Action:** Document that `clients/` = HTTP API wrappers, `integrations/tools/` = MCP/search providers.

### OV-7: Zotero — clients/zotero.py vs integrations/tools/zotero_import.py vs integrations/tools/zotero_sync.py
**Observation:** Zotero functionality is split across three files with different responsibilities.
**Assessment:** NOT a true overlap — correct separation: `clients/zotero.py` = API client, `zotero_import.py` = BibTeX import wrapper, `zotero_sync.py` = API sync wrapper.
**Action:** None needed. Document the relationship.

### OV-8: State — harness/domain/state.py vs harness/services/state_manager.py
**Observation:** Both deal with ManuscriptState.
**Assessment:** NOT overlap — domain entity vs application service. StateManager coordinates domain with persistence.
**Action:** None needed.

### OV-9: Formatting — engine/formatter.py vs cli/paper/output.py
**Observation:** Both format output.
**Assessment:** NOT overlap — `engine/formatter.py` formats validation findings (JSON/terminal), `cli/paper/output.py` formats CLI results (text/JSON).
**Action:** None needed.

---

## Orphan Capabilities (Not Connected to Pipeline)

### OR-1: workflow_skill_creator
**Location:** `skills/local/workflow_skill_creator/` (9 agents, 84 Python files)
**Observation:** A complete skill creation system that is NOT integrated with the Paper Writer pipeline.
**Impact:** Low — it's a development tool, not a pipeline capability.
**Action:** Document as separate tool, not part of core pipeline.

### OR-2: science-bundle
**Location:** `skills/local/science-bundle/`
**Observation:** Not integrated with the pipeline.
**Impact:** Low — potential future integration point.
**Action:** Document as available but not integrated.

### OR-3: autoresearch/
**Location:** `autoresearch/` and `gemini-autoresearch/`
**Observation:** Research logs and external autoresearch skill.
**Impact:** Low — developer tooling.
**Action:** Document as research tooling.

### OR-4: benchmarks/
**Location:** `benchmarks/`
**Observation:** FAIR benchmark and trifecta integration bench.
**Impact:** Low — evaluation tooling.
**Action:** Document as evaluation tooling.

### OR-5: .gemini/settings.json
**Location:** `.gemini/settings.json`
**Observation:** Contains hardcoded local paths to MCP servers.
**Impact:** Low — provider-specific configuration.
**Action:** Document as provider-specific, not portable.

### OR-6: skill.md
**Location:** `skill.md`
**Observation:** Trifecta-specific agent harness asset with hardcoded path.
**Impact:** Low — outdated/stale.
**Action:** Flag as potentially obsolete.

### OR-7: Gemini autoresearch skill
**Location:** `.gemini/skills/autoresearch/`
**Observation:** External autoresearch skill vendored into the repo.
**Impact:** Low — external tool.
**Action:** Document as external, not core.

---

## Summary

| Category | Count | Action |
|----------|-------|--------|
| True overlaps (divergence risk) | 4 | Add parity tests, document intentional strictness |
| Perceived overlaps (correct separation) | 5 | Document relationships |
| Orphans | 7 | Document as non-core, flag stale items |
| Stale content | 1 (skill.md) | Flag for cleanup |

**Conclusion:** The repository has 4 true overlapping authorities that require parity tests to prevent divergence. COMMAND_REGISTRY is a transitory mirror in v1; full migration is a v2 concern. The orphans are either development tooling or provider-specific configurations that don't affect the core pipeline.
