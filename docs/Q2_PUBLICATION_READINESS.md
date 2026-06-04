# Q2 Publication Readiness Log — paper-writer

> Generated: 2026-06-03 | Last updated: 2026-06-04
> Status: **NOT READY** — 1/12 gaps resolved, 1 P0 partially resolved (1 P0 blocking remains, 4 P1, 5 P2)
> Target: Systematic review on retrieval-augmented code generation, Q2 journal

---

## Evidence Baseline — What Works Now

### Pipeline (verified 2026-06-04)

| Component | Status | Evidence |
|:---|:---|:---|
| State machine (7 stages) | ✅ | `harness/domain/state.py` — 886 tests pass |
| **CS scoring engine** | ✅ **NEW** | `skills/imported/literature_search/scoring_cs.py` — domain-aware dispatch, 9/14 arXiv papers Tier 3 |
| **LLM content generation** | ✅ **NEW** | `clients/llm_content.py` — subprocess wrapper for claude/codex/gemini |
| Gate system (12 validators) | ✅ | `harness/services/gates.py` — fail-closed, structured YAML logs |
| PRISMA checklist | ✅ | `rules/method_gate/prisma.yml` — 8 critical + 1 non-critical items |
| CONSORT + STROBE checklists | ✅ | `rules/method_gate/consort.yml`, `strobe.yml` |
| E2E CLI (12 commands) | ✅ | init→search→screen→draft→lint→check→audit→gate→render→verify |
| Per-run artifact isolation | ✅ | `outputs/runs/{run_id}/` + `outputs/latest/` symlink |
| Structured command logs | ✅ | YAML per command via `write_command_log()` |
| Trifecta code health | ✅ | 54 findings (orphans + coupling hotspots) |
| 100% API coverage | ✅ | 104/104 public symbols tested |
| mypy + ruff clean | ✅ | 0 errors across 60 source files |
| Render to docx/pdf | ✅ | `paper render --format docx/pdf` via pandoc |

### CS Scoring Engine (implemented 2026-06-04)

`skills/imported/literature_search/scoring_cs.py` — 5 dimensions, domain dispatch:

| Dimension | Range | Default | What it measures |
|:---|:---|:---|:---|
| `venue_tier` | 0-5 | 2.0 | ICSE/FSE=5.0, EMNLP/ACL=4.5, arXiv=2.0 |
| `recency_score` | 0-1 | 0.50 | Linear decay 0.10/yr, floor 0.20 |
| `citation_score` | 0-2 | 0.50 | Per-year normalization, None→0.50 |
| `relevance_score` | 0-2 | 1.0 | Keyword overlap query vs title+abstract |
| `rigor_score` | 0-1 | 0.40 | Human study=1.0, benchmark=0.8, case=0.5, theoretical=0.3 |

**Domain detection**: whole-word regex (`\bICSE\b` prevents "database" false positive). CS venue check happens before clinical keywords. Default: "cs".

**E2E result**: 14 arXiv papers → 9 Tier 3, 5 Discard. `screened_evidence.json`: 0→9 papers.

| Paper | Final Score | Tier |
|:---|:---|:---|
| CodeRAG-Bench (Wang et al.) | 5.8 | Tier 3 |
| SWE-bench (Jimenez et al.) | 5.5 | Tier 3 |
| RACG Survey (Tao et al.) | 5.2 | Tier 3 |
| EvoR (Su et al.) | 5.0 | Tier 3 |
| SWE-agent (Yang et al.) | 5.0 | Tier 3 |
| Reflexion | 5.0 | Tier 3 |
| Codex paper (Chen et al.) | 5.0 | Tier 3 |
| OpenCodeInterpreter | 5.0 | Tier 3 |
| RAG survey (Gao et al.) | 5.0 | Tier 3 |
| RepoCoder (Zhang et al.) | 4.8 | Discard |
| RepoFusion (Shrivastava et al.) | 4.8 | Discard |
| Magicoder | 4.8 | Discard |
| DocPrompting | 4.7 | Discard |
| RAG Code Summarization (Parvez) | 4.5 | Discard |

### Content Generation (proof of concept, 2026-06-03)

4 sections generated with `PAPER_LLM_CLI=claude`, 14 arXiv papers as evidence:

| Section | Words | Model | Quality |
|:---|:---|:---|:---|
| Introduction | 1,243 | CARS (Territory→Niche→Occupy) | Q2 — critical argumentation, no laundry list |
| Methods | 914 | PRISMA-compliant | Q2 — search strategy, eligibility, databases |
| Results | 1,627 | APA 7th reporting | Q2 — evidence synthesis |
| Discussion | 1,160 | Critical comparison | Q2 — comparison, limitations, recommendations |
| **Total** | **4,941** | | **34 in-text citations, 11 distinct authors** |

