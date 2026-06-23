# Roadmap Coverage Matrix: Paper Writer Repository

**Date:** 2026-06-19
**Status:** Complete exploration, no code changes

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| `code` | Module exists and runs |
| `tests` | Dedicated unit/integration tests |
| `docs` | Documented in docs/ or SKILL.md |
| `CI` | Covered by CI pipeline |
| `prod` | Production-ready (all above + edge cases handled) |
| `—` | Not applicable or not tracked |

---

## Phase 1: Core Workflow

| Capability | code | tests | docs | CI | prod | Notes |
|-----------|------|-------|------|-----|------|-------|
| State machine (ManuscriptState) | ✅ | ✅ | ✅ | ✅ | ✅ | 8 stages, 15 gates, forward-only |
| Orchestrator (3-phase) | ✅ | ✅ | ✅ | ✅ | ✅ | 696 lines, prepare→apply→verify |
| Gate system (fail-closed) | ✅ | ✅ | ✅ | ✅ | ✅ | 461 lines, 13 hard + 2 soft |
| CLI entry point | ✅ | ✅ | ✅ | ✅ | ✅ | 27+ commands, 6 exit codes |
| Atomic persistence | ✅ | ✅ | ✅ | ✅ | ✅ | yaml_repository.py, atomic writes |
| Run lineage | ✅ | ✅ | ✅ | ✅ | ✅ | outputs/runs/{run_id}/, run.yaml |

**Phase 1 status: 6/6 production-ready**

---

## Phase 2: Research Capability

| Capability | code | tests | docs | CI | prod | Notes |
|-----------|------|-------|------|-----|------|-------|
| Search providers (4) | ✅ | ✅ | ✅ | ✅ | ✅ | fixture, mcp, consensus, consensus_mcp_remote |
| HTTP clients (9) | ✅ | 🟡 | 🟡 | ✅ | 🟡 | crossref, s2, openalex, arxiv, zotero, trifecta, llm_content, _text_similarity, _retry |
| MCP clients (3) | ✅ | 🟡 | 🟡 | ✅ | 🟡 | ConsensusClient, ConsensusMcpClient, McpPaperSearchProvider |
| Literature search skill | ✅ | ✅ | ✅ | ✅ | ✅ | scoring.py 589 lines, chaining |
| Academic writer skill | ✅ | ✅ | ✅ | ✅ | ✅ | Imported adapter |
| Screening and chaining | ✅ | ✅ | ✅ | ✅ | ✅ | Multi-stage relevance scoring |

**Phase 2 status: 4/6 production-ready, 2 partial**

---

## Phase 3: Document Integrity

| Capability | code | tests | docs | CI | prod | Notes |
|-----------|------|-------|------|-----|------|-------|
| Validators (23) | ✅ | ✅ | 🟡 | ✅ | 🟡 | Most tested, docs scattered |
| Rules (6 modules, 24 YAML) | ✅ | ✅ | 🟡 | ✅ | 🟡 | Declarative, some lack tests |
| Tool wrappers (14) | ✅ | 🟡 | 🟡 | ✅ | 🟡 | Pandoc/Vale prod-ready, inline vary |
| Manuscript parser | ✅ | ✅ | ✅ | ✅ | ✅ | .md/.tex/.txt support |
| Source map | ✅ | ✅ | ✅ | ✅ | ✅ | Citation provenance |
| Deduplication engine | ✅ | ✅ | 🟡 | ✅ | 🟡 | DOI, PMID, title similarity |
| Formatting engine | ✅ | 🟡 | 🟡 | ✅ | 🟡 | Terminal/claims/gate formatting |
| CSL styles (2) | ✅ | — | ✅ | — | ✅ | vancouver.csl, apa.csl |
| Vale rules | ✅ | — | ✅ | — | ✅ | .vale.ini + paper-writer pack |
| Journal presets (3) | ✅ | ✅ | ✅ | ✅ | ✅ | Nature, Elsevier, Springer |

**Phase 3 status: 5/10 production-ready, 5 partial**

---

## Phase 4: Agent Integration

| Capability | code | tests | docs | CI | prod | Notes |
|-----------|------|-------|------|-----|------|-------|
| MCP server | 🔲 | — | 🟡 | — | 🔲 | Planned in capability-ledger |
| Preflight resolver | 🔲 | — | ✅ | — | 🔲 | Spec/design/tasks complete |
| Agent prompts | 🔲 | — | 🔲 | — | 🔲 | Not started |
| Capability registry | 🔲 | — | 🟡 | — | 🔲 | Static registry planned |

**Phase 4 status: 0/4 implemented, 2 have specs**

---

## Phase 5: Engineering Maturity

| Capability | code | tests | docs | CI | prod | Notes |
|-----------|------|-------|------|-----|------|-------|
| CI pipeline | ✅ | — | ✅ | ✅ | ✅ | 7-job pipeline, 3 Python versions |
| Security scanning | ✅ | — | ✅ | ✅ | ✅ | pip-audit, CodeQL, dependency-review |
| Release workflow | ✅ | — | ✅ | ✅ | ✅ | Tag-based, wheel verification |
| Real-material validation | ✅ | ✅ | ✅ | ✅ | ✅ | verification/ runner |
| Benchmarks | ✅ | 🟡 | 🟡 | 🟡 | 🟡 | FAIR + Trifecta, not in CI |
| Documentation | 🟡 | — | 🟡 | — | 🟡 | Some sections complete, some stale |

