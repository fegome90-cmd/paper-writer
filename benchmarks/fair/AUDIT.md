# Fair Benchmark Audit Report

> **Auditor**: Self-audit (el mismo autor del benchmark)  
> **Date**: 2026-06-02  
> **Veredicto**: ⛔ RESULTADOS NO CONFIABLES — 12 bugs/sesgos detectados

## Executive Summary

El benchmark "fair" que construí para corregir los sesgos del estudio original **introduce sesgos nuevos** que son igualmente graves. Los resultados (CVR 0.58x, 57% bias reduction) **no son confiables** y no deberían citarse como evidencia sin las correcciones siguientes.

---

## BUGS CRÍTICOS (invalidan resultados)

### B1: Gold answer T-P1 incorrecta — mata TODOS los brazos
**Archivo**: `fixtures/synthetic_repo.py` línea ~442  
**Bug**: `gold_symbol: "DataProcessor.process"` pero la función se define como `def process(self, ...)`. Ningún brazo puede encontrar `"DataProcessor.process"` porque ese símbolo no existe como `symbol_name`.  
**Impacto**: Los 3 brazos reportan recall=0.00 en T-P1 synthetic. No mide nada.  
**Fix**: `gold_symbol: "process"` + filtrar por `gold_file`.

### B2: Runner hardcodea símbolos en vez de leer gold answers
**Archivo**: `runner.py` función `_run_arm_task`  
**Bug**: T-W1 hardcodea `"BaseTransformer"`, T-D2 hardcodea `"normalize"`. El paper-writer define `gold_descendants` para ToolWrapper pero el runner IGNORA el gold y busca BaseTransformer (que no existe en paper-writer).  
**Impacto**: T-W1 en paper-writer reporta 0.00 para RAG y Trifecta aunque AMBOS encontrarían las subclasses correctas si se usara el símbolo correcto.  
**Fix**: Leer el target class del gold dict, no hardcodear.

### B3: fibonacci no es orphan — gold answer incorrecta
**Archivo**: `fixtures/synthetic_repo.py` línea ~460  
**Bug**: `fibonacci` es recursiva (se llama a sí misma). El grafo tiene un self-edge. Por definición, una función recursiva NO es orphan — tiene al menos 1 caller (ella misma). Pero `gold_orphans` incluye fibonacci.  
**Impacto**: RAG/LSP reportan fibonacci como orphan (correcto por la definición de texto) pero Trifecta no lo reporta (correcto por la definición de grafo). El scoring penaliza a Trifecta por NO reportar algo que correctamente no es orphan.  
**Fix**: Eliminar fibonacci de gold_orphans o aclarar la definición.

### B4: Orphan scoring no penaliza falsos positivos no listados
**Archivo**: `runner.py` función `score_task` branch "orphan"  
**Bug**: `gold_false_orphans` solo tiene 2 entries (enrich, slugify). RAG devuelve 16 orphans (3 true + 13 false) pero solo 1 false positive es penalizado. Los otros 12 falsos orphans (main, __init__, validate_input, etc.) no están en `gold_false_orphans` y NO afectan el scoring.  
**Impacto**: RAG y LSP reportan recall=1.00 y precision alta a pesar de tener 80%+ de falsos positivos.  
**Fix**: Enumerar TODOS los false orphans en gold, o cambiar scoring a F1 contra ground-truth completa.

---

## SESGOS SIGNIFICATIVOS (distorsionan comparación)

### S1: "LSP" baseline es realmente GREP + pyright confirm
**Archivo**: `arms/lsp_baseline.py`  
**Problema**: pyright CLI NO expone goto-definition, find-references, o call hierarchy como herramienta programática. El brazo usa grep para todas las operaciones excepto find_definition (donde pyright solo verifica que el símbolo existe, no lo encuentra).  
**Impacto**: El brazo "LSP" es básicamente un segundo brazo grep con overhead de latencia. No representa lo que un IDE real ofrece. Esto **infla la ventaja de Trifecta** en latencia porque grep es más lento que un LSP real con cache.  
**Fix**: Renombrar a "grep_pyright" o implementar un cliente LSP real via JSON-RPC.

