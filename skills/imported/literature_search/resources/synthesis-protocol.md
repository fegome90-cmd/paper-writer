# Synthesis Protocol — Literature Search Skill

> **Purpose:** Fase 5 del pipeline. Transformar papers rankeados en texto de marco teórico con claims verificados.
> **Version:** 1.0.0 | **Created:** 2026-05-23
> **Depends on:** ranking-criteria.md (Phase 3), critical-appraisal.md (Phase 3)
> **Sources:** K-Dense `literature-review` Fase 5+6, luwill/research-skills literature matrix, auditoría FALP 2026-05-23

---

## Overview

El synthesis protocol es la **fase obligatoria** entre Export (Phase 4) y la redacción final del documento. Sin esta fase, el agente escribe claims basados en memoria o resúmenes incompletos, introduciendo errores de transcripción, inversión de conclusiones, y contexto poblacional incorrecto.

**Pipeline completo actualizado:**

```
Phase 1: Plan      → Definir pregunta, fuentes, criterios
Phase 2: Search    → Buscar, descargar, deduplicar
Phase 3: Rank      → Scoring A-E, tiering, quality appraisal
Phase 4: Export    → Database, ranking, matrix, thesaurus
Phase 5: Synthesize → ESTE DOCUMENTO (verificar + sintetizar + redactar)
```

---

## Phase 5.1: Pre-Synthesis Verification

**Antes de escribir una sola línea del marco teórico**, ejecutar verification gate para cada paper Tier 1-2.

### 5.1.1 Journal Metadata Cross-Check

Para cada referencia, verificar contra PubMed API o Semantic Scholar:

```
CHECKLIST PER REFERENCE:
□ Journal name → coincide con NLM catalog title?
□ Publication year → coincide con PMID/DOI?
□ Sample size (n=) → coincide con abstract/fulltext?
□ Study design → coincide con lo que vamos a claimar?
   (prospectivo vs retrospectivo, RCT vs observacional, cualitativo vs cuantitativo)
```

**Método:**
```bash
# PubMed API lookup
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=PMID&rettype=abstract&retmode=json"

# Semantic Scholar lookup
curl -s "https://api.semanticscholar.org/graph/v1/paper/PMID:XXXXX?fields=title,authors,year,venue,abstract,externalIds,citationCount"
```

**Error categories:**

| Error Type | Severity | Example |
|------------|:--------:|---------|
| Journal name incorrect | 🔴 Critical | "JAMA Otolaryngol" cuando es "European Psychiatry" |
| n= incorrect | 🔴 Critical | n=52.3% cuando es 92.3% |
| Study design incorrect | 🔴 Critical | "prospectivo" cuando es "retrospectivo" |
| Year incorrect | 🟡 Minor | 2022 cuando es 2021 |
| Author order wrong | ⚪ Cosmetic | "Smith et al." cuando es "Smith J, Jones K" |

### 5.1.2 Conclusion Direction Audit

Para claims sobre **dirección de efecto** (mejora/empeora/aumenta/disminuye):

```
MANDATORY CHECK:
□ ¿El paper reporta MEJORA o DETERIORO?
□ ¿El marco teórico claima la misma dirección?
□ Si hay subgrupos con direcciones diferentes → ¿cuál se claima?
□ ¿El n= del subgrupo coincide con lo claimado?
```

**Ejemplo de error detectado:** Mukoyama 2024 concluye "anxiety decreases" → marco teórico claimaba "sin mejoría espontánea" → **INVERSIÓN DE CONCLUSIÓN**.

### 5.1.3 Context Alignment Check

Para cada claim, verificar que la población del estudio sea relevante para la población objetivo:

```
CONTEXT GATE:
□ ¿Población del estudio = población objetivo del proyecto?
□ Si NO → ¿El claim incluye caveat explícito?
□ ¿La intervención del estudio = intervención relevante?
□ Si NO → ¿Se explica la extrapolación?
```

**Ejemplo de error detectado:** Bakia 2025 estudia reposo vocal agudo por patología benigna (edad media 36.4) → marco teórico lo presenta como evidencia para HNC oncológico → **CONTEXT MISMATCH** sin caveat.

**Formato de caveat obligatorio:**
```
"Si bien [Hallazgo del estudio] fue demostrado en [Población real del estudio],
[la brecha / la extrapolación / la necesidad de verificar en población oncológica]
requiere investigación adicional."
```

