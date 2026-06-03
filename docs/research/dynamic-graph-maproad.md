# Trifecta Dynamic Graph Integration — Maproad

> **Date**: 2026-06-02 | **Status**: DRAFT | **Owner**: Felipe  
> **Scope**: trifecta_dope graph indexer + paper-writer validation

## 0. Contexto — Qué tiene Trifecta HOY

Trifecta es MUCHO más que un graph estático. El ecosistema tiene 3 capas:

```
┌─────────────────────────────────────────────────┐
│                  ORACLE (L3)                     │
│  Unified Intelligence: LSP + AST + PRIME        │
│  ctx oracle --query "..." --segment .            │
├─────────────────────────────────────────────────┤
│              CONTEXT PACK (L2)                   │
│  Chunked text search, PRIME index, aliases       │
│  ctx build → ctx search → ctx get                │
│  ctx plan (execution planning)                    │
│  ctx calibrate (weight auto-tuning)              │
├─────────────────────────────────────────────────┤
│               GRAPH (L1)                         │
│  AST-only: calls, imports, inherits              │
│  graph index/search/callers/callees/orphans      │
│  graph impact (blast radius) / path / hubs       │
│  graph cycles / overview (architectural health)  │
└─────────────────────────────────────────────────┘
```

**paper-writer usa**: ~20% de Trifecta (graph search + find_callers + find_orphans)  
**trifecta_dope self-analysis**: 1304 nodes, 1415 edges, **494 non-test orphans**

### Los 494 orphans de trifecta_dope — categorías

| Categoría | Count | Root Cause |
|-----------|-------|-----------|
| cli.py (CLI handlers) | 54 | Typer commands — registered by decorator |
| graph_store.py (methods) | 24 | Class methods — called via DI |
| ast_cache.py | 22 | Cache API — called from SkeletonMapBuilder |
| platform/registry | 17 | Platform layer — runtime binding |
| cli_graph.py (commands) | 16 | CLI subcommands — Typer registration |
| graph_service.py | 14 | Service methods — called via DI |
| result.py, segment_resolver.py | 26 | Dataclass/Protocol methods |
| Everything else | 321 | Mix of DI, callbacks, decorator patterns |

### Paper-writer: 67 non-test orphans — categorías

| Categoría | Count | % | Root Cause |
|-----------|-------|---|-----------|
| integration_methods | 27 | 40% | ToolWrapper protocol — DI via resolver |
| port_methods | 14 | 21% | Abstract interfaces |
| adapter_methods | 11 | 16% | Concrete implementations via DI |
| parser/engine | 5 | 7% | CLI-invoked, not graph-visible |
| domain_methods | 5 | 7% | Dataclass methods |
| other | 5 | 7% | Validators |

### Patrones que el AST jamás resuelve (medido empíricamente)

1. **DI/Protocol Dispatch** (61%): `self.tool.run()` → AST ve Attribute call, no PandocWrapper.run()
2. **Decorator Registration** (15%): `@app.command("status")` → Typer registra como handler
3. **Callback/Argparse** (10%): `set_defaults(func=X)` → partially fixed
4. **Plugin Loading** (8%): `importlib.import_module(name)` → nombre es variable
5. **Reflection/getattr** (6%): `getattr(obj, method)()` → imposible estáticamente

---

## 1. Capability Audit — Lo que YA tenemos y NO usamos

Antes de agregar dynamic graph, hay que verificar que usamos todo lo existente.

### Trifecta features sin explotar

| Feature | Comando | Valor | ¿Por qué no lo usamos? |
|---------|---------|-------|----------------------|
| **Oracle** | `ctx oracle` | LSP+AST+PRIME unified | No hay LSP daemon corriendo en CI |
| **Call graph traversal** | `graph callers/callees` | Impact analysis | Solo usamos search, no traversal |
| **Blast radius** | `graph impact` | Change risk assessment | Nunca integrado en pipeline |
| **Architectural health** | `graph overview` | Cycle/hub detection | Solo usamos orphans |
| **Context plan** | `ctx plan` | Execution planning | No tenemos PRIME calibrado |
| **Weight calibration** | `ctx calibrate` | Auto-tune search weights | Nunca ejecutado |
| **Telemetry** | `telemetry report` | Query analytics | No integrado |

### Acción inmediata: usar lo que ya existe

```
 Paso 0: Habilitar features existentes (1 día, ROI inmediato)
 ├─ Correr ctx oracle en paper-writer → medir vs graph search solo
 ├─ Correr graph impact en nodos críticos → validar blast radius
 ├─ Correr graph overview → detectar cycles
 └─ Correr ctx calibrate → auto-tunear weights
```

---

