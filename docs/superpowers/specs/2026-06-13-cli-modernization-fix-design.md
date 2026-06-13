# CLI Modernization Fix Cycle — Design Spec

**Date:** 2026-06-13
**Status:** Approved (user-validated remediation plan)
**Scope:** Focused — 2 open blockers from the `cli-modernization-typer-rich` review + their safety tests

---

## Background

A 4-agent `mr-thorough` review of the `cli-modernization-typer-rich` work at HEAD
re-examined the three blockers identified in the original audit. Findings:

| # | Blocker | Status |
|---|---------|--------|
| B1 | Missing `UserInputError` imports → F821/NameError | **RESOLVED.** Out of scope. |
| B2 | Output contract is dead code | **OPEN.** |
| B3 | `main.py` error boundary incomplete | **OPEN.** |

### Blocker 2 — Output contract is dead code

`cli/paper/output.py` defines a 5-channel contract
(`configure` / `summary` / `emit_result` / `emit_json` / `emit_info` /
`emit_warning` / `emit_error`, plus `to_json_value` and
`effective_output_format`). None of it is wired in:

- `output.configure()` has **zero call sites**.
- `dispatch.py:~178` still calls the legacy `_print_summary` (bare `print`)
  instead of `output.summary()`.
- The root `--quiet` and `--output-format` flags **do not exist** in `parser.py`.
- `to_json_value()` raises `TypeError` for `Path`, `Enum`, `dataclass`, and
  `datetime` — the branches were never added.
- No output-contract test file exists.

### Blocker 3 — `main.py` error boundary incomplete

`cli/paper/main.py:21-32` catches only `KeyboardInterrupt`, `UserInputError`,
and `ExternalServiceError`. Any other exception
(`OSError` from a corrupt `state.yaml`, `yaml.YAMLError`, `UnicodeDecodeError`,
`NameError`, `TypeError`) surfaces as a raw traceback, exits 1, and shows no
`Error:` prefix.

---

## Scope

### IN scope

- **B3** — `main.py` catch-all.
- **B2** — minimal wire of `output.py` (configure, summary, `to_json_value`
  branches, root flags, output-contract tests).
- **Safety tests** — new output-contract test file, exit-code-3 matrix test,
  zotero command coverage.

### OUT of scope (explicitly deferred — follow-up)

These are real findings but are **not** required to close B2/B3 and are
deferred to keep the fix cycle atomic and reviewable:

- **Phase C** — `dispatch.py` `if/elif` chain → `PIPELINE_MAP`; give the
  `verify` command a dispatch owner.
- **code_health_auditor.py** — fail-closed fix.
- **`test_import_time_budget`** — flaky test stabilization.
- **Rename 6 stale test names.**
- **Per-handler `print() → emit_*` migration** (`audit.py` 28 sites,
  `zotero.py` 25 sites, `graph.py` 22 sites) — deferred to Phase E+. This is
  **not** required to close B2; the minimal-wire approach makes the contract
  real without touching handlers.

---

## Strategy

- **TDD, test-first.** Each safety test is written first and must fail red
  before the fix.
- **Atomic commits.** One commit per blocker, smallest first.
- **Execution order:** B3 → B2 → safety tests.
- **Full-suite verification gate before every commit** (anti-trust-gap measure
  — see Verification Gate).

---

## Component Design

### 1. Blocker 3 — `main.py` catch-all (smallest, first)

Extend the existing boundary in `cli/paper/main.py`:

```python
except KeyboardInterrupt: ...              # existing
except UserInputError: sys.exit(2)         # existing
except ExternalServiceError: sys.exit(3)   # existing
except SystemExit: raise                   # NEW — CRITICAL
except Exception as exc:                   # NEW — the missing catch-all
    emit_error(f"Unexpected error: {exc}")
    sys.exit(1)
```

**Subtle requirement (load-bearing):** the catch-all `except Exception` MUST
re-raise `SystemExit`. `SystemExit` does not inherit from `Exception`, so the
explicit `except SystemExit: raise` is the safety net — typed exit codes
(`sys.exit(2)` / `sys.exit(3)` from `UserInputError` / `ExternalServiceError`
handlers deeper in the stack) must propagate untouched. Without this, those
codes collapse to exit 1. The exit-code-3 matrix test verifies this behavior.

### 2. Blocker 2 — minimal wire (5 touchpoints)

**`parser.py`** — add two ROOT flags that do not exist today:
- `--quiet` (`store_true`)
- `--output-format` (choices: `text`, `json`; default `text`)

**`main.py`** — after argparse, before dispatch:
```python
output.configure(
    quiet=args.quiet,
    output_format=effective_output_format(args),
)
```

