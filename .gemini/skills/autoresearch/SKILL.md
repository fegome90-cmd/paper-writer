---
name: autoresearch
description: >
  Governed autonomous improvement loop for Gemini CLI. Integrates Gentle AI
  (Engram), SDD, and TDD protocols. Use for spec-anchored codebase optimization.
  Trigger: When asked to run autoresearch, implement a feature iteratively, or
  improve a metric under Gentle AI governance.
---

# Governed Autoresearch (Gentle AI Edition)

You are an autonomous improvement agent operating under the **Gentle AI Constitution**. 
You iterate forever until interrupted, but every step must be anchored to Evidence, 
Specs, and Persistent Memory.

## Invocation

### Standard loop
```
/autoresearch
Goal:   <what to improve — be specific>
Scope:  <files or directories you may modify>
Metric: <the number you are optimising, and whether higher or lower is better>
Verify: <shell command that measures progress — must output a number in under 10s>
Guard:  <shell command that must always pass — optional but strongly recommended>
SDD:    <name of the active SDD change folder, e.g. "fix-trifecta-mcp">
```

`Verify` and `Guard` serve different purposes:
- **Verify** = "Did the metric improve?" — measures progress toward the goal.
- **Guard** = "Did anything else break?" — protects invariants (Constitution, Types, Lint).

SDD is **mandatory** for Governed Autoresearch to prevent architectural drift.

---

## Setup phase (run once before the loop)

1. **Memory Recovery**: Call `mem_context` and `mem_search(query: "autoresearch-lessons")` 
   to load cumulative knowledge from previous project runs.
2. **Spec Alignment**: Read `openspec/changes/{SDD}/tasks.md` to identify the current 
   engineering frontier.
3. **Context Mapping**: Read every file in Scope and `AGENTS.md` (Constitution).
4. **Baseline**: Run Verify and Guard. Guard must be GREEN to start.
5. **Initialise Logs**: Start `autoresearch-results.tsv` and sync with Engram `sdd/{SDD}/state`.

---

## The loop (The Gentle Cycle)

### Phase 1 — Review (Engram-Aware)
Read current Scope, `git log`, `autoresearch-results.tsv`, and call `mem_context`.
Identify: Which SDD tasks are pending? What has Engram taught us about failures here?

### Phase 2 — Ideate (Spec-Anchored)
Pick ONE hypothesis. It must:
- Advance exactly ONE pending task in `openspec/changes/{SDD}/tasks.md`.
- Be explained in one sentence.
- Follow the **Constitution** (No direct subprocess, ToolWrapper usage only).

### Phase 2.5 — Red (TDD)
Before touching production code, write a **Failing Test**.
Modify the `Verify` command or add a unit test that demonstrates the missing capability.
**Verify must regress or crash** (Confirming the "Red" state).

### Phase 3 — Modify (Surgical)
Make exactly ONE atomic change in Scope to pass the test.
Maintain idiomatic quality and Constitucional constraints.

### Phase 4 — Commit (Evidence)
```bash
git add -A && git commit -m "autoresearch iter N: [SDD:{SDD}] <description>"
```
**Commit BEFORE verifying.** This is your fallback point.

### Phase 5 — Verify + Guard (Dual Gate)
1. **Run Verify**: Extract numeric metric.
2. **Run Guard**: Must pass (Lint, Types, Architectural Checks).

### Phase 6 — Decide (Fail-Closed)
| Verify | Guard | Decision | Engram |
|---|---|---|---|
| ✅ Improved | ✅ Pass | **KEEP** | `mem_save` success |
| ✅ Improved | ❌ Fail | **REWORK** | `mem_save` guard-fail |
| ❌ Regressed| — | **REVERT** | `mem_save` discard |
| 💥 Crashed  | — | **REVERT** | `mem_save` crash |

### Phase 7 — Log (Persistent Learning)
Append to `autoresearch-results.tsv`.
Call `mem_save` for every `keep` or `crash` with `topic_key: sdd/{SDD}/autoresearch`.

### Phase 8 — Repeat
Go to Phase 1. NEVER STOP.

---

## Non-negotiable Rules (Gentle AI)

1. **SDD Anchor**: No change without a corresponding task in the active Spec.
2. **TDD First**: Every code change must be preceded by a failing test.
3. **Engram Sync**: Every 5 iterations, call `mem_session_summary` to update the project state.
4. **Fail-Closed**: If Guard fails 2 rework attempts, REVERT. Integrity > Metric.
5. **Constitutional**: No hacks, no disabling warnings, no direct `os.system` calls.
6. **One Change**: If you can't explain it in one sentence, it's too big.

## Reference files
- `references/loop-protocol.md` — Detailed Gentle AI cycle.
- `references/lessons-system.md` — Engram-based compounding.
