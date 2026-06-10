# Code Issues Log — paper-writer

Este log registra problemas críticos, deuda técnica y discrepancias detectadas durante la auditoría del sistema.

| ID | Severidad | Componente | Descripción | Estado |
|:---|:---|:---|:---|:---|
| ISSUE-001 | **Crítica** | `harness/domain/state.py` | `ManuscriptState.validate()` estaba desconectado. Conectado en `StateManager.load_state()`. | ✅ Resuelto |
| ISSUE-002 | **Crítica** | `harness/services/state_manager.py` | La validación estricta impedía salvar estados iniciales incompletos. Arreglado mediante normalización en `ManuscriptState.__post_init__()`. | ✅ Resuelto |
| ISSUE-003 | **Alta** | `harness/services/orchestrator.py` | El Orchestrator carga el estado mediante `load_state()`. Ahora invoca la validación automáticamente al cargar, previniendo estados corruptos. | ✅ Resuelto |
| ISSUE-004 | **Media** | `docs/orphan-detection-use-cases.md` | Discrepancia documental resuelta añadiendo sección de "Auditoría Real Junio 2026" manteniendo el historial previo. | ✅ Resuelto |
| ISSUE-005 | **Baja** | `integrations/tools/vale.py` | Densidad de orfandad alta en métodos internos. Verificado: son falsos positivos de Trifecta; los métodos se invocan correctamente en `run()`. | ✅ Cerrado (FP) |
| ISSUE-006 | **Media** | `harness/services/gates.py` | `validate_render_passed` estaba desconectado. Conectado en `Orchestrator._run_gate_verification()`. | ✅ Resuelto |

| ISSUE-007 | **Alta** | `verification/run_real_validation.py` | Duplicación de lógica de gates y bootstrap. Resuelto importando `ManuscriptState` y delegando a `paper init`. | ✅ Resuelto |

## Backlog de correcciones priorizadas — Junio 2026

Este backlog registra los próximos puntos a corregir con prioridad explícita.
La regla es simple: no cerrar ningún punto sin evidencia en código, tests y/o docs alineadas.

| Rank | ID | Prioridad | Área | Descripción | Evidencia principal | Responsable | Estado |
|:---|:---|:---|:---|:---|:---|:---|:---|
| 1 | BACKLOG-001 | **Crítica** | Documentación | Alinear documentación con el comportamiento real del sistema, especialmente CLI, harness y flujo operativo. | `cli/paper/main.py`, `docs/tools/paper-cli.md`, `docs/HARNESS_AND_STATE_MACHINE.md`, `docs/REPO_ARCHITECTURE.md` | **Completado** | ✅ Resuelto |
| 2 | BACKLOG-002 | **Crítica** | State machine / Harness | Corregir la semántica de stages: stage `verified` renombrado a `rendered`. `paper verify` queda en `rendered` como no-op; la verificación real es el gate `ready_for_delivery`. | `harness/services/orchestrator.py`, `harness/domain/state.py`, `harness/adapters/yaml_repository.py` | **Completado** | ✅ Resuelto |
| 3 | BACKLOG-003 | **Alta** | Artifacts / Outputs | Per-run artifacts aislados en `outputs/runs/{run_id}/` con `outputs/latest/` symlink. `run_id` persistido en `outputs/.run_id`. Gates y wrapper usan `outputs/latest/`. Solo templates quedan como singletons. | `harness/adapters/filesystem_action_runner.py`, `harness/services/gates.py`, `harness/services/orchestrator.py` | **Completado** | ✅ Resuelto |
| 4 | BACKLOG-004 | **Alta** | Gobernanza documental | Clasificados 44 docs: 22 source-of-truth, 10 design-intent, 12 historical. Registro central en `docs/DOCUMENT_GOVERNANCE.md`. | `docs/DOCUMENT_GOVERNANCE.md` | **Completado** | ✅ Resuelto |
| 5 | BACKLOG-005 | **Media-Alta** | Observabilidad | Cablear logs estructurados por comando al flujo principal. `write_command_log()` ahora es parte del runtime del orchestrator. | `harness/adapters/filesystem_action_runner.py` | **Completado** | ✅ Resuelto |
| 6 | BACKLOG-006 | **Media** | Degraded mode | Semántica warn vs fail-closed documentada en todos los gate validators. | `harness/services/gates.py` | **Completado** | ✅ Resuelto |
| 7 | BACKLOG-007 | **Media** | Testing / Docs | Reconciliar claims documentales con el estado real de tests y coverage. Stale paths fixed. | `docs/TESTING_STRATEGY.md`, `tests/`, `docs/REPO_ARCHITECTURE.md` | **Completado** | ✅ Resuelto |
| 8 | BACKLOG-008 | **Media-Baja** | CLI | Modularizado: handlers extraídos a `cli/paper/commands/`. main.py 816→413 líneas (-49%). | `cli/paper/main.py`, `cli/paper/commands/` | **Completado** | ✅ Resuelto |

### Nota operativa

- **BACKLOG-002** está resuelto. El rename `verified→rendered` fue implementado y validado con 669 tests pasando, 0 fallando.
- Los artefactos versionados en `outputs/` pueden estar desalineados con `outputs/state.yaml` (que dice `stage: search`) ya que el repositorio fue usado para testing manual. Esto no es un bug de runtime.

### Observaciones de auditoría externa (2026-06-03)

Un agente externo auditó el repo y encontró las siguientes observaciones (ya resueltas o documentadas):

