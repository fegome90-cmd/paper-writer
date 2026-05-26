---
version: 1.0.0
updated: 2026-05-22
purpose: External skills audit of 33 skills evaluated against Felipe's 12-point gate criteria
---

# Skills Audit — Literature Search Ecosystem

> **Fecha:** 2026-05-22
> **Objetivo:** Evaluar skills externas para integrar al stack de investigación FALP
> **Criterio de rechazo (Felipe):** Sin DOI/PMID, sin search string, sin dedup, sin evidence table, mezcla refs verificadas con inventadas, escribe conclusiones clínicas sin grading

---

## 📊 Resumen Ejecutivo

| # | Skill | Stars | ¿Para qué sirve? | Veredicto | Acción |
|---|-------|:-----:|-------------------|-----------|--------|
| 1 | K-Dense/literature-review | 19K | Búsqueda + revisión amplia (PubMed, arXiv, Semantic Scholar) | ⚠️ **BASE pero NO instalar ciegamente** | Extraer estructura metodológica |
| 2 | dsebastien/ai-skill-scholar | Nuevo | OpenAlex search + citations + literature review con state persistente | ✅ **MEJOR que K-Dense para búsqueda** | Integrar OpenAlex API y patrón de estado |
| 3 | luwill/research-skills | 478 | Workflow 7 fases, literature-scout + paper-analyst + survey-writer | ✅ **BUEN MODELO** de estructura multi-agente | Copiar literature matrix y coverage analysis |
| 4 | Aperivue/medsci-skills | 37 | Clinical reporting audit (STROBE, PRISMA, CONSORT, RoB 2, GRADE) | ✅ **MUY ÚTIL para calidad clínica** | Integrar check-reporting como sub-skill |
| 5 | AIPOCH/medical-research-literature-reader-pro | — | Lectura crítica de papers médicos, clasifica evidencia | ✅ **ÚTIL para appraisal** | Evaluar integración |
| 6 | K-Dense/scientific-critical-thinking | 19K | Evaluación metodológica, GRADE, Cochrane RoB | ✅ **COMPLEMENTA** medsci-skills | Combinar con Aperivue |
| 7 | kgraph57/paper-writer-skill | — | Escritura médica, templates PRISMA/GRADE/RoB | 🟡 **SOLO al final** | No tocar hasta tener evidence |
| 8 | Imbad0202/academic-research-skills | — | Suite completa: research + writing + review + citation-check | ⚠️ **Mega-suite, modularizar** | Extraer módulos útiles |
| 9 | SmartBibl.IA | — | Bibliotecas, OpenAlex, HAL/SUDOC, bilingüe | 🟡 **Interesante concepto** | Baja prioridad |
| 10 | ZoFiles | — | Zotero → Markdown, read-paper skill | ✅ **SI tenemos Zotero** | Futuro: cuando armemos Zotero |
| 11 | kerim/zotero-mcp-skill | — | Buscar en Zotero desde Claude | ✅ **SI tenemos Zotero** | Futuro |
| 12 | kerim/zotero-code-execution | — | Python code para filtrar Zotero (evitar contexto masivo) | ✅ **PATRÓN SANO** | Futuro |
| 13 | ShZhao27208/Aut_Sci_Write | — | arXiv/PubMed/WoS + PDF extract + Zotero sync + PPT | ⚠️ **Ambicioso, sin auditar** | Skip |
| 14 | Calix-L/awesome-latex-skills | — | LaTeX read/convert/polish | 🟡 **Solo si escribimos en LaTeX** | Futuro |
| 15 | DeerFlow (ByteDance) | — | Systematic review pero solo arXiv | ❌ **RECHAZADO** | No sirve para clínica |

---

## 🔍 Análisis Detallado por Skill

### 1. dsebastien/ai-skill-scholar — ⭐ RECOMENDADO

**Qué hace:** Búsqueda académica vía OpenAlex (250M+ works), sin API key, rate limit generoso (10 req/sec). Tiene 3 sub-skills:
- `scholar-search` — búsqueda con filtros (year, venue, concepts, min-citations, open-access)
- `scholar-citations` — forward/backward citation tracking
- `literature-review` — two-pass screening orchestrator

**Por qué es mejor que K-Dense para búsqueda:**
- OpenAlex > Semantic Scholar en rate limits reales (S2 429s constant)
- Stdlib Python only (no dependencies)
- Output JSON con arXiv ID, DOI, PMID, citation_count, open_access_pdf
- `--min-citations` flag para quality floor
- Patrón de estado persistente: state.json, candidates.json, shortlist.json

**Qué robar:**
- ✅ Patrón de estado persistente (poder pausar/reanudar búsqueda)
- ✅ OpenAlex como fuente primaria (ya lo tenemos en v1.2 pero sin CLI)
- ✅ Two-pass screening (primer filtro por abstract, segundo por full text)

