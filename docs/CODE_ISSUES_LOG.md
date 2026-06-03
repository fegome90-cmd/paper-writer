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
| 2 | BACKLOG-002 | **Crítica** | State machine / Harness | Corregir la semántica de stages: hoy `render` transiciona a `verified` antes de ejecutar `paper verify`, lo que hace que el nombre del stage sea engañoso. | `harness/services/orchestrator.py`, `harness/domain/state.py`, `docs/HARNESS_AND_STATE_MACHINE.md` | **Codex (tomado)** | 🟠 En análisis |
| 3 | BACKLOG-003 | **Alta** | Artifacts / Outputs | Diseñar y aplicar una nomenclatura seria de artifacts (`case_id`, `run_id` o timestamp) para evitar nombres genéricos y colisiones. | `harness/adapters/filesystem_action_runner.py`, `integrations/tools/pandoc.py`, `harness/services/gates.py` | Pendiente | 🔴 Abierto |
| 4 | BACKLOG-004 | **Alta** | Gobernanza documental | Definir qué documentos son source of truth, cuáles son design intent y cuáles son históricos. | `docs/REPO_ARCHITECTURE.md`, `docs/HARNESS_AND_STATE_MACHINE.md`, `docs/TESTING_STRATEGY.md`, `docs/tools/*` | Pendiente | 🔴 Abierto |
| 5 | BACKLOG-005 | **Media-Alta** | Observabilidad | Cablear logs estructurados por comando al flujo principal; `write_command_log()` existe pero no es columna vertebral del runtime. | `harness/adapters/filesystem_action_runner.py` | Pendiente | 🔴 Abierto |
| 6 | BACKLOG-006 | **Media** | Degraded mode | Hacer explícito en docs y contratos de gates cuándo degraded mode implica warning y cuándo implica fail-closed. | `harness/services/doctor.py`, `integrations/tools/bibtex_tidy.py`, `docs/PRODUCTION_READINESS.md` | Pendiente | 🔴 Abierto |
| 7 | BACKLOG-007 | **Media** | Testing / Docs | Reconciliar claims documentales con el estado real de tests y coverage reportado. | `docs/TESTING_STRATEGY.md`, `tests/`, salida real de `pytest --collect-only` | Pendiente | 🔴 Abierto |
| 8 | BACKLOG-008 | **Media-Baja** | CLI | Modularizar la CLI si la superficie sigue creciendo; hoy funciona, pero `cli/paper/main.py` concentra demasiado. | `cli/paper/main.py`, `docs/REPO_ARCHITECTURE.md` | Pendiente | 🔴 Abierto |

### Nota operativa

- **BACKLOG-002** queda tomado en este turno para análisis y propuesta de corrección.
- Antes de renombrar o mover stages, hay que verificar impacto en:
  - transición de `render`
  - `paper verify`
  - `outputs/state.yaml`
  - docs del state machine
  - tests CLI / harness / E2E
