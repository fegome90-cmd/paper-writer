# Phase 1 Plan — Scientific Linting Expansion

> **Fecha**: 2026-05-31
> **Origen**: Phase 0 completion + Judgment Day findings
> **Principio**: Phase 1 expande reglas y performance SIN romper Phase 0 Boundary.

## 1. Phase 0 Boundary (preserved)

Phase 0 explicitly does **NOT** do:

- ❌ No LLM (local or remote)
- ❌ No APIs (no runtime network calls)
- ❌ No external search (no PubMed, Semantic Scholar, OpenAlex, CrossRef)
- ❌ No MCP (Model Context Protocol is out of scope)
- ❌ No truth verification (Phase 0 detects risk, does not verify truth)
- ❌ No global score (no "paper scored 8.5/10" — only per-finding severity + gate pass/fail)
- ❌ No evidence retrieval (no abstract fetching, no full-text lookup)
- ❌ No automatic support/refute (no claim-against-evidence classification)
- ❌ No Phase 1 features (no LLM-assisted claim decomposition, no discourse-level analysis)

**Governing principle:** Phase 0 detects risk; it does not verify truth.

## 2. Phase 1 Scope

### 2.1 What Phase 1 IS
- Expandir reglas existentes (más checks, más checklists)
- Mejorar performance (cache, pre-compile)
- Agregar exit codes para CI
- Completar STROBE y PRISMA checklists

### 2.2 What Phase 1 is NOT
- No LLM
- No APIs
- No búsqueda externa
- No nuevos comandos que rompan la Boundary
- No score global

## 3. Architecture Decisions

### ADR-1: YAML rules cache
- Cache parsed rules in `__init__` to avoid re-read on every `validate()`
- Tradeoff: memory vs I/O

### ADR-2: Pre-compiled regex patterns
- Compile patterns once during rule loading
- Store as `re.Pattern` objects
- Tradeoff: memory vs CPU

### ADR-3: Exit codes for P0 findings
- `paper audit prose` and `paper audit claims` exit 1 when P0 findings exist
- `--strict` flag for CI that fails on P1 too
- Tradeoff: backward compatibility vs CI integration

### ADR-4: STROBE/PRISMA completion
- Add missing `expected_location` to all non-critical items
- Add missing items from full EQUATOR checklists
- Tradeoff: coverage vs maintenance burden

## 4. Deliverables

### 4.1 Performance improvements
| Item | File | Change |
|------|------|--------|
| YAML cache | `engine/loader.py` | Cache parsed rules/checklists in `__init__` |
| Regex pre-compile | `validators/prose.py` | Compile patterns once, store as `re.Pattern` |
| Regex pre-compile | `validators/claims.py` | Same |
| Checklist cache | `validators/method_gate.py` | Cache parsed checklists |

### 4.2 CI integration
| Item | File | Change |
|------|------|--------|
| Exit codes | `cli/paper/main.py` | Exit 1 on P0 findings |
| `--strict` flag | `cli/paper/main.py` | Exit 1 on P1 findings too |
| Schema validation | `cli/paper/main.py` | Validate output against schema |

### 4.3 Rule expansion
| Item | File | Change |
|------|------|--------|
| STROBE completion | `rules/method_gate/strobe.yml` | Add missing `expected_location`, add missing items |
| PRISMA completion | `rules/method_gate/prisma.yml` | Same |
| More prose checks | `rules/prose/*.yml` | Add passive voice, redundancy, sentence length |
| More claim types | `rules/claims/*.yml` | Add temporal, comparative triggers |

### 4.4 Bug fixes from Judgment Day
| Item | File | Change |
|------|------|--------|
| Abbreviation case | `parsers/source_map.py` | Handle uppercase abbreviations |
| Title Case false positives | `parsers/manuscript.py` | Restrict regex |
| Dedup risk field | `engine/deduplicator.py` | Handle `risk` field in sort key |
| YAML parse errors | `engine/loader.py` | Graceful degradation |

## 5. Implementation Order

| Batch | Focus | Dependencies |
|-------|-------|--------------|
| 1 | Performance (cache + pre-compile) | None |
| 2 | CI integration (exit codes + strict) | None |
| 3 | STROBE/PRISMA completion | None |
| 4 | More prose/claims rules | None |
| 5 | Bug fixes | None |

Batches 1–5 are independent and can be done in parallel.

## 6. Success Criteria

- [ ] All 523 existing tests still pass
- [ ] New tests for each new rule
- [ ] Performance: `validate()` completes in <100ms for 10-page manuscript
- [ ] Exit codes: P0 findings cause exit 1
- [ ] `--strict` flag: P1 findings cause exit 1 in strict mode
- [ ] STROBE checklist: all items have `expected_location`
- [ ] PRISMA checklist: all items have `expected_location`
- [ ] No new dependencies added
- [ ] Phase 0 Boundary preserved

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| New rules introduce false positives | High | Medium | Whitelist mechanism, severity tuning |
| Cache invalidation bugs | Medium | Low | Cache is read-only after init |
| Exit codes break existing scripts | Low | Medium | `--strict` is opt-in, default is legacy behavior |
| STROBE/PRISMA items incomplete | Medium | Low | Start with critical items only |

## 8. Post-Phase 1 (Phase 2+)

These features BREAK the Phase 0 Boundary and require explicit decision:
- `paper audit stats` — statcheck pattern (still local, but new command)
- `paper audit claims` with LLM — semantic verification
- `paper evidence-map` — evidence retrieval
- `paper gate journal` — journal-specific compliance