**Riesgos:** Ninguno significativo. MIT license, stdlib only.

---

### 2. Aperivue/medsci-skills — ⭐ RECOMENDADO

**Qué hace:** Skills para investigación médica — hechas por un physician-researcher. 37 stars.

**Sub-skills relevantes:**
- `check-reporting` — Audita contra 33 guías: STROBE, STARD, TRIPOD, PRISMA, CONSORT, CARE, SPIRIT, AMSTAR 2, QUADAS-2, RoB 2, ROBINS-I, ROBIS, PROBAST, NOS, COSMIN
- Output: JSON con porcentaje de cumplimiento por guideline

**Por qué es crítico para nosotros:**
- Nuestra skill tiene scoring A-E pero NO evalúa risk of bias metodológico
- Para el formulario FALP, necesitamos poder decir "estos papers cumplen CONSORT, estos no"
- El check-reporting genera exactamente el tipo de evidence grading que Felipe exige

**Qué robar:**
- ✅ Lista de 33 reporting guidelines con criterios
- ✅ Output JSON con compliance score
- ✅ Risk of bias assessment (RoB 2, ROBINS-I, NOS)

**Riesgos:** Solo 37 stars — proyecto joven pero hecho por médico.

---

### 3. AIPOCH/medical-research-literature-reader-pro — ✅ ÚTIL

**Qué hace:** Lectura crítica de papers médicos desde PDF/DOI/PMID/título. No es un resumidor genérico:
- Clasifica tipo de evidencia (RCT, cohort, meta, etc.)
- Hace appraisal por track (terapia, diagnóstico, pronóstico, daño)
- Respeta límites de interpretación

**Por qué sirve:**
- Complementa nuestra skill (nosotros buscamos + rankeamos, este lee + critica)
- La lectura crítica es el paso DESPUÉS del ranking

**Qué robar:**
- ✅ Framework de appraisal por tipo de estudio
- ✅ Separación explícita finding vs interpretation vs recommendation

---

### 4. K-Dense/literature-review (19K stars) — ⚠️ BASE con reservas

**Qué hace:** Revisión bibliográfica completa con PubMed, arXiv, bioRxiv, Semantic Scholar.

**Problemas:**
- Obliga a generar figuras con scientific-schematics (innecesario para nosotros)
- Usa `parallel-cli search` como herramienta principal (no siempre disponible)
- No tiene scoring de calidad explícito
- No captura MeSH/DeCS
- Mezcla búsqueda con escritura (deberían ser fases separadas)

**Qué robar:**
- ✅ Estructura multi-fase (Planning → Search → Screen → Extract → Synthesize → Verify)
- ✅ PICO framework explicitado
- ✅ Citation verification workflow

---

### 5. luwill/research-skills (478 stars) — ✅ BUEN MODELO

**Qué hace:** Workflow académico multi-agente: literature-scout → paper-analyst → survey-director → survey-writer → quality-editor

**Sub-skills:**
- `literature-scout` — Búsqueda multi-fuente (Exa, ArXiv API, Semantic Scholar, Papers With Code)
- `paper-analyst` — Análisis profundo por paper
- `survey-director` — Coordina la revisión
- `survey-writer` — Escribe la revisión
- `quality-editor` — QA final

**Por qué es interesante:**
- Patrón multi-agente (separa roles)
- Literature matrix con coverage analysis
- Coverage targets: ≥5 mature categories, ≥2 emerging, 80% total

**Qué robar:**
- ✅ Literature matrix format (ya lo tenemos en v1.2.0)
- ✅ Coverage analysis con targets
- ✅ Search log tracking

**Problema:** Orientado a AI/ML (ArXiv-focused), no clínica.

---

## 🏗️ Stack Recomendado (Modular)

```
┌──────────────────────────────────────────────────┐
│              STACK INVESTIGACIÓN FALP              │
├──────────────────────────────────────────────────┤
│                                                    │
│  CAPA 1: BÚSQUEDA                                 │
│  ├── literature-search (nuestra skill v1.2.0)     │
│  ├── OpenAlex API (de ai-skill-scholar)           │
│  ├── Semantic Scholar API (ya integrado v1.2.0)   │
│  └── PubMed/PMC/LILACS (ya integrado v1.2.0)      │
│                                                    │
│  CAPA 2: SCREENING + RANKING                      │
│  ├── Scoring A-E (nuestro, con tests)             │
│  ├── Deduplication (nuestro, PMID/DOI/Levenshtein)│
│  ├── Citation verification gate (nuestro v1.2.0)   │
│  └── State persistence pattern (de ai-scholar) 🔜 │
│                                                    │
│  CAPA 3: LECTURA CRÍTICA                          │
│  ├── medical-research-literature-reader-pro 🔜     │
│  ├── check-reporting (de medsci-skills) 🔜         │
│  └── scientific-critical-thinking (K-Dense) 🔜     │
│                                                    │
│  CAPA 4: GESTIÓN DE REFERENCIAS                   │
│  ├── Zotero (SSOT) — futuro                       │
│  ├── zotero-mcp-skill — futuro                    │
│  └── BibTeX/RIS export — futuro                   │
│                                                    │
│  CAPA 5: ESCRITURA                                │
│  └── paper-writer-skill (SOLO al final) 🔜         │
│                                                    │
└──────────────────────────────────────────────────┘
```

