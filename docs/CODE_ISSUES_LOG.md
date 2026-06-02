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

---
*Log generado por Gemini CLI Agent mediante auditoría con Trifecta Context Engine.*
