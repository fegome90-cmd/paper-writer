# ARS Diff — Skill Recommendations for Continued Exploration

## Summary

After 7 experiments exploring the ARS vs paper-writer diff, these are the skills
that provide the most value for continued exploration, ranked by gap coverage.

## Skills Ranked by Gap Coverage

### 1. `cli-explorer` — 4 gaps unlocked

Quick `rg`/`fd` patterns across both codebases. Best for pattern-matching gaps.

| Gap | Exploration Command | What You'll Find |
|-----|-------------------|------------------|
| contamination_signals | `rg "venue\|preprint\|contamination" validators/` | Zero hits — no venue-based quality signals in any validator |
| uncited_assertion_detector | `rg "ref:.*slug\|citation_marker\|<!--ref:" parsers/` | Zero hits — no per-sentence citation marker detection |
| claim_audit_constants | `rg "RE_NUMERIC_QUANTIFIER\|RE_REF_MARKER" .` | Zero hits — no shared claim audit patterns |
| claim_audit_pipeline | `rg "step_[1-6]\|phase_[1-9]" validators/` | Zero hits — no phased validation pipeline |

### 2. `context7` — 3 gaps unlocked

Fetches current API documentation for libraries and services.

| Gap | Query | What You'll Get |
|-----|-------|-----------------|
| arxiv_client | `context7 "arXiv API python"` | Atom 1.0 XML feed spec, id_list/search_query endpoints |
| openalex_client | `context7 "pyalex openalex python client"` | REST JSON endpoints, filter syntax, pagination |
| policy_anchor_disclosure | `context7 "Nature AI disclosure policy"` | Current journal AI disclosure requirements |

### 3. `codebase-explorer` — 3 gaps unlocked

Systematic exploration of codebase structure.

| Gap | Target | What You'll Find |
|-----|--------|------------------|
| audit_snapshot | Our `parsers/` + `validators/` | No SHA-256 hashing, no mutation detection anywhere |
| obsidian adapter | Our `integrations/tools/` | Only ZoteroImporter — no vault/directory ingestion |
| folder_scan adapter | Our `skills/imported/literature_search/` | Search queries S2 API, no local file ingestion |

### 4. `authority-flow-audit` — 2 gaps unlocked

Traces authority and gate decision flows.

| Gap | Target | What You'll Find |
|-----|--------|------------------|
| claim_audit_finalizer | Our `harness/services/gates.py` | Boolean gates (pass/fail) — no tiered severity |
| verification_gate | Our Orchestrator + StateManager | Simple gate check, no 4-resolver triangulation |

### 5. `code-path-cartographer` — 1 gap unlocked

Maps code connectivity and entrypoint reachability.

| Gap | Target | What You'll Find |
|-----|--------|------------------|
| claim_audit_pipeline | Our `validators/claims.py` → ToolWrapper → Orchestrator | 2-step flow vs ARS 6-step pipeline |

### 6. `sdd-explore` — 1 gap unlocked

Design investigation for potential features.

| Gap | Target | What You'll Investigate |
|-----|--------|----------------------|
| citation_verification_summary | Our `validators/citation_verify.py` output shape | How to add aggregated 3-class verdict reduction |

### 7. `librarian` — Cross-cutting utility

Caches ARS repo permanently for ongoing comparison.

```bash
# One-time setup — then ARS always available at ~/.cache/checkouts/
librarian cache Imbad0202/academic-research-skills
```

---

## Exploration Priority (Skills to Use Next Session)

### Phase 1: Understand what we're missing (1-2 hours)

Use `cli-explorer` for the 4 pattern-matching gaps. These are fast and reveal
whether our existing code has any partial coverage:

```bash
# 1. Check for any venue/preprint awareness
rg "venue\|preprint\|arxiv\|biorxiv\|medrxiv" validators/ clients/ skills/

# 2. Check for citation marker detection
rg "ref:.*slug\|citation_marker\|<!--ref:\|\\cite" parsers/ validators/

# 3. Check for claim audit patterns
rg "quantifier\|empirical\|assertion\|uncited" validators/ rules/

# 4. Check for tiered severity in gates
rg "tier\|severity\|annotation\|warn\|refuse" harness/ cli/
```

### Phase 2: Get API specs for porting (30 min)

Use `context7` to fetch arXiv and OpenAlex API documentation:

```
context7 "arXiv API Atom feed python"
context7 "OpenAlex API pyalex python"
```

### Phase 3: Architecture investigation (1-2 hours)

Use `authority-flow-audit` to trace how our gate system could evolve to support
tiered severity. This is the structural gap that affects ALL validators.

---

## Findings from This Session

| # | Finding | Skill Used | Status |
|---|---------|-----------|--------|
| 1 | 15 true ARS gaps (not 7) after removing false positives | Symbol analysis | ✅ Confirmed |
| 2 | 4 gaps are ARS-specific (skip) | Analysis | ✅ Filtered |
| 3 | Claim-faithfulness: we have 2 of 6 ARS steps | code-path-cartographer | ✅ Traced |
| 4 | Prose rules don't check citation presence | cli-explorer | ✅ Verified |
| 5 | No preprint venue detection | cli-explorer | ✅ Verified |
| 6 | 2 resolvers vs ARS 4 (missing arXiv + OpenAlex) | cli-explorer | ✅ Verified |
| 7 | Boolean gates vs tiered gates (structural) | authority-flow-audit | ✅ Verified |

## Dependency Chain for Porting

```
arXiv client ──┐
               ├──→ contamination_signals ──→ claim_audit_pipeline (full 6-step)
OpenAlex client┘                              ├──→ claim_audit_finalizer (8-row matrix)
                                              ├──→ uncited_assertion_detector (3-condition rule)
                                              └──→ claim_audit_calibration (FNR/FPR)
```

Porting `arXiv` + `OpenAlex` clients unlocks both the contamination detection gap
and the multi-resolver triangulation gap. They are the highest-ROI porting targets.

## Critical Discovery (Run #311)

**`compute_preprint_signal` is PURE LOGIC** — no API calls needed. It checks:
- `year >= 2024` AND `venue` in 10-item preprint venue list
- Falls back to `source_pointer` URL matching (arxiv.org → arXiv, etc.)

This means contamination detection can be ported **IMMEDIATELY** with zero
new dependencies. The full 4-resolver triangulation can wait.

**Dependency chain revised:**
```
compute_preprint_signal (port NOW — pure logic, ~30 loc)
    ↓
contamination_signals (port with CrossrefClient only — FUNCTION INJECTION)
    ↓
full triangulation (port after arXiv + OpenAlex clients — ~10h effort)
```