## 🎯 Acciones Inmediatas (lo que integra AHORA)

| # | Acción | Fuente | Esfuerzo |
|---|--------|--------|:--------:|
| 1 | Integrar OpenAlex CLI pattern (scholar_search.py) | dsebastien/ai-skill-scholar | 1 hr |
| 2 | Agregar risk of bias checklist a ranking-criteria | Aperivue/medsci-skills | 30 min |
| 3 | Agregar appraisal framework por tipo de estudio | AIPOCH/reader-pro | 30 min |
| 4 | Implementar state persistence (candidates.json/shortlist.json) | dsebastien/ai-skill-scholar | 1 hr |

## 🔜 Acciones Futuras (cuando tengamos Zotero)

| # | Acción | Fuente |
|---|--------|--------|
| 5 | Instalar zotero-mcp-skill | kerim |
| 6 | Instalar ZoFiles read-paper | ZoFiles |
| 7 | Integrar paper-writer-skill para escritura final | kgraph57 |

---

**Gate mínimo (de Felipe):** Rechazar cualquier skill que no pueda producir los 12 puntos de trazabilidad.

---

**Generado:** 2026-05-22 | **Skill:** literature-search v1.2.0 | **Tipo:** External skills audit

---

## Anexo: K-Dense Skills Relevantes (Audit Detallado)

El ecosistema K-Dense (19K stars) tiene ~100+ skills. De estas, las relevantes para investigación clínica FALP:

### 🔬 scientific-critical-thinking — ✅ RECOMENDADO

**Qué hace:** Evaluación sistemática de rigor científico:
- Study design assessment (experimental/quasi-experimental/observacional)
- Internal/external/construct/statistical validity
- Control & blinding evaluation
- Measurement quality
- Bias identification (cognitive, selection, measurement, analysis)
- Statistical review (power, tests, assumptions, multiple comparisons)
- GRADE framework application
- Cochrane Risk of Bias assessment

**Por qué sirve para nosotros:**
- Nuestra skill tiene scoring A-E pero NO evalúa risk of bias
- K-Dense proporciona el framework completo de evaluación por estudio
- Complementa perfectamente con Aperivue/medsci-skills (check-reporting = ¿cumple guideline? vs critical-thinking = ¿es metodológicamente sólido?)

**Qué robar:**
- ✅ Bias taxonomy completa (confirmation, HARKing, publication, cherry-picking, p-hacking, outcome switching)
- ✅ Statistical review checklist (power analysis, test assumptions, effect size inflation)
- ✅ GRADE assessment methodology
- ✅ Cochrane RoB framework

**Problema:** Fuerza generación de figuras con scientific-schematics (innecesario). Ignorar esa parte.

### 📑 citation-management — ✅ ÚTIL (parcialmente)

**Qué hace:** Gestión de citas con:
- Búsqueda en Google Scholar + PubMed
- Extracción de metadata (CrossRef, PubMed, arXiv)
- Validación de citas
- Generación de BibTeX
- Detección de duplicados

**Por qué sirve:**
- Nuestro citation verification gate verifica pero NO gestiona formato bibliográfico
- La generación de BibTeX es útil para el formulario FALP
- CrossRef/DOI validation coincide con lo que ya tenemos

**Qué robar:**
- ✅ BibTeX generation workflow
- ✅ Duplicate citation detection
- ✅ Citation validation pipeline

**Problema:** Depende de scripts Python (`search_google_scholar.py`, `search_pubmed.py`) que no tenemos. Solo útil como referencia de workflow.

### 📋 clinical-reports — 🟡 FUTURO (cuando escribamos)

**Qué hace:** Escritura de reportes clínicos:
- Case reports (CARE guidelines)
- Diagnostic reports (radiology, pathology, lab)
- Clinical trial reports (ICH-E3, SAE, CSR)
- Patient documentation (SOAP, H&P, discharge summaries)
- Regulatory compliance (HIPAA, FDA, ICH-GCP)

**Por qué sirve:**
- Para la sección de resultados/discusión del formulario
- CARE guidelines si presentamos como case report
- Templates para estructura de manuscript