### S2: RAG baseline usa TF-IDF, no embeddings
**Problema**: El brazo RAG usa TF-IDF (bag of words). Un sistema RAG moderno usa dense embeddings (OpenAI, Cohere, sentence-transformers) que capturan semántica (sinónimos, paráfrasis).  
**Impacto**: En tareas semánticas (T-S1 "remove duplicates" vs "deduplicate"), TF-IDF falla donde embeddings tendrían éxito. Esto **infla la ventaja de Trifecta** en tareas semánticas (aunque Trifecta también falló).  
**Fix**: Agregar un brazo con sentence-transformers o vía API.

### S3: Trifecta search threshold demasiado alto para queries verbosas
**Archivo**: `arms/trifecta_arm.py` `search()`  
**Problema**: El threshold de 0.3 para token overlap es demasiado alto cuando la query tiene 7 tokens y solo 2 matchean symbol names. "architecture layers core plugins cli utils tests" → score 2/7 = 0.28 → filtrado.  
**Impacto**: Trifecta reporta 0.00 en T-D1 y T-A1 synthetic no porque no pueda resolver, sino porque el query artificial no se mapea a nombres de símbolos.  
**Fix**: Bajar threshold a 0.15, o tokenizar queries de forma más inteligente.

### S4: Tamaño de muestra aún insuficiente
**Problema**: 16 tareas por brazo (11 synthetic + 5 paper-writer). El estudio original tenía 10. No es una mejora suficiente para significancia estadística.  
**Impacto**: Un solo bug (como B2) cambia el resultado aggregate de forma desproporcionada.

---

## BUGS MENORES (afectan métricas secundarias)

### M1: RAG find_orphans hace substring matching
`if name in chunk["content"]` — `validate` aparece como substring de `invalidate`, `validated`, etc. Produce falsos negativos en orphan detection.

### M2: LSP find_callers no excluye definition correctamente
El check `f"def {name}"` en `content_line` falla cuando la línea es `async def {name}` o tiene decoradores.

### M3: Index time no incluye Trifecta indexing cost
Trifecta reporta `index_time_ms = 0` porque el grafo está precomputado. Pero la indexación real tomó tiempo en un paso anterior. Para ser justo, debería incluir el costo de indexación inicial.

### M4: Paper-writer tasks no tienen T-D1, T-W2, T-W3, T-S1, T-S2
Solo ejecutan 5 de las 11 categorías de tareas. El aggregate está sesgado hacia las tareas donde Trifecta peor funciona (weakness, architecture) porque esas son las que se incluyen.

---

## Conclusión de Auditoría

| Dimensión | Original | Este Benchmark | Veredicto |
|-----------|----------|----------------|-----------|
| Control | Straw-man (ciego) | 2 baselines débiles | Mejor, pero LSP es falso |
| Timeout | 300s restrictivo | Sin timeout | ✅ Corregido |
| Repos | 1 repo | 2 repos | Mejor, pero synthetic tiene bugs |
| Debilidades | No probadas | Probadas pero hardcoded | ⛔ Bug B2 invalida |
| Scoring | Subjetivo (0-5) | Objetivo (recall/precision) | ✅ Mejor método |
| Gold answers | No verificables | Verificables pero incorrectas | ⛔ Bugs B1, B3 |

### Recomendación

**NO citar los resultados (CVR 0.58x) como confiables.** Los 4 bugs críticos invalidan el aggregate. El benchmark es un buen FRAMEWORK que necesita:

1. Corregir gold answers (B1, B3)
2. Leer símbolos del gold dict en vez de hardcodear (B2)
3. Enumerar TODOS los false orphans o cambiar scoring (B4)
4. Renombrar LSP arm a "grep_pyright" (S1)
5. Agregar brazo con embeddings reales (S2)
6. Bajar search threshold o mejorar tokenización (S3)

El valor de este benchmark es el **framework de 3 brazos** y la **metodología de scoring objetiva**, no los resultados numéricos actuales.
