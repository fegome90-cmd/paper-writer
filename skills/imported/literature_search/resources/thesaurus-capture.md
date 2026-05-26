# Thesaurus Capture — Literature Search Skill

## Why Capture Thesaurus Terms

Without MeSH terms and DeCS equivalents, searches are not reproducible. Capturing controlled vocabulary enables:

1. **Reproducibility** — Re-run the exact same search months later
2. **Cross-database translation** — Use MeSH terms to build DeCS queries for LILACS
3. **Gap detection** — Identify which MeSH terms are missing from your search strategy
4. **Reporting** — PRISMA requires documented search strategies

## What to Capture

| Field | Source | Where to find |
|-------|--------|---------------|
| **MeSH terms** | PubMed | Article page → "MeSH terms" section |
| **DeCS terms** | BVS/LILACS | https://decs.bvsalud.org/ |
| **Author keywords** | Paper metadata | Abstract page or full text |
| **Emtree terms** | Embase | (if accessible via institutional login) |

## Extraction Protocol

### Step 1: From PubMed

For each Tier 1 and Tier 2 paper:

```
URL: https://pubmed.ncbi.nlm.nih.gov/PMID/
```

Scroll to "MeSH terms" section. Extract all terms listed.

### Step 2: DeCS Equivalents

Look up each MeSH term at https://decs.bvsalud.org/

Not all MeSH terms have DeCS equivalents. Mark as "N/A" if none exists.

### Step 3: Author Keywords

Extract from the paper's metadata (usually listed after the abstract).

### Step 4: Build Search Strategy

Combine the most frequent MeSH terms into a reproducible PubMed query.

## Output Format

### Per-Paper Thesaurus

```markdown
### [ID] Título Corto

- **MeSH:** Term1, Term2, Term3, ...
- **DeCS:** Término1, Término2, ... (or "N/A" if no equivalent)
- **Keywords:** keyword1, keyword2, ...
```

### Aggregate Thesaurus (apps/pae-wizard/outputs/research/thesaurus.md)

```markdown
# Thesaurus — [Topic]

Generated: YYYY-MM-DD | Skill: literature-search v1.4.0

## MeSH Terms (by frequency)

| MeSH Term | Frequency | Papers |
|-----------|:---------:|--------|
| Laryngectomy | 12/20 | [ID1, ID2, ...] |
| Voice Quality | 9/20 | [ID1, ...] |
| ... | ... | ... |

## DeCS Equivalences

| MeSH | DeCS |
|------|------|
| Laryngectomy | Laringectomía |
| Voice Quality | Calidad de Voz |
| Head and Neck Neoplasms | Neoplasias de Cabeza y Cuello |
| ... | ... |

## Reproducible Search Strategies

### PubMed
```
("Laryngectomy"[MeSH] OR "Laryngeal Neoplasms"[MeSH])
AND ("Voice Quality"[MeSH] OR "Communication"[MeSH])
AND ("Quality of Life"[MeSH] OR "Patient-Reported Outcome Measures"[MeSH])
AND ("2019/01/01"[PDat] : "2025/12/31"[PDat])
```

### LILACS/DeCS
```
("Laringectomía"[DeCS] OR "Neoplasias de Cabeza y Cuello"[DeCS])
AND ("Calidad de Voz"[DeCS] OR "Comunicación"[DeCS])
AND ("Calidad de Vida"[DeCS])
```

### Cochrane
```
(laryngectomy OR "total laryngectomy") AND ("voice quality" OR communication) AND ("quality of life")
```
```

## When to Capture

| When | What |
|------|------|
| **During Phase 2** | Capture MeSH + keywords for each paper as you fetch it |
| **After Phase 3** | Build aggregate thesaurus from top papers |
| **Phase 4 export** | Include `apps/pae-wizard/outputs/research/thesaurus.md` as output file |

## Common MeSH Terms by Domain

### Head and Neck Cancer / Communication

| MeSH Term | DeCS Equivalent | Use for |
|-----------|----------------|---------|
| Laryngectomy | Laringectomía | Surgical removal of larynx |
| Laryngeal Neoplasms | Neoplasias Laríngeas | Laryngeal cancer |
| Head and Neck Neoplasms | Neoplasias de Cabeza y Cuello | HNC general |
| Voice Quality | Calidad de Voz | Voice outcomes |
| Speech, Alaryngeal | Habla Alaringea | Post-laryngectomy speech |
| Communication | Comunicación | Communication general |
| Quality of Life | Calidad de Vida | QoL outcomes |
| Prosthesis Implantation | Implante de Prótesis | TEP / voice prosthesis |
| Depression | Depresión | Mental health |
| Patient-Reported Outcome Measures | Medidas de Resultados Informadas por el Paciente | PROMs |
| Smartphone | Teléfono Inteligente | Mobile technology |
| Mobile Applications | Aplicaciones Móviles | Apps |
| Speech Recognition Software | — | ASR technology |
| Text-to-Speech | — | TTS technology |
| Assistive Technology | Tecnología Asistiva | AAC / assistive devices |

---

**Version:** 1.2.0 | **Created:** 2026-05-22
