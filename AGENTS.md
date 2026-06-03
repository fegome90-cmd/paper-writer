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
- Consulta `docs/trifecta-mcp-agent-guide.md` para evitar el anti-patrón "One-Tool MCP" y usar la herramienta exacta (callers, ast_hover, etc.) en lugar de depender solo de ctx_oracle.

## Skills

| Skill | Description | File |
|-------|-------------|------|
| `trifecta-mcp` | Code navigation and semantic search via Trifecta MCP | [SKILL.md](skills/local/trifecta-mcp/SKILL.md) |
