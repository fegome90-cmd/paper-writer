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

### 2.1 Phantom Validation 🧟‍♂️ (CRITICAL)

**Affected symbols**:
- `ManuscriptState.validate()` — `harness/domain/state.py`
- `StateManager.validate_state()` — `harness/services/state_manager.py`

**The bug**: These methods are documented as "enforces schema invariants and stage-gates consistency", but the **graph cannot see any of the call sites**.

**Why the graph is right** (in this case): the methods are invoked through local variables:
- `yaml_repository.py:36` — `state = ManuscriptState(...); state.validate()` — variable `state` is locally typed
- `state_manager.py:39` — `temp_state = ManuscriptState(...); temp_state.validate()` — same pattern
- `state_manager.py:55,68,81` — `self.load_state()` returns a dict, not a state

**Why the methods ARE reachable** (in reality):
- `state_manager.load_state()` returns `dict[str, Any]`
- The dict is then **implicitly** converted to a `ManuscriptState` somewhere downstream (or it isn't, in which case the validation is **never actually invoked in production**)

**Consequence**:
- If the conversion never happens, the system **loads `state.yaml` but never validates it**
- A user could write `state.yaml` claiming `stage: rendering` without `gates.search_completed: true`
- The system would trust the file and proceed

**Evidence the bug is real**:
```bash
$ grep -rn "validate_state\|state\.validate" harness/ cli/ 2>/dev/null
harness/adapters/yaml_repository.py:36:            state.validate()
harness/adapters/yaml_repository.py:43:            state.validate()
harness/services/state_manager.py:39:            temp_state.validate()
```
Only 3 call sites, all in repositories. The orchestrator's `load_state()` returns a dict, not a `ManuscriptState`. So **between `load_state()` and any use of the dict, the data is never validated**.

**Fix needed** (out of scope for this audit, but flagged):
- Either have `StateManager.load_state()` return a `ManuscriptState` object directly (force validation)
- Or call `validate_state()` on the loaded dict in `Orchestrator.execute()` before any transition

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

## 6. Recommended Next Steps

1. **Fix the phantom validation** — add `self._state_manager.validate_state(data)` after every `load_state()` call in `Orchestrator.execute()`. This is a 3-line change in 3 places.
2. **Refactor the Vale dispatch** — extract `_run_vale` and `_builtin_lint` into a single strategy table.
3. **Implement O-8** in Trifecta — self-attribute dispatch. This is a graph quality win, not a paper-writer fix.
4. **Run the new TrifectaBench IDX-07 (files with syntax error)** — ensure indexing recovers gracefully.
5. **Add a regression test** that runs `ctx validate` on a known-good state and confirms 0 source orphans. Run the same on a known-stale state and confirm the diff is reported.