## 2. Maproad — Incremento de Complejidad, Decrecimiento de ROI

### Nivel 0: DI-Aware Static Analysis (1-2 días)

```
Complejidad: ★☆☆☆☆
ROI:         ★★★★☆
Risk:        ★☆☆☆☆
```

**Qué**: Analizar assignments en `__init__` y constructor para resolver DI patterns.

```python
# Detectar: self.tool = PandocWrapper(resolver)
# Cuando se ve: self.tool.run() → resolver a PandocWrapper.run()
```

**Cómo**:
1. Enhance `_resolve_file_targets` en graph_indexer.py
2. Parse constructor assignments: `self.X = ConcreteClass(...)`
3. En visit_Call con `self.X.method()`, lookup X → ConcreteClass → method

**Cubre**: 61% de orphans (DI/Protocol dispatch)  
**No cubre**: Decorators, plugins, reflection  
**Código**: ~150 líneas nuevas en graph_indexer.py  
**Schema**: Sin cambios (edge_kind="calls", source="ast_di")  

---

### Nivel 1: Decorator Call Resolution (2-3 días)

```
Complejidad: ★★☆☆☆
ROI:         ★★★★☆
Risk:        ★★☆☆☆
```

**Qué**: Resolver funciones registradas por decorators.

```python
@app.command("status")   # → status se registra como CLI handler
@dataclass               # → __init__, __post_init__ son callers
@pytest.fixture          # → fixture function se usa en tests
```

**Cómo**:
1. Detect decorator applications: `@decorator` sobre `def func`
2. Lookup decorator name en graph (app.command, dataclass, etc.)
3. Crear edge: decorator_module.caller → decorated_func

**Cubre**: 15% de orphans (decorator registration)  
**Código**: ~200 líneas nuevas  
**Schema**: edge_kind="decorated_by", source="ast_decorator"

---

### Nivel 2: Coverage.py Merge (2-3 días)

```
Complejidad: ★★★☆☆
ROI:         ★★★★★
Risk:        ★★☆☆☆
```

**Qué**: Usar coverage data como fuente supplemental de edges.

```
pytest --cov --cov-report=json
         ↓
  RuntimeEdgeExtractor → edges con source="coverage"
         ↓
  MERGE into graph.db
```

**Cómo**:
1. `uv add pytest-cov` en paper-writer
2. Correr tests con `--cov --cov-report=json`
3. Nuevo `CoverageEdgeExtractor`: parse JSON, map executed lines a nodes
4. Merge: `INSERT OR IGNORE` edges con `source="coverage"`, `confidence=frequency`

**Cubre**: P1 (DI) + P2 (callbacks) + P4 (reflection) — todo lo que los tests ejecutan  
**No cubre**: Código no testeado  
**Código**: ~200 líneas nuevas (extractor + merge)  
**Schema**: Sin cambios — ya tiene `source` y `confidence` columns  
**Ventaja**: Zero invasivo — no cambia producción, solo post-processing

---

### Nivel 3: Type Inference Overlay (3-5 días)

```
Complejidad: ★★★★☆
ROI:         ★★★☆☆
Risk:        ★★★☆☆
```

**Qué**: Usar pyright type analysis para resolver DI sin runtime.

```python
# pyright infiere: self.tool: PandocWrapper
# Donde self.tool.run() → PandocWrapper.run()
```

**Cómo**:
1. Correr pyright con `--outputjson`
2. Parse type assignments y parameter types
3. Crear edges: caller → inferred_type.method

**Cubre**: DI resolution sin tests  
**No cubre**: Monkey-patching, dynamic imports  
**Código**: ~500 líneas (type analysis bridge)  
**Schema**: edge_kind="calls", source="type_inference", confidence=0.8  
**Riesgo**: pyright es lento (5-30s), requiere types, puede ser impreciso

---

### Nivel 4: sys.monitoring Runtime Tracer (5-7 días)

```
Complejidad: ★★★★★
ROI:         ★★★☆☆
Risk:        ★★★★☆
```

**Qué**: Trace directo de ejecución usando Python 3.12+ sys.monitoring.

```python
import sys.monitoring as monitoring

def on_call(event, code, offset):
    # Captura CADA call en runtime
    record_edge(caller=code, callee=...)
    
monitoring.use_tool_id(sys.monitoring.DEBUGGER_ID, "trifecta")
monitoring.register_callback(SYS_MONITORING_EVENTS.CALL, on_call)
```

**Cómo**:
1. Crear `RuntimeTracer` que captura call events
2. Ejecutar test suite con tracer activo
3. Merge edges con `source="runtime"`, `confidence=1.0`

