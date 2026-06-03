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
| 1 | BACKLOG-001 | **Crítica** | Documentación | Alinear documentación con el comportamiento real del sistema, especialmente CLI, harness y flujo operativo. | `cli/paper/main.py`, `docs/tools/paper-cli.md`, `docs/HARNESS_AND_STATE_MACHINE.md`, `docs/REPO_ARCHITECTURE.md` | Pendiente | 🔴 Abierto |
| 2 | BACKLOG-002 | **Crítica** | State machine / Harness | Corregir la semántica de stages: stage `verified` renombrado a `rendered`. `paper verify` queda en `rendered` como no-op; la verificación real es el gate `ready_for_delivery`. | `harness/services/orchestrator.py`, `harness/domain/state.py`, `harness/adapters/yaml_repository.py` | **Completado** | ✅ Resuelto |
| 3 | BACKLOG-003 | **Alta** | Artifacts / Outputs | Diseñar y aplicar una nomenclatura seria de artifacts (`case_id`, `run_id` o timestamp) para evitar nombres genéricos y colisiones. | `harness/adapters/filesystem_action_runner.py`, `integrations/tools/pandoc.py`, `harness/services/gates.py` | Pendiente | 🔴 Abierto |
| 4 | BACKLOG-004 | **Alta** | Gobernanza documental | Definir qué documentos son source of truth, cuáles son design intent y cuáles son históricos. | `docs/REPO_ARCHITECTURE.md`, `docs/HARNESS_AND_STATE_MACHINE.md`, `docs/TESTING_STRATEGY.md`, `docs/tools/*` | Pendiente | 🔴 Abierto |
| 5 | BACKLOG-005 | **Media-Alta** | Observabilidad | Cablear logs estructurados por comando al flujo principal; `write_command_log()` existe pero no es columna vertebral del runtime. | `harness/adapters/filesystem_action_runner.py` | Pendiente | 🔴 Abierto |
| 6 | BACKLOG-006 | **Media** | Degraded mode | Hacer explícito en docs y contratos de gates cuándo degraded mode implica warning y cuándo implica fail-closed. | `harness/services/doctor.py`, `integrations/tools/bibtex_tidy.py`, `docs/PRODUCTION_READINESS.md` | Pendiente | 🔴 Abierto |
| 7 | BACKLOG-007 | **Media** | Testing / Docs | Reconciliar claims documentales con el estado real de tests y coverage reportado. | `docs/TESTING_STRATEGY.md`, `tests/`, salida real de `pytest --collect-only` | Pendiente | 🔴 Abierto |
| 8 | BACKLOG-008 | **Media-Baja** | CLI | Modularizar la CLI si la superficie sigue creciendo; hoy funciona, pero `cli/paper/main.py` concentra demasiado. | `cli/paper/main.py`, `docs/REPO_ARCHITECTURE.md` | Pendiente | 🔴 Abierto |

### Nota operativa

- **BACKLOG-002** está resuelto. El rename `verified→rendered` fue implementado y validado con 669 tests pasando, 0 fallando.
- Los artefactos versionados en `outputs/` pueden estar desalineados con `outputs/state.yaml` (que dice `stage: search`) ya que el repositorio fue usado para testing manual. Esto no es un bug de runtime.

### Observaciones de auditoría externa (2026-06-03)

Un agente externo auditó el repo y encontró las siguientes observaciones (ya resueltas o documentadas):

1. **verified vs rendered (RESUELTO)**: El dominio, orchestrator, tests y docs ahora usan consistentemente `rendered`. Legacy YAMLs con `stage: verified` se auto-upgradearon via `LEGACY_STAGE_MAP`.
2. **state.yaml vs artefactos (DOCUMENTADO)**: `outputs/state.yaml` versionado dice `stage: search` pero existen artefactos de etapas posteriores. Esto es ruido del repositorio de desarrollo, no un bug de runtime. Los artefactos reales se generan en tmp dirs durante E2E tests.
3. **SOFT_GATES sin cablear (CONOCIDO)**: `citation_verified` y `ethics_passed` tienen validadores en `gates.py` pero no están integrados al pipeline. Son scaffold para futuras integraciones, no código roto.