**Problema:** Demasiado temprano. Necesitamos la evidencia primero, luego escribimos.

### 🔍 bgpt-paper-search — 🟡 INTERESANTE (MCP)

**Qué hace:** Búsqueda de papers vía BGPT MCP server:
- Retorna 25+ campos por paper (methods, results, sample sizes, quality scores)
- Extrae datos del full-text, no solo abstract
- Structured data output
- Free tier: 50 searches/network

**Por qué sirve:**
- La extracción de full-text es exactamente lo que hacemos manualmente con web_fetch
- 25+ campos structured > nuestra extracción ad-hoc
- Quality scores automáticos

**Problema:**
- MCP server remoto (dependencia externa)
- Base de datos curada, no cobertura completa
- Free tier limitado (50 searches)
- No reemplaza PubMed/Semantic Scholar para búsqueda amplia

**Veredicto:** Complemento atractivo pero no crítico. Agregar como fuente opcional.

### 🚫 Skills K-Dense NO relevantes para nosotros

| Skill | Por qué NO |
|-------|------------|
| scientific-schematics | No necesitamos generación de figuras ahora |
| autoskill | Meta-skill para crear skills, no para investigación |
| adaptyv, aeon, anndata, arboreto, etc. | Bioinformática/genómica, no clínica |
| astropy, cirq, dask | Física/computación, no clínica |
| benchling-integration | Lab management, no investigación bibliográfica |
| deepchem, depmap, diffdock | Drug discovery computacional |
| dnanexus-integration | Genomics platform |
| consciousness-council | Filosofía de la mente |
| database-lookup | Lookup genérico |
| docx | Generación Word, futuro |

---

## 🔍 Auditoría de Skills Adicionales (Sesión 2026-05-23)

### 5. K-Dense/literature-review (Systematic Review) — ✅ APROBADO CON ADAPTACIÓN
*   **Qué hace:** Multi-phase workflow (Planning -> Search -> Screening -> Extraction -> Synthesis). Search via `parallel-web` (`parallel-cli search`) and domain APIs. Screening supports deduplication by DOI or title.
*   **Alineamiento con Gate Mínimo:** 
    *   Soporta PICO (Punto 1), bases/fechas (Punto 2), exact search strings (Punto 3) e inclusión/exclusión (Punto 4).
    *   Maneja deduplicación programática (Punto 7) y extracción detallada de limitaciones/COI (Punto 8).
    *   Utiliza Cochrane RoB 2 para RCTs, Newcastle-Ottawa Scale (NOS) para observacionales, y AMSTAR 2 para revisiones (Punto 9).
    *   *Visual obligatorio:* Exige generar 1-2 esquemas usando `scientific-schematics` (ej. diagramas de flujo PRISMA).
*   **Qué robar:** El checklist de extracción detallado de limitaciones, financiamiento y conflictos de interés, además de la obligatoriedad de diagramas de flujo PRISMA automatizados con Mermaid/Schematics.
*   **Ajuste necesario:** En la fase de síntesis final, se debe forzar la división estricta del Punto 10 (findings vs interpretation vs recommendation), que no viene detallado rígidamente en K-Dense.

### 6. K-Dense/paper-lookup — 🟡 ACEPTADO COMO UTILIDAD AUXILIAR (SUPPORTING)
*   **Qué hace:** Consulta de forma paralela las REST APIs de 10 bases de datos (PubMed, PMC, bioRxiv, medRxiv, arXiv, OpenAlex, Crossref, Semantic Scholar, CORE, Unpaywall).
*   **Alineamiento con Gate Mínimo:** Falla como skill independiente de revisión sistemática (no tiene PICO, screening, extracción ni bias assessment). Pasa solo en validación de IDs (Punto 6) y logs (Punto 12).
*   **Qué robar:** Su lógica de selección de base de datos según la query e identificador (PubMed para biomedicina, arXiv para física/CS, Unpaywall para PDFs abiertos, Crossref para metadatos/retractaciones).
*   **Uso FALP:** No se debe usar de forma directa para tomar decisiones, sino como un utilitario interno de bajo nivel que `literature-search` puede llamar para automatizar búsquedas o resolver identificadores.

### 7. paperzilla-skills — ❌ RECHAZADO
*   **Qué hace:** Herramienta propietaria/externa de feeds y monitoreo de RAG que lee recomendaciones y canonical papers de Paperzilla mediante su CLI (`pz`).
*   **Alineamiento con Gate Mínimo:** Falla rotundamente (no tiene PICO, search logs reproducibles, deduplicación ni evaluación de sesgo clínica).
*   **Veredicto:** Descartado para el pipeline de evidencia FALP. Solo útil para alertas rápidas a nivel de productividad personal.

