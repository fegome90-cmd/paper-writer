# Paso 0 Baseline — Trifecta Feature Audit on paper-writer

> **Date**: 2026-06-02 | **Status**: COMPLETE

## Resumen

Corrimos TODAS las features de Trifecta sobre paper-writer. Resultado: **el graph gana 4/5 queries contra el Oracle**. El Oracle sin LSP es una versión débil. Hay features valiosas que no usamos (impact, callers, hubs). `ctx.calibrate` y `ctx.plan` no están operativos.

## 1. Oracle vs Graph Search — 5 Queries

| Query | Oracle (LSP+AST+PRIME) | Graph Search | Ganador |
|-------|----------------------|-------------|---------|
| orchestrator stages | ORCHESTRATOR_SPEC.md (docs) | Orchestrator class + builder | **Graph** |
| bibliography validation | validate_bibliography + chunks | bibliography.py + BibliographyNormalizer | **Oracle** (combined) |
| save state to disk | save_state, StateManager | state.py, state_repository.py | **Tie** |
| render markdown to docx | synthesis-protocol.md (WRONG) | PandocRenderer, _build_command | **Graph** |
| doctor checks tools | TestDoctor* classes (NOISE) | doctor.py, ToolStatus | **Graph** |

**Graph gana 4/5.** Oracle gana 1/5 (bibliography) porque combina AST symbols + text chunks.

### Key finding: Oracle sin LSP es "fallback"

Todos los resultados muestran `"fidelity": "fallback", "lsp_data": null`. Sin LSP daemon:
- Oracle = AST symbols + PRIME chunks
- No hay type resolution, no hay definition jumping, no hover
- El graph ya hace lo que Oracle hace sin LSP, pero mejor (structured edges vs text matching)

## 2. Graph Overview — paper-writer

| Metric | Value |
|--------|-------|
| Nodes | 1,058 |
| Edges | 994 |
| Cycles (calls) | 0 |
| Cycles (imports) | 0 |
| Orphans | 676 (63% total), 67 non-test |
| Reachability | 1.8% |
| Avg path distance | 3.6 |
| Max path distance | 8 |

**Core spine**: `make_manuscript (30) → ManuscriptState (28) → ManuscriptParser (22)`

**0 ciclos** → arquitectura limpia, sin dependencias circulares.

### Top 5 Hubs (architectural keystones)

| Symbol | In-degree | File | Role |
|--------|-----------|------|------|
| make_manuscript | 30 | tests/validators/conftest.py | Test fixture |
| **ManuscriptState** | **28** | harness/domain/state.py | **Domain core** |
| **ManuscriptParser** | **22** | parsers/manuscript.py | **Parser core** |
| get_asset_path | 20 | harness/ports/assets.py | Asset resolver |
| _run | 20 | tests/e2e/test_smoke_e2e.py | Test helper |

**Highest risk**: make_manuscript (30 dependents). Si cambia, 30 test files se rompen.

### Comparison: paper-writer vs trifecta_dope

| Metric | paper-writer | trifecta_dope |
|--------|-------------|---------------|
| Nodes | 1,058 | 1,304 |
| Edges | 994 | 1,415 |
| Orphan % | 63% | 20% |
| Cycles | 0 | 2 (imports) |
| Reachability | 1.8% | 0.6% |

**paper-writer tiene 3x más orphans** porque usa Hexagonal Architecture (DI, ports, adapters). trifecta_dope es más procedural (CLI commands, use cases directos).

## 3. Graph Impact — Blast Radius

| Target | Upstream dependents | What changes affect |
|--------|--------------------|--------------------|
| **ManuscriptState** | **61** | Domain core — changing it affects adapters, services, ALL tests |
| **PandocRenderer** | **38** | Render pipeline — changing it affects orchestrator_builder + all render tests |

Esto es VALIOSO. Antes de hacer un refactor, `graph impact X` te dice exactamente qué se rompe.

## 4. Graph Callers — Call Traversal

`graph callers --symbol ManuscriptState` → 28 results, 3 production (load, execute, validate_state), 25 tests.

Esto es útil para:
- Antes de borrar una función: ¿quién la llama?
- Antes de cambiar una API: ¿cuántos callers debo actualizar?

## 5. ctx.stats — Usage Analytics

| Metric | Value |
|--------|-------|
| Total searches | 24 |
| Hits | 21 (87.5%) |
| Zero hits | 3 |
| Avg latency | 1.0ms |
| Top zero-hit | "integrations tools validator" |

87.5% hit rate. Los 3 zero-hits son queries mal formadas.

## 6. Features NO operativas

| Feature | Status | Razón |
|---------|--------|-------|
| `ctx calibrate` | **Not implemented** | `status: "not_implemented"` |
| `ctx plan` | **No PRIME features** | Returns "No features available" |
| `ctx oracle` (full) | **Degraded** | `"fidelity": "fallback"` — sin LSP daemon |
| `graph path` | **Ambiguous** | Needs unique symbol names, `main` fails |

## 7. Conclusiones y Decisiones para el Maproad

### Lo que vale la pena mantener

1. **Graph search** — Mejor que Oracle sin LSP para code navigation
2. **Graph callers/callees** — Útil para impact analysis antes de refactors
3. **Graph hubs** — Identifica keystones arquitectónicos
4. **Graph impact** — Blast radius real, no estimado
5. **Graph overview** — Health check rápido (cycles + orphans + hubs)

### Lo que NO vale la pena (por ahora)

1. **Oracle sin LSP** — Graph search lo hace mejor. Solo vale la pena si corremos LSP daemon.
2. **ctx.plan** — No funciona sin PRIME features, y paper-writer no tiene.
3. **ctx.calibrate** — No implementado.

### Decisiones para el maproad

1. **Priorizar DI-aware static (Paso 1) sobre coverage merge (Paso 3)**
   - 63% orphans en paper-writer son DI. Si resolvemos DI estáticamente, bajamos a ~20%.
   - Coverage merge agrega complejidad CI por marginal gain.

2. **No invertir en LSP daemon hasta Paso 4+**
   - Oracle sin LSP no supera graph search. El LSP sería para type inference, no para search.

3. **El impacto del Paso 0 en el maproad**
   - Paso 0 confirma que el graph ES la herramienta principal. No hay "silver bullet" en las features que no usamos.
   - La prioridad es mejorar el graph (edges más precisos), no agregar capas encima.

### Updated maproad priority

```
Paso 0: ✅ DONE — Baseline established
Paso 1: DI-Aware Static Analysis    (2 días) → resuelve 61% orphans
Paso 2: Decorator Resolution        (2 días) → +15% orphans
Paso 3: Coverage.py Merge           (3 días) → para código no testeado  
Paso 4: LSP + Type Inference        (4 días) → Oracle full fidelity
Paso 5: sys.monitoring              (6 días) → full runtime tracing
Paso 6: Continuous Daemon           (9 días) → self-improving
```
