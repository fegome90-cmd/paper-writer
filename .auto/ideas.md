# Autoresearch Ideas — PR2 Output-Contract Migration (2026-06-13)

## Metric Pivot Rationale

`system_exit_1_count` saturated at **legitimate floor = 4** (audit P0 findings x3 + gate
blocked x1). These are XR6 domain-validation exit-1 calls — migrating them = cheating.
Pivoted primary metric to `print_calls` (other half of PR2 "Output contract"). output.py
has a full 5-channel emit contract (`emit_json`/`emit_result`/`emit_info`/`emit_warning`/
`emit_error`) that handlers don't use yet.

## Floor Estimate for print_calls

- **Irreducible**: output.py contract itself = 5 print() (the channel implementations).
- **Deferred (behavior-sensitive)**: stderr Warning prints (emit_warning respects --quiet),
  multi-line text sequences in code_health/factuality/tables/quality_appraisal.
- **Realistic floor**: ~30-40 calls.

## Deferred Optimization Opportunities (apply per-iteration)

### graph.py stdout prints (~6 migratable)
- `print(json.dumps(result.data, indent=2, ensure_ascii=False))` -> `emit_json(result.data)`
  [callers/callees/path/overview json branches]
- Text result prints -> `emit_result(...)`
- graph.py needs `from cli.paper.output import emit_json, emit_result` added
- NOTE: graph.py was just migrated to ExternalServiceError; its stdout prints are clean wins

### gate.py stdout prints
- ✅ DONE (commit 11f82cb): print(json.dumps)->emit_json + print(format_gate_result)->emit_result.

### zotero.py stdout prints (24 total)
- ✅ DONE (commit 7b2a237): migrated 19 safe stdout result prints (3 emit_json + 16 emit_result). Deferred 6 behavior-sensitive: 1 stderr FAILED, 4 [DRY RUN] info, 1 Cancelled.

### dispatch.py stdout result prints (NEXT TARGET)
- ~11 prints; `_print_summary` has stdout result lines -> emit_result
- Check which are result vs info/stderr before migrating

### doctor.py (3 prints)
- Scan for result vs info categorization

### dispatch.py stdout result prints
- ✅ DONE (commit 2323772): migrated 5 RESULT prints (Success/Pipeline-Blocked/blockers/Artifacts) to emit_result. Deferred 6 info/warning prints (4 step-progress + 2 warning) — spec says emit_info/emit_warning=stderr but current=stdout=stream change.
- DISCOVERY: output.summary() is DEAD CODE duplicating _print_summary. design.md:776 says PR2 deletes _print_summary -> output.summary, but that full consolidation changes behavior (steps->stderr, adds JSON/--quiet) = multi-file refactor, documented as completion task.

### doctor.py (3 prints)
- Scan for result vs info categorization

### BEHAVIOR-SENSITIVE (defer unless --quiet semantics verified)
- `print(f"Warning: ...", file=sys.stderr)` -> emit_warning (respects --quiet = behavior change)
- `print(f"Note: ...", file=sys.stderr)` -> emit_info (respects --quiet)
- Multi-line text sequences -> emit_result per line (verbose, needs care)
- These need tests that assert stderr-under-quiet behavior BEFORE migrating
- BLOCKED: write a --quiet integration test FIRST, then migrate these (currently 6 in zotero + 2 audit stderr + 3 output.py stderr)

## Floor Analysis (current)
- output.py contract itself: 5 print() (irreducible — the channel implementations)
- output.py 3 stderr prints in emit_info/emit_warning/emit_error (irreducible)
- deferred behavior-sensitive (stdout->stderr stream change): dispatch 6 + zotero 6 + audit 2 = 14 prints
- realistic floor WITHOUT --quiet wiring: ~29 (output.py 8 + doctor 3 + deferred 14 + misc)
- realistic floor WITH --quiet wiring (full PR2 spec): ~8-10 (just output.py contract)

## Next Major Step (NOT a grep optimization — deliberate refactor)
To drop print_calls below ~29 HONESTLY, must wire --quiet per design.md:775-813:
1. Add --quiet + --output-format flags to parser.py
2. Call output.configure(quiet=..., output_format=...) in dispatch.py/main.py
3. DELETE _print_summary -> call output.summary() (design.md:776)
4. Migrate deferred info/warning prints (dispatch 6, zotero 6, audit 2) to emit_info/emit_warning
5. Update tests asserting stdout step output (test_paper_cli, test_cli_request_mapping, test_orchestrator, test_search_zotero_hardening) to expect stderr
This is a multi-file behavior change = should confirm with user before scope.

## Completed

- audit.py: 14 stdout prints -> emit_json/emit_result (commit 5d6a12a, print_calls 96->82)
- graph.py: 22 stdout prints -> emit_json/emit_result (commit abd6400, print_calls 82->60)
- gate.py: 2 stdout prints -> emit_json/emit_result (commit 11f82cb, print_calls 60->58)
- zotero.py: 19 safe stdout result prints -> emit_json/emit_result (commit 7b2a237, print_calls 58->39)
- dispatch.py: 5 RESULT prints -> emit_result (commit 2323772, print_calls 39->34)