---

## Phase 5.2: Claim-to-Source Traceability Matrix

### 5.2.1 Registro Obligatorio

Cada afirmación con ≥1 dato estadístico, dirección de efecto, o conclusión de un paper debe ser registrada en una **traceability matrix**:

```markdown
| Claim # | Afirmación | Ref # | Fuente | Verificado | Status |
|---------|-----------|-------|--------|:----------:|:------:|
| 1 | 60.8% disartria post-HNC | Ref 5 | Won 2025, PM&R | ✅ | Correct |
| 2 | 57% problemas vocales post-TL | Ref 7 | Wulff 2022 | ✅ | Correct |
| N | ... | ... | ... | ⬜ | Pending |
```

### 5.2.2 Categorías de Verificación

| Status | Significado | Acción |
|:------:|-------------|--------|
| ✅ | Verificado contra fuente original | Incluir |
| ⚠️ | Verificado con discrepancia menor | Incluir con corrección |
| 🔴 | Verificado con discrepancia mayor | NO incluir hasta corregir |
| ⬜ | No verificado aún | NO incluir hasta verificar |
| 🔍 | No verificable (paywall, preprint) | Incluir con nota "[no verificado independientemente]" |

### 5.2.3 Regla de inclusión

**NINGÚN claim con status 🔴 o ⬜ puede incluirse en el documento final.**

Si un claim es 🔴:
1. Buscar la fuente original completa (fulltext vía PMC, Unpaywall)
2. Si no es accesible → reemplazar con claim de otro paper verificado
3. Si no hay reemplazo → eliminar el claim

---

## Phase 5.3: Literature Matrix (Coverage Analysis)

### 5.3.1 Estructura

Antes de redactar, construir una **literature matrix** que muestre cobertura por categoría:

```markdown
# Literature Matrix — [Topic]

## Overview
- Search date: YYYY-MM-DD
- Total collected: N papers
- After screening: N papers
- Tier 1 (primary): N | Tier 2 (supporting): N | Tier 3 (background): N

## Coverage by Category

| Category | Target | Found | Status | Core papers |
|-----------|:------:|:-----:|:------:|------------|
| Prevalencia alteración vocal HNC | ≥3 | N | ✅/⚠️ | [papers] |
| Impacto salud mental HNC | ≥3 | N | ✅/⚠️ | [papers] |
| Impacto participación social | ≥2 | N | ✅/⚠️ | [papers] |
| Rehabilitación vocal convencional | ≥2 | N | ✅/⚠️ | [papers] |
| Tecnología AAC/TTS | ≥2 | N | ✅/⚠️ | [papers] |
| Evidencia local (Chile/LatAm) | ≥1 | N | ✅/⚠️ | [papers] |
```

### 5.3.2 Gap Detection

Categorías con `⚠️` (found < target) requieren:
1. Búsqueda adicional específica en esa categoría
2. Si no se encuentra → documentar como "brecha identificada" en el marco teórico
3. La brecha puede ser parte de la justificación del estudio

---

## Phase 5.4: Writing Protocol

### 5.4.1 Estructura del Marco Teórico (3 secciones estándar FALP)

```
1. Definición del Problema
   - Contexto epidemiológico
   - Magnitud del problema (con datos verificados)
   - Brecha local

2. Análisis del Conocimiento Actual
   - Subsecciones por dimensión (funcional, mental, social)
   - Subsecciones por tipo de intervención
   - Brecha en el conocimiento

3. Justificación de la Investigación
   - Por qué es necesario
   - Qué va a aportar
   - Cómo se usa la evidencia
```

### 5.4.2 Reglas de Escritura

1. **Un claim = una fuente.** Cada afirmación factual debe tener exactamente una referencia verificada. Si múltiples papers respaldan el mismo claim, citar el de mayor tier.

2. **Direction words require verification.** Palabras como "mejora", "empeora", "aumenta", "disminuye", "persiste", "nunca", "siempre" requieren conclusion direction audit (5.1.2).

3. **Absolute claims require absolute evidence.** "Nunca se recupera" requiere que el paper diga exactamente eso. Si el paper dice "significantly impaired" → usar "no recupera completamente", no "nunca se recupera".

4. **Context qualifiers are mandatory.** Si el paper estudió población A y el claim se aplica a población B → incluir caveat explícito (ver 5.1.3).

