# Phase 2 Plan — Paper-Writer as MCP Client

> **Date**: 2026-06-02
> **Origin**: Phase 1 completion + `robin-era-mcp-audit.md` §10 reconciliation + `plan-extract-cli-wiring-builder.prompt.md` as a hard prerequisite.
> **Governing principle**: The `paper` CLI **consumes** external MCPs (Robin, ERA, others) through adapters, decides **per tool** whether to resolve locally (Phase 0) or via an MCP adapter, and **fails closed** by default.

---

## 1. Frozen inputs (read first, do not re-open)

This plan builds on documents already committed to the repo. Treat each as locked unless explicitly noted.

- **`docs/plans/plan-extract-cli-wiring-builder.prompt.md`** — Defines the `OrchestratorDependencies` builder (frozen dataclass with `repo_path`, `state_manager`, `checker`, `action_runner`, `wrappers`, `skill_adapters`) and the rule that the CLI **constructs** `Orchestrator` from the returned container. Phase 2 extends the same pattern with an `mcp_clients` slot. Status: implementation partially merged; Phase 2 cannot proceed until all four sub-gates in §13 are green.
- **`docs/research/phase-1-plan.md` §8** — Enumerates the four post-Phase-1 features that BREAK the Phase 0 Boundary (`paper audit stats`, `paper audit claims` with LLM, `paper evidence-map`, `paper gate journal`). Phase 2 introduces a **resolution layer** that gates these features on adapter availability; it does NOT add LLM-in-the-loop behavior in v1.
- **`docs/research/mcp-tools-candidates.md`** — Canonical candidate list for MCP consumers. Four P0 tools: `paper_claim_audit`, `paper_evidence_map`, `paper_reviewer2`, `paper_method_gate`. P1/P2 listed but explicitly deferred. This plan treats that priority list as locked.
- **`docs/research/robin-era-mcp-audit.md` §8–§10** — Section 8 (reconciled 2026-06-01) confirms the corrected direction: paper-writer is an MCP **client**, never a server. Section 9 explicitly recommends architecture **A** (CLI orchestrator with MCP-client adapters, local fallback). Section 10 reserves Fase 2 for a "pendiente de spec canónico" — this document fills that gap and supersedes the placeholder.

**Locked vs open**:
- Locked: `ToolWrapper` as the port (Q1), resolution precedence CLI > config > invariant (Q2), fail-closed default (Q4), plumbing-only v1 (Q9), P0 candidate set, no MCP server exposure, no agentic loops.
- Open and configurable in implementation: probe transport (Q3), timeouts/retries (Q5), response schema (Q6), HTTP/SSE transport (Q7), credential storage (Q8), sanitization policy (Q10), adapter-to-gate mapping cardinality (Q11), CLI surfacing format (Q12). Defaults supplied; override allowed in code review.

---

## 2. Scope

### 2.1 What Phase 2 IS

1. Move all inline Fase 0 logic (`_cmd_audit_prose`, `_cmd_audit_claims`, `_cmd_gate_method`) from `cli/paper/main.py` into `harness/services/audit/` so the CLI entrypoint becomes pure dispatch.
2. Introduce an `MCPAdapter` class that conforms to the existing `ToolWrapper` port — no new port, no sibling port.
3. Add an `mcp_clients: MappingProxyType[str, MCPAdapter]` slot to `OrchestratorDependencies` (parallel to `wrappers` and `skill_adapters`).
4. Define a config schema (`.paper-writer/mcp.yaml`) and a CLI flag (`--mcp-resolver`) for per-tool resolution between local and MCP paths. Precedence: CLI flag > config file > static invariant in `harness/services/orchestrator.py`.
5. Implement a fail-closed default with an explicit opt-in (`fallback: local`) for resolvers where a local implementation exists. MCP-only tools (P1+ tools with no local path) ALWAYS fail-closed (schema-level enforcement: `fallback` key rejected).
6. Probe adapter availability at command start (JSON-RPC `initialize` for stdio) and emit a structured step in `OrchestratorResult.steps` describing which path was used.
7. Provide a stub MCP transport usable in CI and integration tests, with no network dependency.
8. Sanitize every adapter request before logging or persisting; reject configs that contain secret-like values.

### 2.2 What Phase 2 is NOT

1. **Not** an agentic loop. No LLM-in-the-loop orchestration, no iterative refinement, no tool-of-tools. Phase 2 is plumbing.
2. **Not** an MCP server. `paper-writer` does not expose its own MCP tools. Adapters only consume.
3. **Not** a Fase 0/1 expansion. No new validators, no new rule families, no new CLI commands beyond the resolution mechanism. P1/P2 tools listed in `mcp-tools-candidates.md` are **out of v1** scope.
4. **Not** a duplicate of `plan-extract-cli-wiring-builder.prompt.md`. The extraction plan owns the dependency builder; Phase 2 consumes its output and adds the `mcp_clients` slot.
5. **Not** an HTTP/SSE transport implementation. v1 is stdio JSON-RPC only. HTTP/SSE is parked as a follow-up.
6. **Not** a keychain integration. Credentials are env-var-only in v1. Keychain is a follow-up.
7. **Not** `paper review`. The composition command that exercises Phase 2 is **PR #5**, a follow-up after the plumbing ships.

