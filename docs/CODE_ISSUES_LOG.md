# Code Issues Log — paper-writer

Este log registra problemas críticos, deuda técnica y discrepancias detectadas durante la auditoría del sistema.

| ID | Severidad | Componente | Descripción | Estado |
|:---|:---|:---|:---|:---|
| ISSUE-001 | **Crítica** | `harness/domain/state.py` | `ManuscriptState.validate()` es código muerto. El dominio no valida su propia integridad estructural al ser cargado. | 🔴 Pendiente |
| ISSUE-002 | **Crítica** | `harness/services/state_manager.py` | `validate_state()`, `set_gate()` y `set_stage()` están desconectados o no se persisten correctamente. El sistema opera en memoria pero no garantiza la persistencia del flujo. | 🔴 Pendiente |
| ISSUE-003 | **Alta** | `harness/services/orchestrator.py` | El Orchestrator carga el estado mediante `load_state()` pero no invoca la validación, permitiendo operar con estados corruptos o inconsistentes. | 🔴 Pendiente |
| ISSUE-004 | **Media** | `docs/orphan-detection-use-cases.md` | Discrepancia mayor: la documentación menciona 566 huérfanos y un archivo `use_cases.py` que no existen en la versión actual del repositorio. | 🔴 Pendiente |
| ISSUE-005 | **Baja** | `integrations/tools/vale.py` | Densidad de orfandad alta en métodos internos (`_run_vale`, `_builtin_lint`). Probable falso positivo de Trifecta o falta de invocación explícita verificable. | 🟡 Investigando |
| ISSUE-006 | **Media** | `harness/services/gates.py` | `validate_render_passed` es código muerto. La verificación de la etapa de renderizado está implementada pero nunca se ejecuta en el pipeline. | 🔴 Pendiente |

---
*Log generado por Gemini CLI Agent mediante auditoría con Trifecta Context Engine.*