**Cubre**: TODO — runtime ve absolutamente todo  
**No cubre**: Código que no se ejecuta  
**Código**: ~300 líneas (tracer + merge + CLI integration)  
**Schema**: edge_kind="calls", source="runtime", confidence=1.0  
**Riesgo**: Invasivo, overhead en tests, solo Python 3.12+

---

### Nivel 5: Continuous Runtime Learning (7-10 días)

```
Complejidad: ★★★★★
ROI:         ★★☆☆☆
Risk:        ★★★★★
```

**Qué**: Background daemon que aprende edges de cada ejecución.

```
Trifecta daemon (already exists!)
    ↓
  Hook into sys.monitoring continuously
    ↓
  Build probabilistic edge graph over time
    ↓
  Confidence increases with frequency
```

**Cómo**:
1. Integrar tracer en daemon (daemon ya existe)
2. Cada ejecución del repo agrega edges al graph
3. Confidence = running frequency
4. Staleness decay: edges de versiones viejas bajan confidence

**Cubre**: Todo, con improving accuracy over time  
**Código**: ~500-800 líneas  
**Riesgo**: Complejidad de daemon, race conditions, storage growth

---

## 3. Recomendación — Sequencia de Ejecución

```
Paso 0: Usar lo que ya existe          (1 día)  → ROI inmediato
  ├─ ctx oracle en paper-writer
  ├─ graph impact en nodos críticos
  ├─ graph overview → detectar cycles
  └─ ctx calibrate → auto-tunear weights

Paso 1: DI-Aware Static Analysis       (2 días) → 61% orphans resueltos
  └─ Enhance _resolve_file_targets

Paso 2: Decorator Resolution           (2 días) → +15% orphans resueltos
  └─ Detect decorator→function edges

Paso 3: Coverage.py Merge              (3 días) → +20% orphans resueltos
  └─ pytest-cov → RuntimeEdgeExtractor → merge

Paso 4: Type Inference                 (4 días) → Para código no testeado
  └─ pyright output → TypeEdgeExtractor

Paso 5: sys.monitoring Tracer          (6 días) → Full coverage
  └─ Runtime tracer → merge con confidence

Paso 6: Continuous Learning Daemon     (9 días) → Self-improving
  └─ Daemon hook → probabilistic edges
```

### Proyección de orphans por paso

```
           paper-writer        trifecta_dope
           67 orphans          494 orphans
Paso 0:    67 (baseline)       494 (baseline)
Paso 1:    ~26 (-61%)          ~195 (-60%)
Paso 2:    ~16 (-76%)          ~120 (-76%)
Paso 3:    ~8  (-88%)          ~60  (-88%)
Paso 4:    ~5  (-93%)          ~35  (-93%)
Paso 5:    ~2  (-97%)          ~10  (-98%)
Paso 6:    ~0  (-100%)         ~0   (-100%)
```

---

## 4. Decisiones Pendientes

1. **¿Corremos Paso 0 antes de implementar nada?** — Hay features de Trifecta que no estamos usando. Quizás el Oracle ya resuelve el 80% sin tocar el graph.

2. **¿Coverage merge o DI-static primero?** — Coverage es más poderoso pero requiere CI integration. DI-static es más simple y cubre el 61%.

3. **¿Confidence model?** — Cuando mergeamos edges de múltiples fuentes:
   - `source="ast"` → confidence=None (determinístico)
   - `source="coverage"` → confidence=frequency (probabilístico)
   - `source="type_inference"` → confidence=0.8 (inferido)
   - `source="runtime"` → confidence=1.0 (observado)
   
   ¿Los queries filtran por confidence? ¿O muestran todo con metadata?

4. **¿Edge deduplication?** — Cuando AST y coverage ambos dicen A→B:
   - ¿Un edge con source="ast,coverage"?
   - ¿Dos edges separados?
   - ¿El edge más confiable gana?

5. **¿Graph versioning?** — Cuando el graph tiene edges dinámicos:
   - ¿Re-indexar borra edges de coverage?
   - ¿Merge incremental?
   - ¿Timestamps por edge?

---

## 5. Schema Impact

El schema ACTUAL ya soporta todo esto sin migration:

```sql
-- Already exists:
CREATE TABLE edges (
    id TEXT PRIMARY KEY,
    segment_id TEXT NOT NULL,
    from_node_id TEXT NOT NULL,
    to_node_id TEXT NOT NULL,
    edge_kind TEXT NOT NULL,        -- "calls", "imports", "inherits", "decorated_by"
    source TEXT NOT NULL,            -- "ast", "coverage", "type_inference", "runtime"
    confidence REAL                  -- NULL (deterministic) or 0.0-1.0 (probabilistic)
);
```

**No se necesita migration.** Solo agregar extractors y merge logic.