---

## 3. Open design questions (already triaged)

| # | Question | Priority | Status | Default (configurable in implementation) |
|---|----------|----------|--------|------------------------------------------|
| Q1 | Port for MCP adapters | P0 | **LOCKED** | Reuse `ToolWrapper`. No new port. |
| Q2 | Resolution policy location | P0 | **LOCKED** | `.paper-writer/mcp.yaml` + CLI flag override; static invariant hardcoded in `harness/services/orchestrator.py`. Precedence: CLI > config > invariant. |
| Q3 | Availability probe | P1 | Open | JSON-RPC `initialize` (stdio). TCP connect for HTTP/SSE in follow-up. |
| Q4 | Failure semantics | P0 | **LOCKED** | Fail-closed default; opt-in `fallback: local` in config. MCP-only tools always fail-closed (schema rejects `fallback` key). |
| Q5 | Timeouts / retries | P1 | Open | Per-adapter config in `.paper-writer/mcp.yaml` under `timeouts:`. No global default. |
| Q6 | Response schema | P1 | Open | Pydantic models in `harness/services/mcp/responses.py`. |
| Q7 | Transports v1 | P1 | Open | stdio JSON-RPC only. HTTP/SSE parked until first HTTP-based MCP appears. |
| Q8 | Credential storage | P1 | Open | Env var only. Precedence: env > config. No keychain in v1. |
| Q9 | `paper review` command | P0 | **LOCKED** | NOT in v1. PR #5 follow-up after PR #1–#4 ship. |
| Q10 | Artifact sanitization | P1 | Open | Redacted dict via `SecretDetector` utility in `harness/services/mcp/sanitization.py`. Never emit raw credentials. |
| Q11 | Adapter → gate mapping | P1 | Open | 1:1 in v1 (each adapter declares exactly one gate). Generalize to many-to-many in follow-up. |
| Q12 | CLI surfacing | P1 | Open | One entry in `OrchestratorResult.steps` per MCP call + one-line summary at the end of the run: `"paper_claim_audit: resolved via mcp:robin (latency=120ms)"`. |

---

## 4. Architecture decisions (ADRs)

### ADR-1: Reuse the `ToolWrapper` port for MCP adapters (Q1)

- **Context**: Phase 2 introduces external tool adapters. The cleanest separation is a new port; the cheapest separation is reuse.
- **Decision**: `MCPAdapter` is a `ToolWrapper` concrete subclass. No new port. The orchestrator does not change.
- **Tradeoff**: Conflates local and remote tools in the same dict (`wrappers` plus the new `mcp_clients`). Mitigated by tagging each entry with an `adapter_id` and a `transport` field in step logs. **Cost**: one more slot in `OrchestratorDependencies`. **Benefit**: zero churn in `_run_wrapper_gate`.

### ADR-2: Resolution policy in `.paper-writer/mcp.yaml` with CLI override (Q2)

- **Context**: The orchestrator must decide per tool whether to call the local validator or the MCP adapter. A static mapping in code is too rigid; a free-form runtime check is too volatile.
- **Decision**: Resolution is configured in `.paper-writer/mcp.yaml` (per-tool section). A CLI flag `--mcp-resolver=tool=adapter[,tool=adapter...]` overrides the config for the current invocation. Hardcoded **invariants** (e.g., `paper_method_gate` always resolves local if no adapter configured) live in `harness/services/orchestrator.py` with an explanatory comment. Precedence: CLI flag > config file > static invariant.
- **Tradeoff**: Three precedence layers is more cognitive load than two. Mitigated by documenting the precedence in the config file's leading comment and by failing closed when a CLI flag names a non-existent tool.

### ADR-3: Fail-closed default with explicit `fallback: local` opt-in (Q4)

- **Context**: External MCPs are flaky, rate-limited, and can disappear. A silent fallback to local hides outages and produces misleading success signals.
- **Decision**: Default is **fail-closed**. The orchestrator emits a `blocker` naming the transport, the tool, and the failure mode. To allow fallback for tools that have a local path, the config author must set `fallback: local` on that tool's entry. When fallback fires, the orchestrator emits a `warning` with the message `"fallback triggered for <tool>: mcp <adapter> unavailable, using local"`. **MCP-only tools** (P1+ tools without a local implementation) are blocked at config load — the schema rejects the `fallback` key on their entries.
- **Tradeoff**: Stricter than typical MCP integrations. **Cost**: more boilerplate in YAML, more explicit "fallback triggered" warnings. **Benefit**: no silent degradation; every fallback is auditable; outages are visible in CI logs.

### ADR-4: v1 is plumbing only; `paper review` is PR #5 (Q9)