5. **Statistics must be exact.** 92.3% no es 52.3%. p<0.0001 no es p<0.001. Si no se puede verificar el número exacto → usar "aproximadamente X%" o "alrededor de X%".

6. **Qualitative studies must state their scope.** n=4-6 estudios cualitativos deben indicar "estudio fenomenológico, n=4-6, muestra de saturación teórica". No presentar como evidencia poblacional.

7. **Qualitative findings must use original labels.** When citing phases, themes, or categories from qualitative studies, use the exact labels from the paper (e.g., "Not normal life", not "shock y pérdida"). If paraphrasing, explicitly mark as "[adapted]" or "[reinterpretación]" to distinguish interpretation from original wording.

### 5.4.3 Prohibiciones

| Prohibido | Por qué | Alternativa |
|-----------|---------|-------------|
| "El estudio demuestra que..." para estudios observacionales | Causalidad no demostrada | "El estudio reporta una asociación entre..." |
| Citar conclusión sin verificar dirección | Inversión de findings | Verificar con 5.1.2 |
| Usar statistic sin verificar contra fuente | Error de transcripción | Verificar con 5.1.1 |
| Mezclar populations sin caveat | Context mismatch | Agregar caveat con 5.1.3 |
| Presentar TTS genérico como solución final | Desactualizado | Usar "AAC inteligente", "síntesis personalizada", "bancos de voz" |

---

## Phase 5.5: Post-Synthesis Audit

### 5.5.1 Checklist Final

Después de completar el marco teórico, ejecutar:

```
POST-SYNTHESIS AUDIT:
□ Traceability matrix completa (todos los claims tienen ref#)
□ Todos los claims tienen status ✅ o ⚠️ (ningún 🔴 o ⬜)
□ Literature matrix cubre todas las categorías del tema
□ Journal names en formato NLM
□ Direcciones de efecto verificadas
□ Context mismatches identificados y con caveat
□ Estudios cualitativos con scope explícito
□ Bibliografía en formato estándar (Vancouver/APA)
□ Número de refs dentro del límite del formulario
□ Word count dentro del límite
```

### 5.5.2 Output

El deliverable de Phase 5 es:

```
apps/pae-wizard/outputs/research/
├── marco-teorico.md           ← Documento final verificado
├── claim-traceability.md      ← Matrix claim ↔ fuente
├── literature-matrix.md       ← Coverage analysis
├── verification-log.md        ← Log de verificaciones (fecha, método, resultado)
└── audit-report.md            ← Resumen de auditoría (errores encontrados, corregidos)
```

---

## Failure Modes and Prevention

| Failure Mode | Causa raíz | Prevención |
|-------------|-----------|------------|
| Inversión de conclusión | Agente lee resumen tercero, no abstract original | 5.1.2 Conclusion Direction Audit |
| Error de transcripción (92.3 → 52.3) | Agente opera desde memoria | 5.1.1 Metadata Cross-Check |
| Journal incorrecto | Nombre citado de oído | 5.1.1 Journal Name Verification |
| Context mismatch (benigno vs oncológico) | Agente no verifica población del estudio | 5.1.3 Context Alignment Check |
| Absolute claim sin evidence absoluta | Agente sobrerreporta para fortalecer narrativa | 5.4.2 Regla 3 (Absolute Claims) |
| Gap no detectado | Sin literature matrix | 5.3 Literature Matrix |
| Claim sin source traceability | Sin registro obligatorio | 5.2 Traceability Matrix |

---

## Integration with Existing Skill

```
SKILL.md (orchestrator)
├── Phase 1: Plan (unchanged)
├── Phase 2: Search (unchanged)
├── Phase 3: Rank (unchanged)
│   └── resources/ranking-criteria.md
│   └── resources/critical-appraisal.md
├── Phase 4: Export (unchanged)
└── Phase 5: Synthesize ← NEW
    └── resources/synthesis-protocol.md ← THIS FILE
```

**SKILL.md update:** Add Phase 5 reference to SKILL.md with trigger "Cuando el usuario pide redactar/escribir el marco teórico o documento de revisión".

---

**Version:** 1.0.0 | **Created:** 2026-05-23 | **Tested against:** Auditoría FALP marco teórico (5 errores mayores detectados y corregidos)
