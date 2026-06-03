# Document Governance

> **Purpose**: Classify every document in `docs/` so contributors know
> which docs reflect runtime behavior (must update with code) vs design
> intent (aspirational) vs historical records (frozen snapshots).

## Classification Legend

| Tag | Meaning | Update Rule |
|-----|---------|-------------|
| `source-of-truth` | Reflects current runtime behavior | MUST update when code changes |
| `design-intent` | Aspirational or planned, may diverge from implementation | Update when plan changes; note divergence |
| `historical` | Frozen snapshot of past state or decisions | Never edit — add new doc if superseded |

## Registry

### Source of Truth (update with code changes)

| Document | Scope |
|----------|-------|
| `HARNESS_AND_STATE_MACHINE.md` | Orchestrator stages, gates, transitions |
| `ORCHESTRATOR_SPEC.md` | Orchestrator contract and API |
| `GATE_SYSTEM.md` | Gate validators and semantics |
| `REPO_ARCHITECTURE.md` | File structure, module responsibilities |
| `PRODUCTION_READINESS.md` | Deployment requirements, degraded mode |
| `SKILL_ADAPTERS_SPEC.md` | Skill adapter contract |
| `SKILLS_VENDORING.md` | Skill vendoring process |
| `TESTING_STRATEGY.md` | Test structure and coverage expectations |
| `ENVIRONMENT_AND_INSTALL.md` | Setup instructions |
| `tools/paper-cli.md` | CLI commands and options |
| `tools/pandoc.md` | Pandoc integration |
| `tools/refchecker.md` | Reference checking |
| `tools/reference-validator.md` | Reference validator |
| `tools/README.md` | Tool index |
| `MANIFEST_SPEC.md` | Manifest schema (schema_version, fields) |
| `trifecta-extension-guide.md` | Trifecta extension API |
| `trifecta-mcp-agent-guide.md` | Trifecta MCP agent patterns |
| `flujo_falp.md` | FALP pipeline flow |
| `STATE_MANAGER_SPEC.md` | State manager contract |
| `VALIDATOR_CONTRACTS.md` | Validator output contracts |
| `tools/bibtex-tidy.md` | Bibtex-tidy integration |
| `tools/vale.md` | Vale style checker integration |

### Design Intent (aspirational, may diverge from implementation)

| Document | Scope |
|----------|-------|
| `MULTI_PROJECT_SPEC.md` | Multi-project mode (partially implemented) |
| `ARS-PORTING-OPPORTUNITIES.md` | Potential ARS integrations |
| `AUDIT_CHECKLIST_001.md` | Audit checklist template |
| `plans/plan-extract-cli-wiring-builder.prompt.md` | CLI extraction plan |
| `plans/plan-phase-2-mcp-client.prompt.md` | Phase 2 MCP client plan |
| `research/phase-0-fix-plan.md` | Phase 0 fix strategy |
| `research/phase-1-plan.md` | Phase 1 research plan |
| `integration/TRIFECTA_NEXT_STEPS.md` | Trifecta integration roadmap |
| `plans/tool-resolver-tasks.md` | Tool resolver task breakdown |
| `orphan-detection-use-cases.md` | Orphan detection use cases |

### Historical (frozen snapshots, never edit)

| Document | Scope |
|----------|-------|
| `CODE_ISSUES_LOG.md` | Issues log (append-only) |
| `ab-test-results.md` | A/B benchmark results |
| `benchmarks/TRIFECTA-BENCHMARK-SPEC-v0.1.md` | Benchmark spec v0.1 |
| `graph-audit-findings.md` | Graph audit findings snapshot |
| `integration/trifecta-bench-results.md` | Benchmark results snapshot |
| `research/paso-0-baseline-results.md` | Phase 0 baseline |
| `research/phase-0-prior-art.md` | Prior art review |
| `research/dynamic-graph-maproad.md` | Dynamic graph research |
| `research/mcp-tools-candidates.md` | MCP tool candidates review |
| `research/robin-era-mcp-audit.md` | Robin-era MCP audit |
| `trifecta-test-results.md` | Trifecta test results snapshot |
| `PHASE_LEDGER.md` | Phase completion ledger (append-only) |