- **Context**: A complete `paper review` flow that exercises MCP resolution end-to-end is high-value but high-risk. Shipping the plumbing first lets us validate the resolution layer against integration tests before composing it into a user-facing command.
- **Decision**: v1 ships PR #1 through PR #4. `paper review` is **deferred to PR #5** and is not part of the v1 success criteria. PR #5 ships in a follow-up plan or a clearly labeled "Phase 2.1" extension.
- **Tradeoff**: Two PRs land before users see the value. Mitigated by a smoke-test script (PR #4) that exercises the resolution layer against a stub adapter so the wiring is visible from day one. **Benefit**: smaller blast radius per PR; clear go/no-go signal at each merge.

---

## 5. Adapter contract

The `ToolWrapper` port in `harness/ports/tool_wrapper.py` is the **only** contract an MCP adapter must satisfy. The contract is:

```python
class ToolWrapper(ABC):
    @abstractmethod
    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def gate(self) -> str: ...

    # Concrete subclass signature target (NOT implementation):
    class MCPAdapter(ToolWrapper):
        def __init__(self, transport: MCPTransport, timeout_ms: int, adapter_id: str) -> None: ...
        def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult: ...
        def is_available(self) -> bool: ...
        @property
        def name(self) -> str: ...
        @property
        def gate(self) -> str: ...
```

The orchestrator's `_run_wrapper_gate` (in `harness/services/orchestrator.py:372`) is the **integration surface**. It already handles `ToolNotAvailableError`, the validator-to-gate conversion, and the fail-closed blocker emission. The MCP-specific concerns — transport spawn, JSON-RPC encode/decode, request sanitization — live entirely inside the `MCPAdapter` subclass. The orchestrator sees no difference between a local wrapper and an MCP adapter.

**Invariant**: An MCP adapter MUST NOT raise anything other than `ToolNotAvailableError` and the JSON-RPC error classes declared in `harness/services/mcp/errors.py`. It MUST return a `ValidatorResult` whose `validator` field equals `self.name`.

**Non-goals for the port**: streaming responses, callbacks, push notifications. v1 is request/response only.

---

## 6. Resolution layer: local vs MCP

```
        CLI
         │  --mcp-resolver=tool=adapter[,tool=adapter...]
         │  .paper-writer/mcp.yaml
         ▼
   ┌─────────────────────────────────────┐
   │       Orchestrator.execute()        │
   │  1. resolve(per tool) ← precedence  │
   │     CLI > config > static invariant │
   │  2. probe (JSON-RPC initialize)     │
   │  3. dispatch to wrapper/adapter     │
   │  4. on fail: blocker or fallback    │
   └──────────┬──────────────────────────┘
              │
      ┌───────┴───────┐
      ▼               ▼
  local wrapper    MCPAdapter
  (ToolWrapper)    (ToolWrapper subclass)
      │               │
      ▼               ▼
  ValidatorResult  JSON-RPC over stdio
                       │
                       ▼
                  remote MCP server
                  (Robin, ERA, other)
```

Per-tool resolution is computed once at command start, recorded as a `step` entry in `OrchestratorResult.steps`, and frozen for the rest of the run. The probe is the only network-touching code in v1 (a single `initialize` call per configured adapter).

**Config schema** (`.paper-writer/mcp.yaml`, gitignored when it contains secrets):

```yaml
version: 1
adapters:
  robin:
    transport: stdio
    command: ["robin-mcp", "--stdio"]
    env: {}                       # NO secrets here; use process env (Q8)
    timeouts:
      connect_ms: 2000
      request_ms: 30000
  era:
    transport: stdio
    command: ["era-mcp", "--stdio"]
    timeouts:
      connect_ms: 2000
      request_ms: 60000
resolvers:
  paper_claim_audit:
    adapter: robin
    fallback: local              # opt-in; absent = fail-closed
  paper_evidence_map:
    adapter: robin
    fallback: local
  paper_reviewer2:
    adapter: robin                # MCP-only; fallback key rejected by schema
  paper_method_gate:
    adapter: era                  # MCP-only; default local
    # NB: no `fallback` key — fails closed if era is down
```

Precedence is enforced in `harness/services/orchestrator.py:_resolve_tool`. A CLI flag parses to a dict that overlays the config dict, which overlays the static invariant.

---

## 7. Fallback and fail-closed semantics

The orchestrator's resolution + fallback logic follows four rules:

1. **No adapter configured for a tool** → use the static invariant (local if available, else fail with `blocker: no resolver for <tool>`).
2. **Adapter configured and reachable** → use the MCP adapter. No fallback.
3. **Adapter configured and unreachable, `fallback: local` set, and a local wrapper exists** → use the local wrapper and emit a `warning: fallback triggered for <tool>: mcp <adapter> unavailable, using local`. The step entry records the path switch.
4. **Adapter configured and unreachable, no `fallback: local` set, OR tool is MCP-only** → emit `blocker: mcp <adapter> unreachable for <tool> (transport=<transport>, tool=<tool>, failure_mode=<class>)`. The step entry records the failure but does not proceed to the local wrapper.

**Schema-level enforcement for MCP-only tools**: `MCPResolverConfig` is a Pydantic model with a discriminator on `fallback`. When the tool has no local path (the canonical list is `paper_reviewer2` until Fase 3 adds more), the `fallback` key is rejected with `ValidationError` at config load. The error message names the tool and the offending key.

**Log discipline on fallback**: every fallback firing writes one structured warning. The warning text is fixed (not user-configurable) so log scrapers can detect it. CI rules can grep for it.

---

## 8. P0 candidate tools (from `mcp-tools-candidates.md`)

| Tool | Orchestrator command (when MCP path is taken) | Local resolver (when MCP path is not) | MCP adapter slot | Fallback allowed |
|------|-----------------------------------------------|---------------------------------------|------------------|------------------|
| `paper_claim_audit` | `audit_claims` (new) — composed in PR #5 | `_cmd_audit_claims` refactored (PR #1) | `robin.paper_claim_audit` | yes (local exists) |
| `paper_evidence_map` | `map_evidence` (new) — composed in PR #5 | none in v1 | `robin.paper_evidence_map` | no (no local) |
| `paper_reviewer2` | `reviewer2_run` (new) — composed in PR #5 | none in v1 | `robin.paper_reviewer2` | no (MCP-only) |
| `paper_method_gate` | `gate_method` (reuses existing command) | `MethodGateValidator` (PR #1 refactor) | `era.paper_method_gate` | yes (local exists) |

**P1/P2 tools — explicitly out of v1**:

| Tool | Status | When to revisit |
|------|--------|-----------------|
| `paper_reference_verify` | P1 parked | After v1 ships; requires `paper://claim-ledger/current` resource |
| `paper_wiki_sync` | P1 parked | After claim ledger resource ships |
| `paper_hypothesis_generate` | P1 parked | After Fase 3 spec exists; out of scope for v1 |
| `paper_experiment_plan` | P1 parked | After Fase 3 spec exists; out of scope for v1 |
| `paper_repro_audit` | P2 parked | After sandbox policy is written; out of scope for v1 |

---

## 9. Configuration, credentials, and discovery

**Config file location**: `.paper-writer/mcp.yaml` at the project root. Justification: the file is resolver-specific, has a different audience (DevOps / CI), and must be gitignored when it carries non-secret operational data (endpoints, timeouts). It is **not** a section of `state.yaml` because (a) `state.yaml` is meant to be machine-generated and human-readable-as-state, not hand-edited, and (b) mixing resolver config with state confuses the diff view.

**Discovery order at command start** (in `harness/services/orchestrator.py:_load_mcp_config`):

1. CLI flag `--mcp-resolver=tool=adapter[,tool=adapter...]` (highest precedence, applied as overlay).
2. `.paper-writer/mcp.yaml` in the project root.
3. Static invariant in `harness/services/orchestrator.py` (lowest precedence; default resolvers and gate mappings).

**Credentials**: env vars only in v1. The schema for the `env:` section in `.paper-writer/mcp.yaml` is `Mapping[str, SecretReference]` where `SecretReference = str` matching the pattern `^[A-Z][A-Z0-9_]*$` (e.g., `OPENAI_API_KEY`). At adapter construction time, the env var is resolved against `os.environ`. The **resolved value never appears** in `OrchestratorResult.steps`, in `state.yaml`, in the artifact directory, or in any log line. A `SecretDetector` utility in `harness/services/mcp/sanitization.py` enforces this at three checkpoints: step-emit, artifact-write, log-emit.

**Security boundary (hard rules)**:

- No secrets in the repo (`.gitignore` includes `.paper-writer/mcp.local.yaml` and any `*.mcp.secret` files).
- No secrets in `state.yaml` (schema rejects string values that look like API keys — see ADR-3 and §9.4 of `VALIDATOR_CONTRACTS.md` if it exists, else define in `harness/services/mcp/sanitization.py`).
- No secrets in `OrchestratorResult` (the `SecretDetector` runs on every dict before it leaves the orchestrator).
- No secrets in artifact files (same detector runs at `action_runner.emit_*`).

**Discovery**: v1 does not auto-discover adapters. The user declares each adapter explicitly in `.paper-writer/mcp.yaml`. This avoids the "where did this adapter come from?" failure mode and keeps the resolution layer auditable.

---

## 10. Observability and traceability

Every MCP adapter call MUST emit one step entry into `OrchestratorResult.steps` with the following schema:

```python
{
    "step_id": f"mcp_{adapter_id}_{tool}",   # e.g. "mcp_robin_paper_claim_audit"
    "status": "succeeded" | "failed",
    "tool": "<tool_name>",                    # e.g. "paper_claim_audit"
    "transport": "stdio",                     # v1: always "stdio"; future: "http", "sse"
    "latency_ms": 120,                        # wall-clock from probe end to response received
    "gate": "<gate_name>",                   # the gate this resolver feeds
    "adapter_id": "<adapter_id>",            # e.g. "robin"
    "error_class": None | "TransportDown" | "Timeout" | "SchemaMismatch" | "AuthFailure" | "RateLimited" | "Other",
    "sanitized_request": {...},              # JSON-RPC payload with secrets redacted
    "path": "mcp" | "local" | "local_via_fallback",   # which path was taken
}
```

**Path field semantics**:

- `path: "mcp"` — adapter was configured, reachable, succeeded.
- `path: "local"` — no adapter configured, or CLI flag disabled MCP for this tool; local wrapper used.
- `path: "local_via_fallback"` — adapter was configured and unreachable; `fallback: local` was set, and the local wrapper was used. The same step entry also carries `status: "succeeded"` and a sibling `warning` entry on the result.

**Artifact emission**: MCP adapters write their raw response (sanitized) to `outputs/audits/<timestamp>_<tool>_<adapter_id>.json`. Local wrappers' existing artifact paths are unchanged. The orchestrator's existing `action_runner.emit_manifest` is the single point that aggregates them.

**One-line summary at run end**: `_print_summary` in `cli/paper/main.py` adds one line per MCP resolution that occurred, formatted as `"{tool}: resolved via {path} ({adapter_id} via {transport}, latency={N}ms)"`. When `path == "local_via_fallback"`, the summary appends `(FALLBACK TRIGGERED)`.

---

## 11. Prerequisites

Phase 2 cannot start until every box is green.

- [ ] `plan-extract-cli-wiring-builder.prompt.md` fully merged (all 4 sub-gates green) — `pytest tests/harness/ -v` must pass.
- [ ] Fase 0 logic extracted from `cli/paper/main.py` into `harness/services/audit/` — `grep -n "_cmd_audit" cli/paper/main.py` returns no matches.
- [ ] `Orchestrator` and `OrchestratorDependencies` confirmed as the only construction path — no second wiring story.
- [ ] `ToolWrapper` port surface reviewed — accepted as the MCP adapter contract.
- [ ] Phase 1 success criteria still green (regression test suite passes).
- [ ] `mcp-tools-candidates.md` reconciled with current `OrchestratorRequest` / `OrchestratorResult` shape (no command name drift).
- [ ] MCP credential storage policy documented in `docs/SECURITY.md` (or equivalent) — env-var-only, no keychain in v1.
- [ ] Stub MCP transport implemented and used by integration tests — CI does not require network.

---

## 12. Implementation batches

| PR | Focus | Files touched | Gate |
|----|-------|---------------|------|
| **#1** | Refactor Fase 0: move `_cmd_audit_prose`, `_cmd_audit_claims`, `_cmd_gate_method` from `cli/paper/main.py` to `harness/services/audit/`. `cli/paper/main.py` becomes pure dispatch (no inline validator calls). | `cli/paper/main.py` (lines 54–167 refactored), NEW: `harness/services/audit/{prose,claims,method_gate}.py`, NEW: `harness/services/audit/__init__.py`. | Existing Fase 0 tests pass without modification. `pytest tests/validators/ -v` green. `pytest tests/cli/test_cli_request_mapping.py` green. |
| **#2** | Adapter contract: define `MCPAdapter(ToolWrapper)` in `harness/services/mcp/adapter.py`, add `mcp_clients: MappingProxyType[str, MCPAdapter]` slot to `OrchestratorDependencies`, register a stub transport (`harness/services/mcp/transports/stdio.py`). | NEW: `harness/services/mcp/{adapter.py,transports/__init__.py,transports/stdio.py,errors.py,responses.py}`, modify `harness/services/orchestrator_builder.py` (add `mcp_clients` field + builder arg), modify `harness/services/orchestrator.py` (no semantic change; just thread the new field). | `tests/harness/test_mcp_adapter.py` ≥ 80% coverage. `_run_wrapper_gate` behavior unchanged. Existing builder tests still pass. |
| **#3** | Resolution layer: parse `.paper-writer/mcp.yaml`, add `--mcp-resolver` CLI flag, implement `_resolve_tool` in `harness/services/orchestrator.py`, probe at command start (JSON-RPC `initialize`). | NEW: `harness/services/mcp/{config.py,schema.py,probe.py}`, modify `cli/paper/main.py` (add flag), modify `harness/services/orchestrator.py` (`_resolve_tool` + probe call). | `tests/integration/test_resolution.py` passes. Config validation rejects unknown tools, missing adapters, and `fallback` key on MCP-only tools. Probe does not block the orchestrator on unconfigured adapters. |
| **#4** | Fallback semantics: implement the four-rule fallback logic, integrate step entries, wire `SecretDetector` into step-emit and artifact-write paths, add the "FALLBACK TRIGGERED" suffix to the one-line summary. | modify `harness/services/orchestrator.py` (fallback dispatch + step emission), NEW: `harness/services/mcp/sanitization.py`, modify `cli/paper/main.py` (`_print_summary`), modify `harness/adapters/filesystem_action_runner.py` (sanitize on emit). | `tests/integration/test_fallback.py` passes. MCP-down → blocker for MCP-only tools; MCP-down → local + warning for `fallback: local` tools. `pytest tests/security/test_secret_detector.py` (or equivalent) passes. |
| **#5** | `paper review` command (follow-up, **not v1**): compose orchestrator + extracted Fase 0 services + zero or more MCP adapters into a single command. | NEW: `cli/paper/review.py` (or extension of `main.py`), NEW: `harness/services/review/orchestrator.py` (sub-orchestrator if composition exceeds main flow). | E2E test: `paper review` runs end-to-end with the stub Robin transport. `pytest tests/e2e/test_paper_review.py` passes. |

**Dependency graph**: PR #1 has no dependencies; PR #2 depends on PR #1 (so the orchestrator surface is stable); PR #3 depends on PR #2; PR #4 depends on PR #3; PR #5 depends on PR #4. PRs #1–#4 form v1.

---

## 13. Success criteria

Observable, testable, and tied to a specific test path.

- [ ] `paper audit prose`, `paper audit claims`, `paper gate method` run end-to-end after PR #1 with no change in output (regression test in `tests/cli/test_cli_phase0_regression.py`).
- [ ] `paper review` runs end-to-end with zero MCP adapters configured and produces equivalent result to pre-Phase-2 Fase 0 invocation (regression test). **Note**: `paper review` itself is PR #5; this criterion is satisfied by the existing Fase 0 regression once PR #5 lands. v1 does not include this criterion.
- [ ] `paper review` runs end-to-end with at least one MCP adapter configured, exercises both local and MCP path for at least one P0 tool. **Note**: same as above — PR #5 criterion.
- [ ] When MCP is configured but unreachable, the orchestrator fails closed with explicit `blocker` naming the transport and the tool. Test path: `tests/integration/test_fallback.py::test_mcp_down_blocks_mcp_only_tool`.
- [ ] When MCP returns a malformed response, the orchestrator fails closed and the artifact path records the sanitized request + failure mode. Test path: `tests/integration/test_fallback.py::test_malformed_response_blocks_and_artifact_sanitized`.
- [ ] Adapter contract test suite passes with stub transport; coverage ≥ 80% for new `MCPAdapter` / `mcp_clients` integration code. Test path: `pytest tests/harness/test_mcp_adapter.py --cov=harness/services/mcp --cov-report=term-missing`.
- [ ] No regression: all Fase 0/1 tests pass; `Orchestrator.__init__` signature unchanged (PR #2 only adds an optional `mcp_clients` arg with default `None`); `OrchestratorDependencies` backward-compatible (PR #2 adds an optional `mcp_clients` slot that defaults to an empty `MappingProxyType`).
- [ ] MCP invocations observable: every MCP call produces a step entry with `{tool, transport, latency_ms, status, gate, adapter_id, error_class, sanitized_request, path}`. Test path: `tests/integration/test_resolution.py::test_step_entry_shape`.
- [ ] No secrets persisted in `state.yaml`, `OrchestratorResult`, or artifacts — `tests/security/test_secret_detector.py` (or equivalent) enforces by injecting a fake `OPENAI_API_KEY` env var, running a fixture adapter, and asserting that no string starting with `sk-` or matching common API-key regexes appears in any emitted field.
- [ ] Adding a new MCP adapter requires zero changes to `Orchestrator` — only builder registration (`orchestrator_builder.py`) and a config entry in `.paper-writer/mcp.yaml`. Test path: `tests/harness/test_orchestrator_builder.py::test_adding_adapter_does_not_change_orchestrator_init_signature`.

---

## 14. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| MCP transport flakiness (stdio subprocess crashes, timeouts, partial responses) | High | High | Stub transport in CI; fail-closed default; explicit `fallback: local` opt-in; structured `error_class` field for triage. |
| Credential leakage via logs / `state.yaml` / artifacts | Medium | Critical | `SecretDetector` utility at three checkpoints; CI linter that fails when `state.yaml` or any emitted artifact contains a high-entropy string; env-var-only storage in v1; `.gitignore` rules for `.paper-writer/mcp.local.yaml`. |
| Fallback masking real issues (MCP down repeatedly, user never notices) | Medium | High | Fallback always emits a `warning` (not silent); one-line summary appends `(FALLBACK TRIGGERED)`; CI rule can grep for it. |
| Schema drift between local validator output and MCP adapter output (different `findings` shapes) | High | Medium | `ValidatorResult` is the only return type; MCP adapter is responsible for translating its raw response into `ValidatorResult`; integration tests assert shape equivalence for at least one P0 tool. |
| Cost — MCP calls have per-call $ | Medium | Medium | Per-adapter timeouts (Q5) cap blast radius; per-adapter request rate cap (configurable, default 10/min) prevents runaway scripts; cost warning logged when adapter config has no `timeouts:` block. |
| Lock-in to a specific vendor's MCP schema (e.g., Robin's exact request shape) | Medium | Medium | Adapter subclasses per vendor; orchestrator sees only `ValidatorResult`; switching vendors = new adapter class + new `.paper-writer/mcp.yaml` entry. No vendor code in `Orchestrator` or `OrchestratorBuilder`. |
| Resolution layer cognitive complexity (precedence + invariants + CLI flag overlay) grows over time | Medium | Medium | ADR-2 documents the precedence once; `_resolve_tool` is the single function; docstring + test coverage freeze the behavior. |
| Probe call at command start adds latency even when no MCP is configured | Low | Low | Probe runs only against adapters declared in `.paper-writer/mcp.yaml`; absent config = no probe. |
| Schema-level rejection of `fallback: local` on MCP-only tools is too strict for early experimentation | Low | Low | Error message names the tool + the offending key; config author can either (a) write a thin local stub, or (b) open a discussion to add the tool to the local-exists list. |
| `OrchestratorDependencies` field proliferation (six fields after PR #2) | Low | Low | Frozen dataclass; no setter pattern; backward-compatible (new field defaults to empty `MappingProxyType`); test in `test_orchestrator_builder.py` enforces constructor signature stability. |

---

## 15. Post-Phase 2 (Fase 3+ handoff)

**Rule**: do NOT pre-design Fase 3 in this document. The plan intentionally leaves these questions open:

- `paper_reference_verify`, `paper_wiki_sync`, `paper_hypothesis_generate`, `paper_experiment_plan`, `paper_repro_audit` — all P1/P2 from `mcp-tools-candidates.md`. Their schemas, gate mappings, and fallback policies are **out of scope** for Phase 2.
- HTTP/SSE transports (Q7) — when the first HTTP-based MCP appears, the spec for that transport goes in a new plan.
- Keychain integration (Q8) — defer until at least one P0 tool has a real production deployment where env-var management becomes a friction point.
- Agentic loops, LLM-in-the-loop orchestration, claims ledger, evidence map (Phase 1 §8 parked features) — Fase 3+ is a separate spec; this document only marks the integration point (the `MCPAdapter` contract and the resolution layer) and does not pre-design the consumers.

**Reference**: see `phase-1-plan.md` §8 for what was already parked from Phase 1. Anything in that list that Phase 2 enables is a Fase 3+ decision, not a Phase 2 decision.

---

## 16. Decisions

- **2026-06-02 — Q1 LOCKED**: Reuse `ToolWrapper` as the MCP adapter contract. No new port. `Orchestrator` is unchanged. `OrchestratorDependencies` gains an `mcp_clients: MappingProxyType[str, MCPAdapter]` slot. Rationale: keeps the orchestrator simple, leverages the existing `_run_wrapper_gate` fail-closed path, and avoids the cost of a sibling port.
- **2026-06-02 — Q2 LOCKED**: Resolution policy lives in `.paper-writer/mcp.yaml` (per-tool section) with a CLI flag override and a static invariant fallback. Precedence: CLI > config > invariant. Rationale: three layers is the minimum that supports both ops-style YAML and per-invocation experimentation.
- **2026-06-02 — Q4 LOCKED**: Fail-closed default. Opt-in `fallback: local` for tools that have a local path. MCP-only tools always fail-closed (schema rejects the `fallback` key). Rationale: silent fallback hides outages; explicit fallback is auditable.
- **2026-06-02 — Q9 LOCKED**: v1 is plumbing only (PR #1–#4). `paper review` is PR #5, follow-up. Rationale: smaller blast radius per PR; plumbing validated before composition.

---

## 17. Further considerations

1. **Cognitive complexity in `_run_wrapper_gate`**: when PR #2 lands, the function already handles local + MCP subclasses of the same port. The further refactor in `plan-extract-cli-wiring-builder.prompt.md` §Further Considerations #2 still applies — extract the resolution-and-dispatch logic into a `ResolutionGateRunner` if it exceeds 60 lines or grows more than one new branch. Track this in a follow-up plan; do not pre-design here.
2. **Sub-orchestrator for `paper review`**: PR #5 may need a `ReviewSubOrchestrator` that composes the orchestrator with the extracted Fase 0 services. This is a v1 follow-up, not a v1 deliverable. Track the decision once PR #4 lands and the integration surface is observable.
3. **Cost dashboard**: per-adapter call counts and approximate cost belong in a future observability plan. Out of scope for Phase 2.
4. **Multiple-`paper review` profiles**: when Fase 3 adds per-journal profiles, the resolution layer must be re-runnable with a profile overlay. The CLI flag already supports this; the config schema may need a `profiles:` section. Out of scope for Phase 2; note in `phase-1-plan.md` §8 successor.
5. **Adapter versioning**: v1 has no concept of an adapter protocol version. When a vendor breaks their schema, the integration test will fail loudly; the fix is a new adapter subclass. A formal `MCP_PROTOCOL_VERSION` handshake belongs in a follow-up.

---

## 18. Relevant files

- `harness/ports/tool_wrapper.py` — `ToolWrapper` ABC, `ValidatorResult`, `ToolNotAvailableError`. The contract.
- `harness/services/orchestrator.py` — `Orchestrator`, `OrchestratorRequest`, `OrchestratorResult`, `_run_wrapper_gate` (the integration surface that MCP adapters plug into without modification).
- `harness/services/orchestrator_builder.py` — `OrchestratorDependencies` (DI container), `build_orchestrator_dependencies` (factory). PR #2 extends this with the `mcp_clients` slot.
- `cli/paper/main.py` — entrypoint. **Refactor target for PR #1** (lines 54–167 contain inline Fase 0 command bodies). Becomes pure dispatch after PR #1.
- `validators/prose.py`, `validators/claims.py`, `validators/method_gate.py` — Fase 0 validators. PR #1 moves the **command bodies** (not the validators themselves) to `harness/services/audit/`. Validators stay where they are.
- `harness/adapters/filesystem_action_runner.py` — artifact emitter. PR #4 wires the `SecretDetector` into its `emit_*` methods.
- `harness/services/assembler.py` — currently unrelated manuscript assembler. **Do not overload** with MCP wiring; keep concerns separate (per `plan-extract-cli-wiring-builder.prompt.md` §Further Considerations #1).
- NEW: `harness/services/mcp/adapter.py` — `MCPAdapter(ToolWrapper)` concrete class.
- NEW: `harness/services/mcp/config.py` — `.paper-writer/mcp.yaml` loader + schema validation.
- NEW: `harness/services/mcp/schema.py` — Pydantic models for `MCPConfig`, `MCPResolverConfig`, `MCPAdapterConfig`.
- NEW: `harness/services/mcp/probe.py` — JSON-RPC `initialize` probe.
- NEW: `harness/services/mcp/transports/stdio.py` — stdio JSON-RPC transport.
- NEW: `harness/services/mcp/responses.py` — Pydantic models for raw MCP responses (Q6 default).
- NEW: `harness/services/mcp/errors.py` — JSON-RPC error classes; `TransportDown`, `Timeout`, `SchemaMismatch`, `AuthFailure`, `RateLimited`.
- NEW: `harness/services/mcp/sanitization.py` — `SecretDetector` utility.
- NEW: `harness/services/audit/__init__.py` + `prose.py` + `claims.py` + `method_gate.py` — PR #1 refactor target.
- NEW: `.paper-writer/mcp.yaml` — resolver config (gitignored if it contains operational data; canonical config in repo for tests).
- NEW: `tests/harness/test_mcp_adapter.py` — adapter contract tests.
- NEW: `tests/integration/test_resolution.py` — resolution layer tests.
- NEW: `tests/integration/test_fallback.py` — fallback semantics tests.
- NEW: `tests/security/test_secret_detector.py` — secret-leak prevention tests.
- MODIFY: `tests/harness/test_orchestrator_builder.py` — backward-compatibility assertion (PR #2).
- MODIFY: `tests/cli/test_cli_phase0_regression.py` — PR #1 regression test (add if not present; assert CLI output unchanged for prose/claims/method).

---

## 19. Verification

Run, in order, after every PR lands. All must pass for v1 to be considered done.

1. `pytest tests/harness/ -v` — orchestrator + builder tests green (no regression in `_run_wrapper_gate`, `Orchestrator` constructor, `OrchestratorDependencies` shape).
2. `pytest tests/validators/ -v` — Fase 0 validators (post-PR #1 refactor) green.
3. `pytest tests/harness/test_mcp_adapter.py -v` — adapter contract with stub transport; coverage ≥ 80% (`--cov=harness/services/mcp`).
4. `pytest tests/integration/test_resolution.py -v` — resolution layer with config; CLI flag > config > invariant precedence verified.
5. `pytest tests/integration/test_fallback.py -v` — fallback semantics: MCP down → fail-closed for MCP-only; MCP down → local + warning for `fallback: local`; malformed response → blocker + sanitized artifact.
6. `python -m paper review --manuscript tests/fixtures/sample.md --mcp-resolver=paper_claim_audit=stub` — E2E smoke run. **Note**: requires PR #5 to exist. Pre-PR-5, this command does not exist; the equivalent smoke for v1 is `python -m paper audit claims --output json <file>` with `--mcp-resolver=paper_claim_audit=stub` accepted (and ignored) by the CLI parser.
7. `grep -rn "secret\|password\|token" .paper-writer/mcp.yaml` (when the file exists) — must return empty. `SecretDetector` covers the runtime path; this command covers the repo path.
8. `ruff check harness/ cli/` — static analysis clean (no new warnings on changed files).
9. `mypy harness/` — type check clean (PR #2's new modules have full annotations; the `mcp_clients` field in `OrchestratorDependencies` is `MappingProxyType[str, MCPAdapter]` with `MCPAdapter` exported from `harness.services.mcp.adapter`).
10. `python -m paper doctor` — environment check; should report MCP adapter count (`0 configured, 0 reachable` is the v1 default).
11. `pytest tests/security/test_secret_detector.py -v` — secret-leak prevention: fake `OPENAI_API_KEY` env var, run fixture adapter, assert no high-entropy string in any emitted field (state, steps, artifacts, log lines).
12. `python -c "from harness.services.orchestrator_builder import OrchestratorDependencies; import inspect; sig = inspect.signature(OrchestratorDependencies); assert 'mcp_clients' in sig.parameters"` — `OrchestratorDependencies` has the new `mcp_clients` field with a default (backward-compat check).
