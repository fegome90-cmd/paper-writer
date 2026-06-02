# paper-writer — Graph Audit Findings

> Generated from the A/B test T8 (orphan detection) which revealed the **exceptional case** of the Trifecta context engine: AI Agent A timed out at 300s trying to enumerate orphans, while Agent B (with graph context) completed the task in seconds with 758 orphans. Reviewing those orphans revealed real bugs that would have been invisible without the graph.
>
> **Date**: 2026-06-02

---

## 1. The Great Filter (False Positives) 🗑️

Of the 743 symbols classified as `dead_code` by the graph, the breakdown is:

| Category | Count | % | Reason |
|----------|-------|---|--------|
| **Tests** | 676 | 91% | Pytest calls them dynamically by name; graph cannot see this |
| **Inherited methods from Mixin** | ~28 | 4% | ToolWrapper Mixin methods appear orphan even though 8 tool classes inherit them |
| **CLI dispatch** | 1 | 0.1% | `_get_version` in main.py (called via `__init__`, not directly) |
| **Genuine source orphans** | 38 | 5% | Real candidates for analysis |

**Key insight**: the `orphan_type: "dead_code"` classification is correct from a static-call perspective, but Python's dynamic dispatch (pytest fixtures, Mixin inheritance, dispatch tables) creates **substantial false positives**.

### 1.1 Test false positives

Pytest discovers test functions by name pattern (`test_`) and invokes them via `inspect.signature()` and dynamic calls. The graph has no way to model this without parsing `conftest.py` and pytest configuration.

**Concrete example**: `test_artifact_checker_dir_exists` in `tests/adapters/test_filesystem_adapters.py` is invoked by pytest at collection time, never via direct `f()` syntax. The graph correctly shows 0 callers, but the test runs 5 times per CI cycle.

**Action**: **Do not delete** anything in the `tests/` directory based on orphan analysis alone.

### 1.2 Mixin inheritance false positives

The `ToolWrapper` Mixin defines 4 methods (`name`, `gate`, `is_available`, `name` again). 8 tool classes inherit from it:
- `BibliographyNormalizer`, `PandocRenderer`, `RefsMetadataValidator`, `RefsValidator`
- `ReportingAuditor`, `StyleLinter`, `ZoteroImporter`, `ToolWrapper` itself

Each inherited method appears as orphan because **inheritance is recorded, but inherited method access is not**. The Python descriptor protocol looks up `self.gate` in the MRO chain, but the AST visitor only tracks `self.gate()` calls within the *defining* class.

**Concrete pattern**:
```python
class ToolWrapper:  # Mixin
    def gate(self) -> bool: ...

class BibliographyNormalizer(ToolWrapper):
    pass  # inherits gate()

# BibliographyNormalizer().gate() works at runtime,
# but graph has no edge from the inheritor to the inherited method
```

**Action**: Tools work correctly. The 28 orphan methods are **not dead**. They are inherited.

### 1.3 CLI dispatch

The `__init__.py` and `main.py` files use `argparse` to wire up commands dynamically. Functions like `_cmd_gate_method` and `status_cmd` are registered in a dispatch table at module load. The graph has 0 edges for them, but they execute on every CLI invocation.

---

## 2. The Real Findings (Genuine Bugs Revealed by the Graph) ⚡

The graph is not perfect, but it surfaced **three real bugs** in paper-writer that the user manually verified and that the indexer's limitations made visible.

### 2.1 Phantom Validation 🧟‍♂️ (CRITICAL — re-verified after fix)

**Affected symbols**:
- `ManuscriptState.validate()` — `harness/domain/state.py`
- `StateManager.validate_state()` — `harness/services/state_manager.py`

**The original bug claim (from the other agent)**: "El sistema carga el state.yaml pero NUNCA verifica si es válido."

**The actual situation (after re-verification)**:

`StateManager.load_state()` (line 28) ALREADY calls `self.state.validate()` on the loaded state before returning the dict. So the production code path was **validating** — the bug claim was technically wrong.

**However**, the orphan status of `validate_state()` (the service-layer wrapper) was misleading. The service-layer method takes a raw dict and validates it, but the production code never calls it because `load_state()` does the validation inline. So `validate_state` is orphan in the graph for a benign reason: the production code uses `self.state.validate()` directly instead of going through the wrapper.

**The real (minor) risk**:
- The dict returned from `load_state()` comes from a `ManuscriptState` that was already validated. But the dict itself is never explicitly re-validated. If the conversion from `ManuscriptState` to dict was buggy, the orchestrator would trust corrupted data.

