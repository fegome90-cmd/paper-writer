# Core Boundary Decisions: Paper Writer Repository

**Date:** 2026-06-19
**Status:** Reconciled with SDD artifacts (pass 7)
**Supersedes:** Previous version describing discarded architecture

---

## Decision 1: What is "Core" vs "Integration" vs "Platform"?

### Core (harness/, parsers/, engine/)
**Definition:** Domain logic, state management, workflow orchestration, document processing.
**Criteria:**
- Has no external dependencies (or uses only stdlib)
- Can be tested in isolation
- Would break the pipeline if removed
- Contains business rules

**Included:**
- ManuscriptState (domain entity)
- Orchestrator (workflow engine)
- StateManager (state coordination)
- Gate validators (gate logic)
- ActionRunner port (command execution)
- ArtifactChecker port (file existence)
- StateRepository port (persistence)
- ToolWrapper port (tool abstraction)
- SkillAdapter port (skill abstraction)
- PaperSearchProvider port (search abstraction)
- ManuscriptParser, SourceMap (document parsing)
- Deduplicator, Formatter, Loader (data processing)
- assembler, verify_artifacts, review_config, doctor (services)
- **CommandSpec + COMMAND_REGISTRY** (new — policy mirror for preflight)
- **PreflightResult + resolve_preflight()** (new — read-only resolver)

### Integration (integrations/tools/, clients/, skills/)
**Definition:** External tool wrappers, API clients, skill adapters.
**Criteria:**
- Depends on external tools or APIs
- Can be swapped without changing core
- Has fallback behavior for missing tools

**Included:**
- 15 tool wrappers (pandoc, vale, bibtex-tidy, refs, reporting, ethics, prose, claims, citations, writing_quality, code_health, zotero_import, zotero_sync)
- 9 HTTP clients (crossref, semantic_scholar, openalex, arxiv, zotero, trifecta, llm_content, _text_similarity, _retry)
- 3 MCP clients (paper, consensus, trifecta)
- 2 skill adapters (LiteratureSearchAdapter, AcademicWriterAdapter)
- Imported skills (literature_search, academic_writer)
- Local skills (thesaurus, mesh-import, trifecta-mcp, science-bundle, essay_crafter, workflow_skill_creator)

### Platform (verification/, benchmarks/, .github/workflows/)
**Definition:** Developer tooling, CI/CD, evaluation.
**Criteria:**
- Not part of the runtime pipeline
- Used for development, testing, or evaluation
- Can be removed without affecting functionality

**Included:**
- Real-material validation (verification/)
- FAIR benchmark (benchmarks/)
- CI pipeline (.github/workflows/)
- Security scanning
- Release workflow

---

## Decision 2: Where Does Preflight Belong?

**Answer:** Core (harness/services/preflight.py)

**Rationale:**
- Preflight is a **read-only resolver** (NOT a pure function — has I/O)
- No external dependencies (reads files, not APIs)
- Can be tested in isolation
- Would be used by CLI, agents, and future MCP server
- Follows the same pattern as gates.py (read-only evaluation)

**What preflight IS:**
- Read-only resolver that reads existing state and computes a view
- Deterministic for a given snapshot
- No side effects, no state mutations
- Uses `COMMAND_REGISTRY` (core-layer policy mirror) for command metadata

**What preflight is NOT:**
- NOT a pure function (has I/O: reads state.yaml, review_config.yaml)
- NOT reading `run.yaml` (v1 concern — deferred to v2)
- NOT reading `PIPELINE_MAP` from CLI layer (uses `COMMAND_REGISTRY` from core layer)
- NOT re-executing gate validators (reads gate values from state.yaml)
- NOT consuming `capability-ledger.yaml` at runtime (documentation only)

**Boundary:**
- Reads: `state.yaml`, `review_config.yaml`, `COMMAND_REGISTRY` (in-memory dict)
- Writes: nothing (read-only)
- Depends on: `ManuscriptState`, `StateManager`, `ReviewConfigSnapshot`, `CommandSpec`
- Does NOT depend on: `ActionRunner`, `ToolWrapper`, `SkillAdapter`, any client, `PIPELINE_MAP`