All citations verified against provided papers. No hallucinated references.

---

## Gap Analysis — What's Missing for Q2

### GAP-001: ~~Insufficient bibliography~~ (14 → 68 refs, target 40-80 MET)

| Field | Detail |
|:---|:---|
| **Severidad** | ~~🔴 Crítica~~ → ✅ RESOLVED |
| **Componente** | `skills/imported/literature_search/chaining.py`, `skills/local/adapters.py` |
| **Problema** | Systematic review Q2 expects 40-80 references. Current bib has 14 from single arXiv search. |
| **Root cause** | ~~(1) PICO scoring gives 0.0 for CS papers~~ **FIXED by GAP-003**. ~~(2) No iterative search~~ **FIXED by GAP-007**. |
| **Evidence** | GAP-007 chaining (autoresearch #282): 14 seeds → 74 after chain → 68 Tier 3+ after screen. Target 40-80 MET. |
| **Acceptance** | Pipeline delivers 68 Tier 3+ papers via search→chain→screen. DOI dedup + title fuzzy dedup prevent duplicates. |
| **Estado** | ✅ DONE — GAP-003 (CS scoring) + GAP-007 (chaining) resolved this gap |

### GAP-002: 3 sections never generated (abstract, literature_review, conclusion)

| Field | Detail |
|:---|:---|
| **Severidad** | 🔴 Crítica — P0 blocking |
| **Componente** | `cli/paper/main.py:105` (draft section subcommand), `skills/imported/academic_writer/drafting.py:94` (`draft_section()`) |
| **Problema** | Only 4 of 7 sections were generated in POC. Missing: abstract (order 1, 250-300 words), literature_review (order 3, 1000-1200 words), conclusion (order 7, 400-600 words). |
| **Root cause** | No `draft all` command exists. Each section requires manual `paper draft section <name>`. |
| **Solución** | (a) Add `draft all` subcommand that generates sections in order with cross-section context. (b) Each section passes `outline_context` from previous sections. (c) Abstract generated last with all 6 sections as context. |
| **Acceptance** | `paper draft all` generates 7 section files. `paper gate method` on combined manuscript shows 0 blockers for PRISMA study type. |
| **Esfuerzo** | 1 día |
| **Estado** | 🟡 Unblocked — evidence set is now non-empty (9 papers) |

### ~~GAP-003: PICO scoring engine incompatible with Computer Science~~

| Field | Detail |
|:---|:---|
| **Severidad** | ✅ **RESOLVED** |
| **Solución aplicada** | Created `scoring_cs.py` with `CSMetrics` (5 dimensions), domain detection via whole-word regex, weight presets (balanced/rigorous/exploratory). Integrated into `search.py` with backward-compatible `_extract_metrics()` dispatch. 68 new tests, 886 total passing, 0 regressions. |
| **Evidence** | 14 arXiv papers: 9 Tier 3, 5 Discard. `screened_evidence.json` went from 0→9 papers. |
| **SDD artifacts** | `openspec/changes/gap-003-cs-scoring/` — proposal, spec, design, tasks. Judgment Day Round 1: 2 CRITICAL + 6 WARNING found and fixed. Round 2: APPROVED. |
| **Estado** | ✅ Resuelto |

### GAP-004: No tables or figures generated

| Field | Detail |
|:---|:---|
| **Severidad** | 🟠 Alta — P1 |
| **Componente** | `clients/llm_content.py` (`generate_section()`), `skills/imported/academic_writer/drafting.py` |
| **Problema** | LLM generates prose only. Q2 systematic review expects: Table 1 (study characteristics), Table 2 (comparison of RAG approaches), Figure 1 (PRISMA flow diagram). |
| **Root cause** | `generate_section()` at `llm_content.py:226` sends text-only prompt. No instruction for markdown tables or mermaid diagrams. |
| **Solución** | (a) Add table generation instruction to section prompts. (b) Add mermaid diagram instruction for PRISMA flow. (c) Post-process LLM output to validate tables. |
| **Acceptance** | Draft output contains ≥1 markdown table with study comparisons. |
| **Esfuerzo** | 1 día |
| **Estado** | ❌ Pendiente |

### GAP-005: ~~Citation format mismatch~~ (Author, Year → @key converter DONE)

| Field | Detail |
|:---|:---|
| **Severidad** | ~~🟠 Alta~~ → ✅ RESOLVED |
| **Componente** | `validators/citation_format.py` |
| **Problema** | LLM generates `(Tao et al., 2025)` but pandoc expects `@tao2025racg` for bibTeX resolution. |
| **Solución** | `convert_citations(text, bib)` parses .bib, builds author+year → key index, replaces inline citations. |
| **Acceptance** | `audit_citation_format()` reports resolved/unresolved. 4/6 test citations resolved. |
| **Estado** | ✅ DONE — `validators/citation_format.py` with parse, index, convert, audit |

### GAP-006: ~~No quality appraisal~~ (QualityAppraisalValidator DONE)

| Field | Detail |
|:---|:---|
| **Severidad** | ~~🟠 Alta~~ → ✅ RESOLVED |
| **Componente** | `validators/quality_appraisal.py` |
| **Problema** | PRISMA `prisma.13` checks for "risk of bias" keywords but no quality appraisal module exists. |
| **Solución** | 5-dimension scoring: venue reputation, citation impact, methodology rigor, reproducibility, recency. Weighted total → quality rating. |
| **Acceptance** | Generates appraisal table JSON with high/moderate/low/very_low ratings. 23 unit tests. |
| **Estado** | ✅ DONE — `validators/quality_appraisal.py` with QualityAppraisalValidator |

### GAP-007: ~~No iterative search mechanism~~ (DONE)

| Field | Detail |
|:---|:---|
| **Severidad** | ~~🟡 Media~~ → ✅ RESOLVED |
| **Estado** | ✅ DONE — `chaining.py` with backward/forward chaining, adaptive threshold, DOI+title dedup |

| Field | Detail |
|:---|:---|
| **Severidad** | 🟡 Media — P2 (but needed for GAP-001) |
| **Componente** | `skills/imported/literature_search/search.py`, Semantic Scholar API |
| **Problema** | `search()` is one-shot. No backward/forward citation chaining. Systematic review requires iterative search until saturation. |
| **Solución** | Add `chaining.py` using Semantic Scholar API. Iterative loop: seed → expand → score → repeat until saturation. |
| **Acceptance** | From 14 seed papers, iterative search finds ≥40 unique relevant papers. |
| **Esfuerzo** | 2-3 días |
| **Estado** | ❌ Pendiente — next P0 priority |

### GAP-008: Sections generated without cross-section awareness

| Field | Detail |
|:---|:---|
| **Severidad** | 🟡 Media — P1 |
| **Componente** | `skills/imported/academic_writer/drafting.py` (`_try_llm_generation()`) |
| **Problema** | Each section generated independently. `outline_context` always empty. Discussion may cite findings not in Results. |
| **Solución** | Generate sections in dependency order. Pass previous sections as context. Abstract generated last with all sections. |
| **Acceptance** | Discussion references only findings present in Results. |
| **Esfuerzo** | Medio día |
| **Estado** | ❌ Pendiente |

### GAP-009: No factual accuracy verification against evidence

| Field | Detail |
|:---|:---|
| **Severidad** | 🟡 Media-Alta — P2 |
| **Componente** | `validators/claim_alignment.py`, `validators/citation_verify.py` |
| **Problema** | LLM may hallucinate findings. `ClaimAlignmentValidator` only checks citation existence, not content accuracy. |
| **Solución** | Extend `ClaimAlignmentValidator` with keyword overlap heuristic. Flag claims with <30% overlap for human review. |
| **Acceptance** | `paper audit claims` flags hallucinated claims. False positive rate < 20%. |
| **Esfuerzo** | 2 días |
| **Estado** | ❌ Pendiente |

### GAP-010: No journal-specific LaTeX template

| Field | Detail |
|:---|:---|
| **Severidad** | 🟡 Media — P2 |
| **Componente** | `templates/journals/` (only Nature preset) |
| **Problema** | For Q2 SE journals (Empirical SE, JSS, IST) need Springer/Elsevier templates. |
| **Solución** | Add Springer (`sn-jnl.cls`) and Elsevier (`elsarticle.cls`) templates. |
| **Acceptance** | `paper init --preset springer` scaffolds correct template. |
| **Esfuerzo** | Medio día |
| **Estado** | ❌ Pendiente |

### GAP-011: No PRISMA flow diagram generated

| Field | Detail |
|:---|:---|
| **Severidad** | 🟡 Media — P2 |
| **Componente** | `search.py:screen()`, PRISMA gate `prisma.16` |
| **Problema** | `screen()` records `total_raw` and `total_screened` but doesn't emit 4-stage PRISMA counts. |
| **Solución** | Extend `screen()` to emit PRISMA counts. Generate mermaid flow diagram. |
| **Acceptance** | `paper screen` writes `prisma_flow.json`. Gate `prisma.16` passes. |
| **Esfuerzo** | Medio día |
| **Estado** | ❌ Pendiente |

### GAP-012: No reproducibility protocol document

| Field | Detail |
|:---|:---|
| **Severidad** | 🟢 Baja-Media — P2 |
| **Componente** | Command logs, state machine |
| **Problema** | No command generates protocol summary for reviewers. Search strings, decisions scattered across files. |
| **Solución** | Add `paper protocol` command that aggregates all pipeline metadata. |
| **Acceptance** | `paper protocol > protocol.md` produces complete document. |
| **Esfuerzo** | Medio día |
| **Estado** | ❌ Pendiente |

---

## Dependency Graph

```
GAP-003 (CS scoring) ──✅ DONE──→ GAP-001 (bibliography) ──blocks──→ GAP-002 (sections)
                                         │
                                         └──→ GAP-007 (iterative search) ←─ NOW P0

GAP-002 (all sections) ──→ GAP-008 (cross-section coherence)
GAP-002 (all sections) ──→ GAP-005 (citation mapping)
GAP-002 (all sections) ──→ GAP-004 (tables/figures)
GAP-001 (bibliography) ──→ GAP-006 (quality appraisal needs ≥40 papers)
GAP-006 (quality appraisal) ──→ GAP-011 (PRISMA flow needs screening data)

Independent: GAP-009 (fact-check), GAP-010 (journal template), GAP-012 (protocol)
```

## Execution Order

| Phase | GAPs | Esfuerzo | Status |
|:---|:---|:---|:---|
| **Phase 1** | GAP-003 (CS scoring) | 1 day | ✅ Done |
| **Phase 2** | GAP-007 (iterative search) → GAP-001 (bib 50+ refs) | 2-3 days | 🟡 Unblocked |
| **Phase 3** | GAP-002 (draft all 7 sections) + GAP-008 (cross-section) | 1.5 days | 🟡 Unblocked |
| **Phase 4** | GAP-004 (tables) + GAP-005 (citation fix) + GAP-006 (quality appraisal) + GAP-011 (PRISMA) | 3 days | ❌ Pending |
| **Phase 5** | GAP-009 (fact-check) + GAP-010 (journal template) + GAP-012 (protocol) | 3 days | ❌ Pending |

**Total remaining effort: 9-11 days**

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|:---|:---|:---|:---|
| LLM hallucinates findings despite prompt instructions | High | High | GAP-009 fact-checking. Always verify against abstracts |
| Semantic Scholar API rate-limited or down | Medium | Medium | Cache results locally. Fallback to Crossref API |
| ~~CS scoring classifies too many papers as Discard~~ | ~~Medium~~ | ~~Medium~~ | **Mitigated**: 9/14 score Tier 3 with adjusted weights |
| Cross-section coherence still inconsistent after GAP-008 | Low | High | Manual editorial pass. Add consistency validator |
| Journal template doesn't match exact submission format | Low | Low | Templates are starting points. Author adjusts before submission |

## Evidence Trail

### 2026-06-04 — GAP-003 CS Scoring Engine Implemented

**SDD Lifecycle**: proposal → spec → design → tasks → apply → verify
**Judgment Day**: Round 1 found 2 CRITICAL + 6 WARNING → all fixed → Round 2 APPROVED

**Implementation**:
- `skills/imported/literature_search/scoring_cs.py` — NEW, ~350 lines
- `skills/imported/literature_search/search.py` — modified `_extract_metrics()` (domain dispatch), `search()` (CS routing), `screen()` (fallback fix)
- `tests/skills/test_scoring_cs.py` — NEW, 68 tests
- `clients/llm_content.py` — NEW, LLM subprocess client
- `skills/imported/academic_writer/drafting.py` — modified `_try_llm_generation()` (LLM opt-in)

**Tests**: 886 passed, 2 pre-existing failures (pandoc/pdflatex), 0 regressions
**E2E**: 14 arXiv papers → 9 Tier 3, screened_evidence 0→9

### 2026-06-03 — LLM Content Generation Proof of Concept

4 sections generated with `PAPER_LLM_CLI=claude`, 14 arXiv papers as evidence:

- Introduction: 1,243 words, CARS model, 11 citations, 9 paragraphs
- Methods: 914 words, PRISMA-compliant
- Results: 1,627 words, evidence synthesis
- Discussion: 1,160 words, critical comparison
- **Total**: 4,941 words, 34 in-text citations from 11 distinct authors

**Quality assessment**: No hallucinated references. CARS structure correct. Academic tone.
