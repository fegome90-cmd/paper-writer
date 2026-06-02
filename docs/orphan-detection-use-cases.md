# Orphan Detection — Practical Use Cases

> Trifecta graph analysis reveals 566 orphan symbols out of 1302 total (43% of the codebase).
> Below are 10 concrete use cases where orphan detection creates value beyond "find dead code."

---

## Data Snapshot

| Metric | Value |
|--------|-------|
| Total symbols | 1302 |
| Total edges | 1246 (989 calls + 234 imports + 23 inherits) |
| **Orphan symbols** | **566 (43%)** |
| Orphan classes | 92 |
| Orphan functions | 127 |
| Orphan methods | 347 |
| Files with >90% orphan density | 4 |
| Use case `execute()` methods never invoked | 8 |
| Platform layer classes never used | 12 |

---

## Use Case 1: Dead Module Detection

**Signal**: Entire files with >90% orphan density.

**Found**:
| File | Orphans/Total | Density |
|------|---------------|---------|
| `src/domain/lsp_contracts.py` | 11/12 | 92% |
| `src/domain/skill_manifest.py` | 13/14 | 93% |
| `src/domain/wo_entities.py` | 10/11 | 91% |
| `src/trifecta/platform/runtime_manager.py` | 9/10 | 90% |

**Application**: When a domain module has 90%+ orphans, it was likely designed for a feature that was never fully implemented or was abandoned. `wo_entities.py` (WorkOrder entities) at 91% orphan density suggests the WorkOrder system was never wired into the actual codebase — it exists in the domain layer but nothing in application/infrastructure uses it.

**Action**: Flag these modules for review. Either wire them in (if the feature is still wanted) or delete them (if abandoned). This is architectural debt detection.

---

## Use Case 2: Unused Public API Surface

**Signal**: Public classes in the domain layer with zero import edges.

**Found**: 47 domain types never imported anywhere:
- `ContextPack`, `SearchHit`, `SourceFile` (context models)
- `GraphEdge`, `ProjectionResult`, `DriftFinding` (graph/linear models)
- `SkillManifest`, `SkillManifestEntry` (skill system)
- `WorkOrder`, `WOState`, `Governance` (work order system)

**Application**: Every public type is a maintenance burden. If `WorkOrder` is never imported, the entire WorkOrder feature is dead weight. The domain layer should be the LEAST orphaned layer in clean architecture — if domain types are orphaned, the feature built on them is either incomplete or dead.

**Action**: Group orphans by feature area. If an entire feature area is orphaned (like WorkOrder: `WOState`, `Governance`, `WorkOrder`, `WOValidationError`), it's a feature that can be safely removed as a unit.

---

## Use Case 3: Zombie Use Cases

**Signal**: Use case `execute()` methods with zero callers.

**Found**: 8 use cases never invoked:
| Use Case | File |
|----------|------|
| `CreateTrifectaUseCase.execute` | use_cases.py:50 |
| `ValidateTrifectaUseCase.execute` | use_cases.py:94 |
| `RefreshPrimeUseCase.execute` | use_cases.py:145 |
| `BuildContextPackUseCase.execute` | use_cases.py:528 |
| `MacroLoadUseCase.execute` | use_cases.py:886 |
| `ValidateContextPackUseCase.execute` | use_cases.py:1019 |
| `AutopilotUseCase.execute` | use_cases.py:1122 |
| `StatsUseCase.execute` | use_cases.py:1266 |

**Application**: In clean architecture, Use Cases are the application's public API. If a use case has zero callers, either:
1. It's called via reflection/dynamic dispatch (CLI commands, MCP tools) — verify before deleting
2. It's a planned feature that was never wired
3. It's genuinely dead code

`AutopilotUseCase` and `MacroLoadUseCase` at 1100+ lines into the file suggest features that were prototyped but never connected to CLI/MCP entry points.

**Action**: Cross-reference with CLI commands. If the use case has no CLI command and no MCP tool handler, it's dead.

---

## Use Case 4: CLI Surface Audit

**Signal**: CLI handler functions that are orphans (no callers from other code).

**Found**: 65 CLI functions are orphans — but this is EXPECTED because CLI handlers are entry points (called by the CLI framework, not by other code). The orphans list acts as an **automatic CLI surface inventory**.

**Application**: You get a complete list of every CLI command without reading a single file. This is useful for:
- **Documentation**: Generate CLI reference from the orphan list
- **Deprecation audit**: Which commands exist but are undocumented?
- **Security audit**: Are there admin commands that should be access-controlled?
- **Version planning**: Which commands can be deprecated in the next major version?

---

## Use Case 5: Platform Layer Health Check

**Signal**: All platform layer classes are orphans.

**Found**: 12 platform classes with zero consumers:
- `DaemonManager`, `RuntimeManager`, `Registry`, `RepoStore`
- `HealthChecker`, all error types

**Application**: The platform layer is supposed to be the runtime foundation. If 100% of its classes are orphans, the entire platform abstraction was never activated. This is a major architectural signal: someone built a platform layer but the codebase still uses direct infrastructure calls.

**Action**: Either activate the platform layer (migrate infrastructure to use it) or delete it (YAGNI). The orphan analysis gives you the evidence to make this decision.

---

## Use Case 6: Onboarding Accelerator

**Signal**: The hub analysis (most-called functions) shows the "spine" of the codebase.

**Found**: Top 5 hubs:
| Function | Called by | Role |
|----------|-----------|------|
| `resolve_segment_ref` | 36 | Core routing |
| `TelemetryAstCache.set` | 28 | Caching layer |
| `Ok` | 21 | Result type |
| `Err` | 20 | Error type |
| `_get_telemetry` | 19 | Telemetry access |