---

## Decision 3: Where Does the Capability Registry Belong?

**Answer:** Core (harness/domain/command_spec.py) for runtime, design-time only (capability-ledger.yaml) for documentation

**Rationale:**
- `COMMAND_REGISTRY` is the runtime registry (in-memory dict of `CommandSpec` objects)
- `capability-ledger.yaml` is a design artifact (documentation, not consumed at runtime)
- `CapabilityResolver` (runtime tool availability checks) is deferred to v2

**Boundary:**
- `COMMAND_REGISTRY`: Core-layer dict, consumed by preflight and parity tests
- `capability-ledger.yaml`: Documentation only, not consumed at runtime
- `CapabilityResolver`: v2 concern (would query `ToolWrapper.is_available()`)

---

## Decision 4: What is the Canonical Section Order?

**Answer:** Abstract → Introduction → Literature Review → Methods → Results → Discussion → Conclusion

**Source:** `harness/services/assembler.py` line 26

**Implications:**
- Journal presets must map their required_sections to this order
- Draft commands produce sections in this order
- Assembler concatenates in this order
- Validators expect this order

---

## Decision 5: What are the Hard Boundaries?

### Hard Boundary 1: State Mutations Go Through StateManager
- Never modify `ManuscriptState` directly
- Always use `StateManager.set_gate()`, `set_stage()`, `reset_downstream_gates()`
- Ensures atomic persistence and consistency

### Hard Boundary 2: Tool Execution Goes Through ToolWrapper
- Never call external tools directly from validators
- Always use `ToolWrapper.run()` which returns `ValidatorResult`
- Ensures consistent error handling and availability checks

### Hard Boundary 3: CLI Output Goes Through output.py
- Never print directly from handlers
- Always use `emit_result()`, `emit_json()`, `emit_info()`, `emit_warning()`, `emit_error()`
- Ensures consistent text/JSON output

### Hard Boundary 4: Artifact Paths Use Run Lineage
- Never hardcode artifact paths
- Always use `ActionRunner._resolve_run()` or `_resolve()`
- Ensures artifacts are correctly located per run

### Hard Boundary 5: Gate Verification is Fail-Closed
- If a wrapper is not registered, the gate fails
- If a tool is not available, the gate fails
- No silent fallbacks for missing capabilities

### Hard Boundary 6: CLI Layer Does NOT Import Core (and Vice Versa for CLI-specific code)
- Core (`harness/`) never imports from CLI (`cli/`)
- CLI imports from core, not the reverse
- `COMMAND_REGISTRY` lives in core layer; `PIPELINE_MAP` lives in CLI layer
- Preflight uses `COMMAND_REGISTRY`, not `PIPELINE_MAP`

---

## Decision 6: What is NOT Core?

### NOT Core: Agent Integration
- MCP server (planned, not implemented)
- Agent prompts and instructions
- Provider-specific configurations (.gemini/, .claude/, .kilo/)

### NOT Core: External Skills
- workflow_skill_creator (standalone tool)
- science-bundle (not integrated)
- autoresearch (research tooling)

### NOT Core: Benchmarks and Evaluation
- FAIR benchmark
- Trifecta integration bench
- Autoresearch experiments

### NOT Core: Documentation
- docs/ (developer documentation)
- AGENTS.md, CLAUDE.md (agent instructions)
- README.md (user documentation)

---

## Summary

| Boundary | Rule | Enforcement |
|----------|------|-------------|
| State mutations | Through StateManager only | Code review, tests |
| Tool execution | Through ToolWrapper only | Code review, tests |
| CLI output | Through output.py only | Code review, tests |
| Artifact paths | Through run lineage | Code review, tests |
| Gate verification | Fail-closed | Tests, CI |
| Core vs Integration | Ports define boundary | Architecture |
| Core vs Platform | Runtime vs developer tooling | Documentation |
| CLI vs Core | CLI imports core, not reverse | Architecture, parity tests |
| Preflight reads | COMMAND_REGISTRY, not PIPELINE_MAP | Architecture, tests |
