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

### zotero.py stdout prints
- Check for `print(json.dumps(...))` stdout result patterns -> emit_json
- Zotero has a legacy `--json` flag; verify output semantics before migrating

### gate.py stdout prints
- `print(json.dumps(result, indent=2, ensure_ascii=False))` -> emit_json
- `print(format_gate_result(result))` -> emit_result

### dispatch.py / other handlers
- Scan for remaining stdout result prints

### BEHAVIOR-SENSITIVE (defer unless --quiet semantics verified)
- `print(f"Warning: ...", file=sys.stderr)` -> emit_warning (respects --quiet = behavior change)
- `print(f"Note: ...", file=sys.stderr)` -> emit_info (respects --quiet)
- Multi-line text sequences -> emit_result per line (verbose, needs care)
- These need tests that assert stderr-under-quiet behavior BEFORE migrating

## Completed

- audit.py: 14 stdout prints -> emit_json/emit_result (commit 5d6a12a, print_calls 96->82)