**`dispatch.py`** — replace `_print_summary(result)` (line ~178) with
`output.summary(result)`, and **delete** the `_print_summary` function
(~35 lines of duplicated bare-print logic).

**`output.py`** — add branches to `to_json_value`. Order matters:
- `Enum` BEFORE `int` (IntEnum safety — otherwise an IntEnum serializes as
  its integer value).
- `bool` BEFORE `int` (so `True` serializes as `true`, not `1`).
- `PurePath` → `str(path)`.
- `datetime` / `date` → `.isoformat()`.
- `dataclass` → `dataclasses.asdict()` (recursive; `asdict` recurses into
  nested dataclasses and containers).

The function is already fail-closed (raises `TypeError` on unknown types) —
keep that contract.

**Deferred:** per-handler `print() → emit_*` migration (Phase E+).

### 3. Safety tests (TDD — written FIRST, must FAIL red)

**NEW `tests/test_cli/test_output_contract.py`:**
- `to_json_value` rejects `Path` / `Enum` / `dataclass` / `datetime` with
  `TypeError` (after the fix, the new branches handle these — the test
  confirms they serialize, not raise).
- `bool` serializes as `true`, not `1` (bool-before-int ordering).
- `configure()` resets `_config`.
- `emit_result` never suppressed (writes to stdout).
- `emit_info` suppressed by `--quiet` (writes to stderr).
- `emit_error` never suppressed (writes to stderr).
- `summary()` JSON branch.
- `effective_output_format` — subcommand overrides root.

**EXTEND `tests/cli/test_cli_exit_code_matrix.py`:**
- Add a subprocess-level test asserting `result.returncode == 3` for an
  `ExternalServiceError` path (Trifecta unavailable). **No exit-3 test exists
  today.**

**NEW `tests/test_cli/test_zotero_command.py`:**
- Cover the migrated `zotero.py` handlers:
  - Input-error path raises `UserInputError` → exit 2.
  - Service-error path raises `ExternalServiceError` → exit 3.
- The 23-site zotero migration currently has **zero unit coverage**.

---

## Data Flow

```
CLI args
  → main.py  (configure output: quiet, output_format)
  → dispatch → handlers  (raise typed exceptions)
  → main.py boundary:
        SystemExit            → propagate (preserve 2/3)
        UserInputError        → sys.exit(2)
        ExternalServiceError  → sys.exit(3)
        everything else       → emit_error + sys.exit(1)
```

---

## Error Handling — Exit Taxonomy

| Exit | Meaning | Source |
|------|---------|--------|
| 0 | Success | Normal completion |
| 1 | Unexpected error OR legitimate domain validation (XR6) | Catch-all; the 4 remaining `sys.exit(1)` in `audit`/`gate` |
| 2 | User input error | `UserInputError` |
| 3 | External service error | `ExternalServiceError` |

Document this taxonomy in the `cli/paper/errors.py` docstring, which today
only documents exit codes 2 and 3.

---

## Verification Gate (mandatory before EACH commit)

A prior executor ran only `tests/cli/` and reported "154 tests pass" — the
full suite is actually ~1685 tests. That trust gap is closed by mandating the
FULL suite at every commit:

```bash
uv run pytest
uv run ruff check cli/paper/
uv run mypy harness/ cli/ validators/ integrations/ verification/ parsers/ engine/ rules/ schemas/ skills/
```

**Never run `mypy .`** — the repo directory name `paper-writer` contains a
hyphen, which mypy rejects. Use the explicit package list above.

Each commit headline must state the **actual, verified** full-suite test
count — not an assumed number.

---

## Sequencing & Commit Plan

| Commit | Scope | Approx. size |
|--------|-------|--------------|
| 1 | **B3** — `main.py` catch-all + `SystemExit` re-raise | ~8 lines |
| 2 | **B2** — minimal wire (5 touchpoints) + output-contract test | parser, main, dispatch, output, test |
| 3 | **Safety tests** — zotero coverage + exit-code-3 matrix test | 2 test files |

Commit format: `<type>: <description>` (conventional commits). No AI attribution,
no `Co-Authored-By`.

Deferred items (Phase C, code_health_auditor fail-closed,
`test_import_time_budget`, 6 stale test renames, per-handler print migration)
are tracked as out-of-scope follow-ups.

---

## Open Questions

None. The design is approved. All scope decisions are recorded above as
resolved and are not re-opened by this spec.

---

## References

- Engram observation **#3727** — `mr-thorough` verdict (3 blockers, B1 resolved, B2/B3 open).
- Engram observation **#3723** — remediation plan (TDD, atomic, smallest-first, full-suite gate).
- Engram observation **#3722** — original 4-agent audit.

Internal references — not load-bearing for the implementation; recorded for traceability.