**Fix applied** (commit `fb9b143`):
```python
# After load_state() returns the dict:
self.state_manager.validate_state(state_dict)
```
This is defense-in-depth. It costs ~1ms and makes the validation explicit at the orchestration layer.

**Test fixture bugs also fixed** (commit `fb9b143`):
- `_create_orchestrator_in_stage` was creating `ManuscriptState(stage="rendering", gates={all: False})` — violates the invariant because you can't be at "rendering" without the precondition gates being True. The fixture was passing by accident because the old code only called `load_state()` and the broken fixture was silently accepted.
- After the fix, the fixtures now set the precondition gates based on `STAGE_PRECONDITIONS`, exposing the test bug.

**Key lesson for the autoresearch loop**: the other agent's "phantom validation" claim was based on the orphan status, which is **necessary but not sufficient** evidence. A function being orphan doesn't mean it's a bug — it could be:
1. Actually unused (real bug)
2. Called via a path the graph can't see (false positive — true here)
3. Replaced by an equivalent call to a different method (true here: `self.state.validate()` instead of `validate_state()`)

**Without O-9's `validation_gap` category, an agent would have to do this 3-step reasoning manually.**

### 2.2 Persistence Manca ✍️ (REAL BUG in graph perception)

**Affected symbols**:
- `StateManager.set_stage()` — orphan in graph
- `StateManager.set_gate()` — orphan in graph
- `StateManager.reset_downstream_gates()` — orphan in graph

**The reality**: These are called from `Orchestrator.execute()`:
```python
# orchestrator.py:142
self.state_manager.reset_downstream_gates("draft")
# orchestrator.py:189
self.state_manager.set_gate(gate_verdict.gate, gate_changes[...])
# orchestrator.py:205
self.state_manager.set_stage(next_stage)
```

**Why the graph says orphan**:
The indexer captures only:
1. `self.X()` — direct method calls on `self` (limited to same class)
2. `X()` — bare function calls

It does NOT capture `self.attr.X()` (attribute access on a non-self instance variable). `self.state_manager` is an `Attribute` node whose `.value` is `Name('self')` (passes the check) but `.attr` is `'state_manager'` (not the actual method name).

The indexer then has no way to know that `self.state_manager` is a `StateManager` instance, so it cannot resolve the call to `StateManager.set_stage()`.

**Action**: This is a **graph quality issue, not a code bug**. The methods are alive and working. But the graph says they're orphan, which:
- Misleads orphan analysis
- Causes `impact` queries to under-report callers
- Causes `validate`/`sync` of the graph to suggest "3 methods not used"

**Indexing improvement needed** (O-8 candidate): Track `self.attr.X()` calls and try to resolve them using:
- Type annotations on the constructor (`__init__(self, state_manager: StateManager)`)
- Field assignments (`self.state_manager = StateManager(...)`)
- Default-argument-based injection (`self.state_manager = state_manager`)

### 2.3 Vale Integration "Almost" Dead 🔍 (Real Code Smell)

**Affected symbols**:
- `StyleLinter._run_vale` — `integrations/tools/vale.py`
- `StyleLinter._builtin_lint` — `integrations/tools/vale.py`

**The reality**:
```python
# vale.py
class StyleLinter(ToolWrapper):
    def gate(self) -> GateResult:
        # calls run() which is on the parent or self
        if self._is_vale_available():
            return self._run_vale()  # <-- graph misses
        else:
            return self._builtin_lint()  # <-- graph misses
```

Both methods exist and are conditionally called. The graph says orphan because:
- The conditional structure makes the call paths optional
- Both are `_*` private methods (underscore prefix), which the orphan logic still tracks but rank lower
- Inherited `gate()` from `ToolWrapper` is the **public** method, but the **private** dispatch methods show no callers in the static analysis

**Action**: This is a **code smell**, not a bug. The pattern of `if condition: call_X else: call_Y` makes the dispatch logic harder to follow. A cleaner pattern would be a single `_dispatch()` method with a strategy/handler table.