1. **verified vs rendered (RESUELTO)**: El dominio, orchestrator, tests y docs ahora usan consistentemente `rendered`. Legacy YAMLs con `stage: verified` se auto-upgradearon via `LEGACY_STAGE_MAP`.
2. **state.yaml vs artefactos (DOCUMENTADO)**: `outputs/state.yaml` versionado dice `stage: search` pero existen artefactos de etapas posteriores. Esto es ruido del repositorio de desarrollo, no un bug de runtime. Los artefactos reales se generan en tmp dirs durante E2E tests.
3. **SOFT_GATES cableados (RESUELTO)**: `citation_verified` wired via check_refs. `ethics_passed` checked as soft gate during verify command. Both validators now called from orchestrator `_run_gate_verification`.

## Backlog Progress — Junio 2026 (Session 2)

| ID | Severidad | Componente | Descripción | Estado |
|:---|:---|:---|:---|:---|
| GAP-003 | **Crítica** | `skills/imported/literature_search/scoring.py`, `scoring_cs.py` | PICO scoring daba 0.0 para papers CS. Creado `scoring_cs.py` con 5 dimensiones CS (venue, recency, citations, relevance, rigor). Domain dispatch en `_extract_metrics()`. 68 tests nuevos, 886 total, 0 regresiones. | ✅ Resuelto |
| LLM-001 | **Alta** | `clients/llm_content.py`, `drafting.py` | Creado cliente LLM subprocess (claude/codex/gemini). Integrado en drafting.py con opt-in explícito (`PAPER_LLM_CLI=claude`). 4 secciones generadas con calidad Q2 (4,941 palabras, 34 citas). | ✅ Resuelto |
| GAP-001 | **Crítica** | `templates/references.bib` | Bibliografía insuficiente (14 refs, need 40-80). Scoring arreglado (9/14 Tier 3), pero falta búsqueda iterativa (GAP-007). | 🟡 Parcial |
| GAP-002 | **Crítica** | `cli/paper/main.py`, `drafting.py` | 3 secciones faltan (abstract, lit_review, conclusion). Desbloqueado por GAP-003. | ❌ Pendiente |

## Bug Hunt Round 1 — Consensus Search Integration (Session 7, 2026-06-08)

Found by Ripper+Walker+Sniper adversarial agents via actual CLI execution.

| ID | Severity | Component | Description | Estado |
|:---|:---|:---|:---|:---|
| BH-1 | **Alta** | `skills/local/adapters.py` | Consensus filters silently ignored by non-Consensus providers. No warning to user. | ✅ Resuelto — warn log when filters ignored by non-Consensus provider |
| BH-2 | **Media** | `skills/local/adapters.py` | No CLI range validation for year_min/max, duration_min/max, sjr_max. Invalid ranges accepted silently. | ✅ Resuelto — adapter validates ranges before API call |
| BH-3 | **Media** | `cli/paper/main.py` | Empty/whitespace query accepted by search command. Wastes API call. | ✅ Resuelto — reject empty/whitespace queries |
| BH-4 | **Baja** | `cli/paper/main.py` | Non-existent raw_papers file path accepted, crashes at parse time with unhelpful error. | ✅ Resuelto — detect non-existent file before parse |
| BH-CRITICAL | **Crítica** | `skills/local/adapters.py`, ABC | `**kwargs` not in ABC or FixturePaperSearchProvider/McpPaperSearchProvider. Adapter filter forwarding crashed non-Consensus providers with TypeError. | ✅ Resuelto — added **kwargs to ABC and all 3 implementations |

## Bug Hunt Round 2 — Chain/Screen/Render Pipeline (Session 7, 2026-06-08)

Found by Ripper+Walker+Sniper adversarial agents on chain/screen/draft/audit/render commands.

| ID | Severity | Component | Description | Estado |
|:---|:---|:---|:---|:---|
| R2-BH1 | **Crítica** | `skills/imported/literature_search/chaining.py` | Paper titles with spaces crash S2 API (InvalidURL). `_encode_paper_id()` URL-encodes title fallbacks only; S2 hex IDs, DOI:, ArXiv: passed through. | ✅ Resuelto |
| R2-BH2 | **Alta** | `skills/imported/literature_search/search.py` | Invalid tier names in `screen()` silently default to Tier 3 instead of raising. | ✅ Resuelto — `ValueError` on invalid tier |
| R2-BH3 | **Alta** | `cli/paper/main.py` | Chain params not validated: `--max-rounds 0`, `--max-papers -1`, `--relevance-threshold 2.0` accepted. | ✅ Resuelto — bounds validation before orchestration |
| R2-BH4 | **Alta** | `harness/services/orchestrator.py` | No state snapshot/rollback on verify phase failure. Gates mutate without rollback on transient errors. | ✅ Resuelto — `copy.deepcopy` snapshot + restore on exception |
| R2-BH5 | **Media** | `integrations/tools/pandoc.py` | CSL/reference-doc validation emits warning but should be error. Non-existent files accepted without halting. | ✅ Resuelto — severity upgraded from `warning` to `error` |

### Judgment Day Review (Session 7, 2026-06-09)

Dual adversarial review of R2 bug fix diff. Round 1 found 2 confirmed WARNING (real):
1. Rollback crashes when snapshot is None — **fixed** with `if _pre_verify_snapshot is not None` guard.
2. `import copy` inside hot path — **fixed**, moved to module top-level.

Round 2 re-judgment: **APPROVED** — 0 CRITICAL, 0 confirmed WARNING.

### Preexisting Issues Noted (Not from R2 diff)

| ID | Severity | Component | Description | Estado |
|:---|:---|:---|:---|:---|
| PRE-1 | **Alta** | `cli/paper/main.py:463` | `from thesaurus.cli import ...` at module level inside `main()`. If thesaurus module missing, ALL paper commands break with `ModuleNotFoundError`. 74 CLI tests affected. | ✅ Resuelto — lazy import with try/except already in place |