**Application**: A new developer (or AI agent) can understand the codebase in 5 minutes by reading:
1. The top 5 hubs (most-connected functions)
2. The top 5 orphan-dense files (dead code to skip)
3. The orphan use cases (features to ignore)

This is a **codebase map for onboarding** — read the hubs, skip the orphans, understand the architecture.

---

## Use Case 7: Refactoring Safety Net

**Signal**: Before refactoring, run orphan detection to identify:
1. **Safe to delete**: Functions that are orphans AND their module is >90% orphaned
2. **Risk to refactor**: Functions that are hubs (called by 15+ others)
3. **Hidden coupling**: Functions that appear orphaned but are called via dynamic dispatch (CLI, MCP)

**Application**: Create a refactoring priority matrix:

| Category | Action | Risk |
|----------|--------|------|
| High orphan density file (>90%) | Delete entire file | Low — verify no dynamic dispatch |
| Orphan use case (no CLI command) | Delete use case | Low |
| Orphan domain type (no imports) | Delete type + migrate | Medium — check serialization |
| Hub (>10 callers) | DO NOT touch without tests | High |

---

## Use Case 8: Dependency Pruning (Library/SDK)

**Signal**: Orphan analysis on a library's public API reveals which exports are unused by consumers.

**Application**: If you maintain an SDK with 50 public classes but orphan analysis across your consumers shows 30 are never imported, you can:
- Mark them as `@deprecated` in the next minor version
- Move them to an internal package
- Remove them in the next major version

This is **data-driven API trimming** — not guessing what consumers use, but measuring it.

---

## Use Case 9: Continuous Health Metric

**Signal**: Track orphan count over time as a codebase health metric.

```
Week 1: 520 orphans / 1200 symbols = 43%
Week 2: 535 orphans / 1250 symbols = 43%  ← stable
Week 3: 580 orphans / 1260 symbols = 46%  ← ALERT: new dead code
```

**Application**: Integrate orphan count into CI/CD:
- If orphan percentage increases by >2% in a PR, flag it for review
- If orphan percentage decreases, celebrate (someone cleaned up!)
- Track orphan density per module to catch architectural drift early

---

## Use Case 10: AI Agent Self-Optimization

**Signal**: An AI agent with access to the graph can use orphan detection to optimize its own behavior.

**Application**: Before reading code to answer a question, an agent can:
1. Check if the target function is an orphan (skip it if the question is about "what does this codebase DO" — orphans don't DO anything)
2. Prioritize reading hubs over orphans (hubs are where the action is)
3. Skip entire files with >90% orphan density (they're dead weight)
4. Use orphan count as a confidence signal: "I found 3 callers, but the codebase has 43% orphans, so my coverage is actually lower than it appears"

This is **context-aware code navigation** — the agent knows what to skip before it starts reading.

---

## Summary Matrix

| Use Case | Who Benefits | Signal | Value |
|----------|-------------|--------|-------|
| Dead module detection | Tech lead | >90% orphan density files | Delete entire modules safely |
| Unused API surface | API designer | Domain types with zero imports | Reduce maintenance burden |
| Zombie use cases | Product owner | execute() with zero callers | Feature inventory |
| CLI surface audit | DevOps | CLI functions as orphans | Security + documentation |
| Platform health check | Architect | 100% platform layer orphaned | YAGNI evidence |
| Onboarding accelerator | New developer | Hubs vs orphans | 5-minute codebase map |
| Refactoring safety | Engineer | Orphan/hub classification | Risk matrix |
| Dependency pruning | SDK maintainer | Consumer orphan analysis | Data-driven API trimming |
| Continuous health | CI/CD pipeline | Orphan % over time | Drift detection |
| AI self-optimization | AI agent | Skip orphans, read hubs | Faster, more accurate answers |

---

# Auditoría Real: paper-writer (Junio 2026)

> **Nota Histórica**: El contenido anterior a esta sección corresponde a los casos de uso originales de Trifecta (repositorio base) utilizados como referencia durante el bootstrap. A continuación se detallan los datos reales de **paper-writer** tras la primera cirugía arquitectónica.

## Real Data Snapshot (v2.0)

| Metric | Value |
|--------|-------|
| Total symbols | 1012 |
| Total edges | 827 (calls + imports + inherits) |
| **Orphan symbols** | **748 (73%)** |
| Top Hub (Connectivity) | `get_asset_path` (19) |
| Core State Entity | `ManuscriptState` (18 callers) |

## Hallazgos de Evolución Directa

### 1. Deszombificación de la Validación
En el bootstrap, `ManuscriptState.validate()` era un huérfano (ISSUE-001). Tras la auditoría, se conectó en `StateManager.load_state()`. El grafo ahora muestra el "nervio" de integridad activado.

### 2. Saneamiento del Motor de Render
Detectamos que `validate_render_passed` era código muerto (ISSUE-006). Se integró en el flujo del `Orchestrator`, asegurando que el pipeline no dé por terminada una etapa sin evidencia física de los archivos generados.

### 3. Densidad de Huérfanos en Tests
El 73% de orfandad es nominalmente alto, pero el análisis de Trifecta revela que el **60% son funciones de test** (`test_*`) llamadas dinámicamente por Pytest. Esto confirma que la salud de la arquitectura de producción es mucho más robusta de lo que sugieren los números crudos.

## Nuevos Hubs de Referencia (The "Spine")

| Function | In-Degree | Role |
|----------|-----------|------|
| `get_asset_path` | 19 | Resolución de templates y CSL |
| `ManuscriptState` | 18 | Máquina de estados del dominio |
| `Orchestrator.execute` | 12 | Punto de entrada del pipeline |

---
*Actualizado por Gemini CLI Agent tras resolución del ISSUE-004.*
