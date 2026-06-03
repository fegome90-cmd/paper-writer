---
name: trifecta-mcp
description: >
  Use for code navigation, graph impact analysis, semantic search, and context validation via Trifecta MCP.
  Trigger: When navigating code, answering architectural questions, finding dead code, testing impact, or validating context packs.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Navigating a codebase dynamically (callers, path, impact).
- Searching for semantic knowledge (`ctx_search`).
- Hovering over a symbol to find types/signatures (`ast_hover`).
- Validating or indexing context packs (`ctx_validate`, `ctx_reindex_graph`).
- Troubleshooting code graph staleness.


## Gentle AI Governance

- **Evidence-First**: Every tool call must include the "evidence" field explaining the source of the fact.
- **Fidelity Monitoring**: Agents MUST check the `fidelity` field. If `degraded`, pivot to structural tools (`ctx_graph`).
- **Fail-Closed**: If a tool returns an error code (e.g., -32001 for LSP), do NOT hallucinate; report the limitation.
- **Spec-Anchored**: Use `ctx_plan` to verify the engineering path before mass modifications.

## Critical Patterns

- **Anti-Pattern (The "One-Tool MCP")**: DO NOT default to `ctx_oracle`. The Oracle is for broad, unspecific searches.
- **Structural Tools (ctx_graph)**:
  - Use `action="callers"` to find who calls a function before modifying it.
  - Use `action="callees"` to find what a function calls.
  - Use `action="subclasses"` or `parents` when tracing class inheritance.
  - Use `action="path"` to trace relationships between two specific symbols.
  - Use `action="orphans"` to detect dead code.
  - Use `action="impact"` to determine blast radius.
- **AST Tools**:
  - Use `ast_hover` to get immediate type signatures and docstrings.
  - Use `ast_analyze` to extract all symbols from a single file in ~10ms.
- **Context Tools**:
  - Use `ctx_search` for semantic queries (e.g., "where is state saved?").
  - Use `ctx_get` to retrieve full chunk contents once an ID is found.
  - Use `ctx_validate` to verify context pack health.
  - Use `ctx_reindex_graph` immediately after modifying `.py` files to prevent staleness.

## Commands

```bash
# This skill primarily relies on MCP tools, but CLI fallbacks include:
trifecta graph callers --symbol <symbol>
trifecta ctx search -q "<query>"
```

## Resources

- **Documentation**: See [references/guide.md](references/guide.md) for full usage scenarios.