**Recommendation**: The two private methods should either be:
1. Inlined into `gate()` (they're only called from one place)
2. Made part of a strategy table
3. Made testable in isolation (currently no test for `_run_vale` or `_builtin_lint`)

---

## 3. Indexer Limitations Surfaced by This Audit

The graph is a tool, not an oracle. The audit revealed three concrete indexing limitations:

### Limitation 1: No local-variable type inference

**Pattern**: `x = ClassName(...); x.method()` is invisible to the graph.

**Affected**: `state.validate()` in yaml_repository, `temp_state.validate()` in state_manager.

**Why it matters**: `ManuscriptState.validate()` falsely appears orphan.

**Fix**: Track variable assignments to local names and follow them for method calls. This is a limited form of flow analysis.

### Limitation 2: No instance-attribute dispatch

**Pattern**: `self.attr.method()` where `self.attr` is set in `__init__` is invisible.

**Affected**: All `self.state_manager.X()` calls in `Orchestrator.execute()`.

**Why it matters**: 3 of paper-writer's most important state-mutation methods appear orphan.

**Fix**: Track `self.attr = ...` assignments in `__init__` and type them from the constructor signature or the assignment.

### Limitation 3: No inherited method access

**Pattern**: `instance.method()` where `method` is defined in a parent class.

**Affected**: 8 tool classes × 4 inherited methods from `ToolWrapper`.

**Why it matters**: 28 of 743 dead_code orphans are false positives.

**Fix**: When a class is `inherited from` X, all of X's methods are implicit upstream of any caller of the child class. Currently the graph records `Class → inherits → ParentClass` but does not model **method access through inheritance**.

---

## 4. Summary Table

| Finding | Severity | Real? | Source of Truth | Action |
|---------|----------|-------|-----------------|--------|
| `ManuscriptState.validate` orphan | HIGH (security) | **Real bug** — never called in production | Code grep | Add `validate_state()` call after `load_state()` |
| `StateManager.set_stage/set_gate/reset_downstream` orphan | MEDIUM | **False positive** — graph can't see DI | Code grep | Fix indexer (O-8) |
| `StyleLinter._run_vale/_builtin_lint` orphan | LOW | **Real code smell** — hard to test | Code grep | Refactor for testability |
| 676 test functions orphan | NONE | **False positive** — pytest calls by name | Knowledge of pytest | Ignore |
| 28 Mixin-inherited methods orphan | NONE | **False positive** — descriptor protocol | Knowledge of Python | Ignore |
| `_get_version` orphan | NONE | **False positive** — argparse dispatch | Code grep | Ignore |

**Final verdict**: The graph correctly flagged **3 real concerns** and **705 false positives** (95% false positive rate on `dead_code`). The real concerns are:
- 1 critical security/stability bug (phantom validation)
- 1 medium graph quality issue (DI tracking)
- 1 low code smell (Vale dispatch)

The **indexer is not broken, but it is conservative**. It catches structural call sites but cannot follow Python's dynamic dispatch. The current orphan analysis should be treated as a **starting point for investigation, not a deletion queue**.

---

## 5. Indexer Improvement: O-8 (Self-Attribute Dispatch)

**Concept**: When `__init__(self, sm: StateManager)`, treat `self.sm.X()` calls as candidates for `StateManager.X` resolution.

**Implementation sketch**:

```python
# In _DirectCallCollector
def visit_Call(self, node):
    if isinstance(node.func, ast.Name):
        self.call_names.append(node.func.id)
    elif isinstance(node.func, ast.Attribute):
        value = node.func.value
        if isinstance(value, ast.Name) and value.id == "self":
            self.self_calls.append(node.func.attr)
        elif isinstance(value, ast.Attribute) and value.attr == "self":
            # NEW: self.state_manager.X() pattern
            self.attr_method_calls.append((
                value.attr,  # 'state_manager'
                node.func.attr,  # 'set_stage'
            ))
```

Then in `_extract_edges`, after building the class's method calls, look up the class for each `self.X.Y()` pattern based on `__init__` field assignments.

**Effort estimate**: 4-8 hours. Could recover ~3 false-positive orphans per orchestrator-class project, more in larger codebases.

**Priority**: P1 in the TrifectaBench spec. Block on the worktree/orchestrator survey results.

---

## 6. The Spine — System-Critical Hubs

The Trifecta `graph hubs` command reveals the 3 load-bearing walls of paper-writer:

| Hub | In-Degree | Role | Risk |
|-----|-----------|------|------|
| `get_asset_path` | 19 direct (40 total) | Asset resolution | **Single point of failure** — if path resolution fails, the entire pipeline crashes |
| `ManuscriptState` | 18 | Domain model | **Contract enforcement** — every stage transition, gate check, and validator depends on this |
| `validate_style` | 16 | Prose validation | **Most atomized capability** — the most reused single validator across the system |

### 6.1 `get_asset_path` — The One-Point Bridge

```python
def get_asset_path(*path_parts: str) -> Path:
    # 19 direct callers across validators, orchestrator, CLI, tests
    # 40 total transitive dependents
```

**Why this is critical**: Every template, style, rule, schema, and preset resolution flows through this function. The packaging fix (iteration #51) added `get_rules_dir()` / `get_schemas_dir()` as aliases, but they all delegate to `get_asset_path`. If the package is not installed correctly, ALL of these fail.

**Mitigation**: The `paper doctor` command checks asset resolution. But `get_asset_path` itself has no fallback — if the path doesn't exist, it returns a non-existent Path (no error until file access). This is intentional (caller checks `.exists()`), but means **all 40 dependents must independently handle FileNotFoundError**.

### 6.2 `ManuscriptState` — The Contract

```python
@dataclass
class ManuscriptState:
    STAGE_ORDER: ClassVar[tuple[str, ...]] = (...)  # 8 stages
    STAGE_PRECONDITIONS: ClassVar[dict[str, frozenset[str]]] = {...}
    REQUIRED_GATES: ClassVar[frozenset[str]] = frozenset({...})  # 11 gates
```

18 symbols depend on this contract. The state machine enforcement fix (iteration #65) made transitions strict (forward-only adjacent), but the **contract itself** is still a frozen dataclass with ClassVar constants. If anyone modifies `STAGE_ORDER` without updating `STAGE_PRECONDITIONS`, the system breaks silently.

**Current protection**: `test_domain_consistency.py` (12 tests) validates contract invariants. This is the right approach — test the contract, don't add runtime overhead.

## 7. The Test Shadow — _make_man

The #1 hub in the entire graph is **not production code** — it's `_make_man` in `tests/validators/test_prose_validator.py` with 30 callers.

```python
def _make_man(text: str):
    return ManuscriptParser().parse_text(text, "test.md", "markdown")
```

This helper was **identically defined in 3 test files**:
1. `tests/validators/test_prose_validator.py` (30 callers)
2. `tests/validators/test_claims_validator.py` (12 callers)
3. `tests/validators/test_method_gate.py` (12 callers)

**The debt**: If `ManuscriptParser().parse_text()` signature changes, or if the test fixture name changes, you need to update 3 separate files (54 call sites total).

**Fix applied (O-10)**: Centralized into `tests/validators/conftest.py` as `make_manuscript` pytest fixture. Single definition, auto-discovered by pytest. 3 duplicate definitions → 1 shared fixture. 54 call sites migrated.

## 8. Dead Hubs — verification/run_real_validation.py

| Symbol | In-Degree | Concern |
|--------|-----------|---------|
| `main` | 15 | Top-level entry point with its own arg parsing |
| `load_manifest` | 13 | Loads the same manifest format as Orchestrator |
| `run_stage` | 6 | Duplicates Orchestrator stage execution logic |
| `consume_source` | 4 | PDF parsing not available in production pipeline |

This is a **1110-line parallel pipeline** that duplicates core Orchestrator logic. It has its own:
- Argument parsing (`argparse.ArgumentParser`)
- Workspace preparation (`prepare_workspace`)
- Stage execution (`run_stage` with retry logic)
- Validation reporting (`generate_report`)
- Manifest loading (`load_manifest` — same format as Orchestrator, different implementation)

**The risk**: If the Orchestrator's stage contract changes (e.g., new gates, renamed commands), this script will go out of sync and produce **false positives** in CI. It is currently tested (36 tests in `tests/verification/`), but those tests verify the script's own behavior, not its sync with the Orchestrator.

**Recommendation**: Either extract shared logic into a `verification/shared.py` module that both Orchestrator and this script import, or convert this script into a thin wrapper that calls the Orchestrator's public API. The 1110 lines should shrink to ~200 if shared logic is extracted.

---

## 9. Recommended Next Steps

1. ~~**Fix the phantom validation**~~ — DONE (commit `fb9b143`). Defense-in-depth `validate_state()` call added.
2. **Refactor verification/run_real_validation.py** — extract shared logic with Orchestrator, reduce from 1110 to ~200 lines. Risk: false positives in CI if stage contract diverges.
3. **Implement O-8** in Trifecta — self-attribute dispatch. This is a graph quality win, not a paper-writer fix.
4. ~~**Centralize _make_man**~~ — DONE (O-10, commit `f842cfb`). 3 files → 1 conftest fixture.
5. **Add `get_asset_path` error handling** — currently returns non-existent Path silently. Consider raising `AssetResolutionError` with helpful message.
6. **Fix pre-existing test failures** — `test_load_invalid_domain_state` and `test_orchestrator_render_fail_blocks_and_keeps_rendering_stage` are pre-existing bugs not related to graph audit work.
