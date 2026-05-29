# paper-writer - AGENTS.md

> **Generated**: 2026-05-29 | **Governance**: Constitucion AI v1.1

## 🏛️ Gobernanza Agéntica

Este repositorio opera bajo la **Constitucion de Codigo Agentico v1.1**.
Source of Truth: `https://github.com/fegome90-cmd/constitucion-ai`

## Reglas

- Todo claim debe tener evidencia trazable o ser marcado como hipótesis
- Los method gates son fail-closed
- El orchestrador nunca llama subprocess directamente — usa ToolWrapper port
- Todos los tool wrappers retornan ValidatorResult
- Ningún cambio es real sin evidencia de ejecución