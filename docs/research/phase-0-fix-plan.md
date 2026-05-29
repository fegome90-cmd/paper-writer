# Phase 0 Fix Plan — Contrato Arquitectónico

> **Fecha**: 2026-05-29
> **Origen**: Judgment Day audit — 6 CRITICAL, 7 WARNING, 4 SUGGESTION
> **Principio**: No se expande scope a Phase 1. No MCP, no LLM, no búsquedas, no nuevas features.

## Decisiones Contractuales

### 1. `Section` es dataclass, no dict
- `parsers/manuscript.py:Section` tiene atributos tipados (`heading: str`, `text: str`, etc.)
- Todo acceso debe ser `section.text`, no `section.get("text", "")`
- Las claves de `manuscript.sections` son `str` → `Section`, no `str` → `dict`

### 2. Keys internas de `manuscript.sections` son lowercase
- `ManuscriptParser._parse_sections` normaliza a lowercase en línea 138
- `SECTION_ALIASES` también usa lowercase
- Cualquier lookup runtime debe normalizar a lowercase antes de acceder

### 3. YAML pueden usar labels humanos, pero todo lookup runtime se normaliza
- Los archivos YAML (`rules/method_gate/*.yml`, `rules/claims/risk_by_section.yml`) pueden usar `"Methods"`, `"Abstract"`, `"Introduction"`
- Pero el código que hace lookup **siempre** pasa a lowercase antes de buscar
- Esto mantiene los YAML legibles para humanos sin romper el matching

### 4. `SourceMap.to_original()` espera offset del texto completo
- `to_original(offset)` asume que `offset` es un character position en `clean_text` completo
- Los matches en scopes parciales (section, sentence) deben sumar el offset base antes de llamar `to_original`

### 5. Debe existir una sola política oficial de dedup
- `engine/deduplicator.deduplicate_findings()` es la implementación SSOT
- `ProseValidator._deduplicate` y `ClaimsValidator._deduplicate_candidates` DELEGAN a `engine.deduplicator`
- Algoritmo correcto: sweep-line con tracking de extensión más allá del `last_end`
- No más de 1 implementación activa de dedup

### 6. Phase 0 detecta riesgos, no verifica verdad
- Findings de prose: candidatos a revisar manualmente
- Candidates de claims: detección basada en triggers léxicos, NO verificación semántica
- Method gate: fail-closed basado en presencia de secciones/keywords, NO validación de contenido

## Orden de Batches

| Batch | Foco | CRITICAL | WARNING/SUGGESTION |
|-------|------|----------|-------------------|
| 1 | Parser/source map | C6, C2 | W3, W2, S2 |
| 2 | Lookups y normalización | C1, C4 | W7, S4 |
| 3 | Findings, offsets, dedup | C3, C5 | W5, W6, W1 |
| 4 | Tests de regresión | — | S3 |
| 5 | Limpieza final | — | W1 (dead code) |

## Archivos Afectados

| Archivo | Batches |
|---------|---------|
| `parsers/source_map.py` | 1 |
| `parsers/manuscript.py` | 1 |
| `validators/method_gate.py` | 2 |
| `validators/claims.py` | 2, 3 |
| `validators/prose.py` | 3 |
| `engine/deduplicator.py` | 3 |
| `engine/matcher.py` | 5 (dead code) |
| `engine/registry.py` | 5 (dead code) |
| `rules/claims/risk_by_section.yml` | 2 |
| `rules/method_gate/*.yml` | 2 (sin cambios, solo normalización en runtime) |
| `cli/paper/main.py` | 2 |
| `schemas/method_gate.schema.json` | 2 (W4: removemos check_types no implementados) |
| `tests/validators/test_parser_manuscript.py` | 1, 4 |
| `tests/validators/test_prose_validator.py` | 3, 4 |
| `tests/validators/test_claims_validator.py` | 2, 3, 4 |
| `tests/validators/test_method_gate.py` | 2, 4 |
| `tests/validators/test_engine.py` | 5 |

## Criterio de Éxito

- [ ] C1: Method gate encuentra secciones con cualquier capitalización
- [ ] C2: Section.line_end refleja la última línea real (incluyendo blanks)
- [ ] C3: Prose section-scoped reporta línea/columna del texto completo
- [ ] C4: risk_by_section modifica riesgo según sección
- [ ] C5: Dedup no descarta findings que se extienden más allá del previo
- [ ] C6: iter_sentences mapea "World" a la W, no al espacio
- [ ] W1: Una sola implementación de dedup activa
- [ ] W2: Title Case headings son detectados
- [ ] W3: Preamble.line_end se actualiza
- [ ] W5: to_original no se llama 3 veces para el mismo offset
- [ ] W6: _detect_section no recalcula to_original por sección
- [ ] W7: CLI acepta todos los study types soportados por YAML
- [ ] S2: SECTION_ALIASES incluye study design, statistical analysis, limitations
- [ ] S3: Tests usan assertions específicas, no `>= 0`
