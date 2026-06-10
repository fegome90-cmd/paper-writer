# Autoresearch Campaign: paper-writer reliability and local MeSH integration

## Goal

Improve demonstrably the reliability of the personal scientific pipeline and convert the existing local thesaurus into a useful tool with real MeSH data. Work through small, reversible, measurable experiments.

## Scope

- Pipeline integrity (search, dedup, provider failure propagation)
- Thesaurus reliability (manifest validation, sample vs real distinction)
- MeSH integration (XML conversion, CLI surface, data fidelity)

## Allowed Changes

- cli/paper/main.py
- harness/adapters/filesystem_action_runner.py
- harness/ports/paper_search_provider.py
- skills/local/adapters.py
- skills/local/thesaurus/**
- tests/**
- scripts/eval_paper_writer_reliability.py
- autoresearch/paper-writer/**
- docs/research/**

## Forbidden Changes

- drafting/
- rendering/
- validators unrelated to search/reliability
- MCP server external code
- vendored skills
- production dependencies
- general harness architecture
- editorial lifecycle

## Baseline Commit

9c2091cab1ce86ede7848e5cf379f1ccb1719ce6 (HEAD on autoresearch/paper-writer-reliability)

## Champion Commit

(initially same as baseline)

## Metrics

1. critical_failures (lower is better)
2. forbidden_prod_fixtures (lower is better)
3. golden_scenarios_passed (higher is better)
4. manifest_validation_passed (boolean)
5. mesh_fixture_import_passed (boolean)
6. regression_tests_passed (higher is better)
7. diff_lines (lower is better)
8. latency_ms (lower is better, tiebreak only)

## Gates (all must pass for promotion)

- G-01: relevant regression suite PASS
- G-02: no fictitious papers in real flow
- G-03: no silent fallback
- G-04: no provenance reduction
- G-05: no unauthorized lifecycle changes
- G-06: no forbidden infrastructure/dependencies
- G-07: no large datasets committed
- G-08: new behavior covered by positive and negative tests

## Hypothesis Queue

### Track A — Pipeline Integrity (Priority: HIGH)

1. **H-A01**: FilesystemActionRunner can generate fictitious paper when adapter fails or produces no artifact. Mock data at L225-233 ("Mock Paper 1", "10.1000/xyz123"). Mitigated by builder wiring but needs verification.
2. **H-A02**: LiteratureSearchAdapter may return status="fail" without raising exception, and FilesystemActionRunner may ignore it.
3. **H-A03**: CLI collects filters but FilesystemActionRunner may not forward them to the adapter correctly. CLI defines --year-min, --study-types etc. but test coverage of forwarding is missing.
4. **H-A04**: ~~deduplicate_papers mixes input and result indices~~ — **REFUTATED**: Already fixed at commit fff6c0a2 with regression test. Dead end.
5. **H-A05**: MCP server default path hardcoded to `/Users/felipe_gonzalez/.openclaw/mcp-servers/paper-mcp/dist/server.js`. Confirmed in mcp_paper_client.py:33. Needs fail-closed path handling.

### Track B — Thesaurus MeSH (Priority: MEDIUM, start after Track A)

1. **H-B01**: `paper thesaurus rebuild` reads JSONL without verifying checksum or concept_count. Reuses same validator as import.
2. **H-B02**: sample.jsonl is correct for tests but operates as ambiguous default. No test distinguishes synthetic from real MeSH. Source field exists but no gate checks it.
3. **H-B03**: ~~Missing MeSH XML converter~~ — **ALREADY EXISTS** in skills/local/mesh-import/. Uses lxml.etree.iterparse with SHA256, descriptors, concepts, terms, tree positions. CLI via `paper mesh import`. No duplication needed.
4. **H-B04**: Thesaurus model too flat for MeSH. Evaluate minimum evolution to preserve Descriptor/Concept/Term/TreePosition hierarchy. mesh-import has rich schema, thesaurus flattens.
5. **H-B05**: ~~Missing CLI surface for mesh conversion~~ — **ALREADY EXISTS** via `paper mesh import` + `paper thesaurus import/audit/search/rebuild`. Pipeline: MeSH XML → mesh-import SQLite → export JSONL → thesaurus import SQLite+FTS5.

## Dead Ends

- H-A04: deduplicate_papers index mixing — already fixed with regression test
- H-B03: MeSH XML converter — already exists in mesh-import
- H-B05: CLI surface — already exists

## Risks

- 4 unstaged modified files on main (clients/zotero.py, orchestrator.py, zotero_import.py, zotero_sync.py)
- mesh-import depends on lxml (external dependency) — not in campaign scope to change
- thesaurus sample.jsonl has 100 synthetic concepts; real mesh.jsonl has 31110

## Next Experiment

H-A01: Verify if mock data path in FilesystemActionRunner can leak into production flows. Create test that reproduces the failure case.

## Stop Conditions

A. Track A without reproducible critical failures AND Track B with stable MeSH fixture
B. 5 consecutive experiments without champion improvement
C. 20 experiments completed
D. Blocker requiring human decision
E. Working tree changes that cannot be safely isolated