**Phase 5 status: 4/6 production-ready, 2 partial**

---

## Phase 6: Production Readiness

| Capability | code | tests | docs | CI | prod | Notes |
|-----------|------|-------|------|-----|------|-------|
| MCP server | 🔲 | — | 🟡 | — | 🔲 | Overlaps with Phase 4 |
| Multi-user support | 🔲 | — | 🔲 | — | 🔲 | Not started |
| Plugin system | 🔲 | — | 🔲 | — | 🔲 | Not started |
| API endpoints | 🔲 | — | 🔲 | — | 🔲 | Not started |

**Phase 6 status: 0/4 implemented**

---

## Summary by Phase

| Phase | Total | prod | partial | planned | Coverage |
|-------|-------|------|---------|---------|----------|
| Phase 1: Core Workflow | 6 | 6 | 0 | 0 | **100%** prod |
| Phase 2: Research | 6 | 4 | 2 | 0 | **67%** prod |
| Phase 3: Document Integrity | 10 | 5 | 5 | 0 | **50%** prod |
| Phase 4: Agent Integration | 4 | 0 | 0 | 4 | **0%** (2 have specs) |
| Phase 5: Engineering Maturity | 6 | 4 | 2 | 0 | **67%** prod |
| Phase 6: Production Readiness | 4 | 0 | 0 | 4 | **0%** |
| **Total** | **36** | **19** | **9** | **8** | **53%** prod |

**Production-ready: 53% | Partially ready: 25% | Planned/not started: 22%**

---

## Capability-Level Detail

### Capabilities at `prod` (19)

1. State machine (ManuscriptState)
2. Orchestrator (3-phase)
3. Gate system (fail-closed)
4. CLI entry point
5. Atomic persistence
6. Run lineage
7. Search providers (4)
8. Literature search skill
9. Academic writer skill
10. Screening and chaining
11. Manuscript parser
12. Source map
13. CSL styles (2)
14. Vale rules
15. Journal presets (3)
16. CI pipeline
17. Security scanning
18. Release workflow
19. Real-material validation

### Capabilities at `partial` (9)

1. HTTP clients (9) — some lack tests
2. MCP clients (3) — some lack tests
3. Validators (23) — docs scattered
4. Rules (6 modules) — some lack tests
5. Tool wrappers (14) — Pandoc/Vale prod, inline vary
6. Deduplication engine — docs incomplete
7. Formatting engine — tests sparse
8. Benchmarks — not in CI
9. Documentation — some sections stale

### Capabilities at `planned` (8)

1. MCP server (Phase 4)
2. Preflight resolver (has spec)
3. Agent prompts
4. Capability registry (has spec)
5. MCP server (Phase 6, overlap)
6. Multi-user support
7. Plugin system
8. API endpoints

---

## Sprint Priorities (Reconciled)

### Sprint: core-preflight (Next)
**Goal:** Preflight resolver + CommandRegistry + CLI command
**Capabilities:** preflight resolver (has spec), CommandRegistry (has design)
**Files:** ~4 new, ~4 modified
**Risk:** Low
**Blocks:** MCP server, agent integration

### Sprint: research-hardening
**Goal:** Harden research capabilities for production
**Capabilities:** HTTP client tests, MCP client tests, client resilience
**Files:** clients/, integrations/tools/
**Risk:** Medium

### Sprint: docs-completeness
**Goal:** Complete documentation and validator coverage
**Capabilities:** validator docs, rule docs, tool wrapper docs
**Files:** docs/, validators/, rules/
**Risk:** Low

### Sprint: mcp-server
**Goal:** MCP server for agent integration
**Capabilities:** MCP server, agent prompts, capability registry
**Files:** New MCP server, prompts/, harness/services/
**Risk:** High
**Depends:** core-preflight

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Total tests | ~1903 |
| Total validators | 23 |
| Total tool wrappers | 15 |
| Total HTTP clients | 9 |
| Total MCP clients | 3 |
| Total search providers | 4 |
| Total CLI commands | 27+ |
| Total gates | 15 (13 hard + 2 soft) |
| Total stages | 8 |
| Total journal presets | 3 |
| Total CSL styles | 2 |
| Total rule modules | 6 |
| Total YAML rules | 24 |
| Total local skills | 6 |
| Total imported skills | 2 |
| Total subprojects | 3 |

---

## Recommendations

1. **Immediate:** Implement preflight resolver (core-preflight sprint) — spec already complete
2. **Short-term:** Harden HTTP/MCP clients with tests, complete validator docs
3. **Medium-term:** MCP server implementation, agent integration
4. **Long-term:** Production readiness (multi-user, plugins, API)

---

## Appendix: Capability Ledger Reference

The full capability ledger is at `changes/paper-core-preflight/capability-ledger.yaml` with 60+ entries across all layers.
