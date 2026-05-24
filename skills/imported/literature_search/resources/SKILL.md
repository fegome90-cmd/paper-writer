---
name: literature-search
description: "Búsqueda bibliográfica sistemática con ranking de calidad, descarga de PDFs y exportación estructurada. Para proyectos de investigación que necesitan evidencia académica."
when: "Cuando Felipe pide buscar papers, artículos, evidencia académica, revisión bibliográfica, o descarga de PDFs"
examples:
  - "Busca papers sobre X"
  - "Revisión bibliográfica de Y"
  - "Busca evidencia sobre Z en PubMed"
  - "Descarga PDFs de estos papers"
  - "Ranking de calidad de estos estudios"
metadata:
  openclaw:
    requires:
      bins: [curl]
    emoji: "📚"
---

# Literature Search Skill

Búsqueda bibliográfica sistemática en 5 fases: **Plan → Search → Rank → Export → Synthesize**. Produce un ranking ponderado de papers con criterios explícitos, descarga PDFs cuando es posible, y genera archivos exportables versionados.

## Fase 1: Plan de Búsqueda

### Interactive Mode

When running interactively, define with the user:

1. **Research question** (PICOT if applicable)
2. **Period** (default: 5 years)
3. **Languages** (default: English + Spanish)
4. **Population focus** (oncology, neurology, etc.)
5. **Intervention type** (technology, drug, rehabilitation, etc.)
6. **Outcomes of interest** (QoL, communication, depression, etc.)
7. **Study phase** → determines scoring weights (see ranking-criteria.md §Weight Adjustments)

Save plan to: `apps/pae-wizard/outputs/research/search-plan.md`

### Autonomous Mode

When running without interactive TTY (subagent, background worker):

1. Parse research question from existing `apps/pae-wizard/outputs/research/search-plan.md`
2. If not found, infer from `HEARTBEAT.md` or project README
3. Use safe defaults: last 5 years, English + Spanish, "balanced" phase
4. Document all assumptions in the output log
5. Execute full pipeline without prompting for confirmation

## Fase 2: Search

See [`resources/search-protocol.md`](resources/search-protocol.md) for the complete protocol.

**Sources by priority:**

| Source | Type | Finds |
|--------|------|-------|
| `web_search` | General | Papers, reviews, meta-analyses |
| Semantic Scholar API | Academic | Citation counts, forward snowball, DOI verification |
| OpenAlex API | Academic | Broad academic coverage, author profiles |
| CrossRef API | Metadata | DOI verification, retraction checks |
| `web_fetch` pmc.ncbi.nlm.nih.gov | Full text | Open access complete |
| `web_fetch` pubmed.ncbi.nlm.nih.gov | Abstracts | Metadata + abstract |
| `web_fetch` journals (PLOS, BMC, Springer Open) | PDFs | Direct download |
| LILACS / SciELO | LatAm | Mandatory when E_CONTEXT includes LatAm |
| Google Scholar | Citations | Author profiles, impact |

**Search layers:**

```
Layer 1:   Broad search (web_search, 10 results)
Layer 2:   Targeted fetch (web_fetch top 5-10)
Layer 2.5: Deduplication (PMID/DOI, or title Levenshtein >95%)
Layer 2.6: Thesaurus capture (MeSH + DeCS + author keywords)
Layer 3:   Author mining (web_search by key author)
Layer 4:   Snowball (references from top papers)
```

See [`resources/thesaurus-capture.md`](resources/thesaurus-capture.md) for thesaurus protocol.

Typically: 3-5 web searches + 5-10 fetches + 1 author mining per topic.

## Fase 3: Ranking

See [`resources/ranking-criteria.md`](resources/ranking-criteria.md) for detailed criteria and formula.

**Formula:**

```
Score = (A × wA) + (B × wB) + (C × wC) + (D × wD) + (E × wE)
```

| Criterion | Default Weight | Measures |
|-----------|:-------------:|----------|
| A. Population relevance | 25% | Does study population = target population? |
| B. Intervention relevance | 25% | Is intervention = what we're evaluating? |
| C. Outcome relevance | 20% | Does it measure our outcomes of interest? |
| D. Methodological quality | 20% | Evidence level, n, journal tier, citations, COI |
| E. Context applicability | 10% | Usable in our context (language, resources)? |

**D sub-scores** (see ranking-criteria.md for full detail):

| Component | Calculation | Max |
|-----------|-------------|:---:|
| Evidence level | `value` (passthrough) | 5 |
| Sample size | `value` (passthrough) | 2 |
| Journal quality | `value` (passthrough) | 2 |
| Citation impact | `value` | 1 |
| COI penalty | `0 or -0.5` | 0 |
| **Total D** | **sum** | **10** |

**Tier classification:**

| Range | Tier | Action |
|:-----:|:----:|--------|
| 8.0-10 | 🏆 Tier 1 | Primary citation |
| 6.5-7.9 | 🥈 Tier 2 | Supporting citation |
| 5.0-6.4 | 🥉 Tier 3 | Background / context |
| < 5.0 | ⬜ Discard | Not cited |

## Fase 4: Export

### Generated Files

All files go to `apps/pae-wizard/outputs/research/` within the project:

| # | File | Content |
|---|------|---------|
| 1 | `search-plan.md` | Search plan with parameters |
| 2 | `papers-database.md` | All papers with complete data |
| 3 | `quality-ranking.md` | Ranked scores with tiers |
| 4 | `papers-summary.md` | 1-2 line summary per paper |
| 5 | `thesaurus.md` | MeSH/DeCS terms + reproducible search strategies |
| 6 | `literature-matrix.md` | Coverage analysis by category (see §Literature Matrix) |
| 7 | `pdfs/` | Downloaded PDFs (open access only) |

### Literature Matrix

A structured table showing coverage by topic category, used to detect gaps.

```markdown
# Literature Matrix — [Topic]
Generated: YYYY-MM-DD | Skill: literature-search v1.4.0

## Overview
- Search date: YYYY-MM-DD
- Total collected: N papers
- After screening: N papers
- Source distribution: PubMed N% | Semantic Scholar N% | PMC N% | LILACS N%

## Coverage by Category

| Category | Target | Found | Status | Core papers |
|-----------|:------:|:-----:|:------:|------------|
| [Cat1] | ≥5 | N | ✅/⚠️ | [paper1], [paper2] |
| [Cat2] | ≥3 | N | ✅/⚠️ | [paper1] |

## Evidence Table

| # | Paper | Tier | Design | n | Population | Key Finding |
|---|-------|:----:|--------|---|------------|-------------|
| 1 | Author Year | 🏆 | RCT | 62 | HNC post-TL | 94% satisfaction |

## Top 20 Core Papers

| Rank | Paper | Score | Why core |
|------|-------|:-----:|----------|
| 1 | ... | 8.15 | Only RCT of TTS communication app |

## Search Log

| Tool | Query | Results | After screening |
|------|-------|:-------:|:---------------:|
| web_search | "pubmed laryngectomy..." | 10 | 5 |
| Semantic Scholar | "voice quality laryngectomy" | 20 | 8 |
| PMC fetch | PMCXXXXXXX | 1 | 1 |

## Coverage Gaps
- [Category needing more papers]
- [Databases not yet searched]
```

### Versioning

**Never overwrite previous results.** Use versioned filenames:

```
results_v1_20260522.json    ← first run
results_v2_20260523.json    ← second run (expanded search)
results_latest.json          ← symlink/copy to most recent version
```

### Output Header

Every exported file starts with:

```yaml
---
generated: 2026-05-22T17:30:00-04:00
skill: literature-search
version: 1.4.0
query: "description of search"
papers_found: 20
papers_ranked: 20
phase: balanced
---
```

### Per-Paper Format

```markdown
### [ID] Short Title (Year)

- **Authors:** LastName et al.
- **Journal:** *Name* | Q1/Q2 | SJR: X.XX
- **Type:** Meta/RCT/Cohorte/Cross-sectional/Review
- **n:** XXX patients
- **PMID:** XXXXXXXX
- **PMC:** PMCXXXXXXX (if applicable)
- **DOI:** 10.xxxx/xxxxx
- **MeSH:** Term1, Term2, Term3
- **PDF:** ✅ downloaded / ❌ paywall
- **COI:** None / Industry-funded (-0.5)
- **Abstract:** [1-2 paragraphs]
- **Key findings:** [bullet points]
- **Limitations:** [bullet points]
- **Score:** A=X B=X C=X D=X E=X → **Final: X.XX** (Tier X)
```

### PRISMA Flow (Optional)

For formal systematic reviews, generate a PRISMA flow diagram:

```
Records identified via web_search (n=X)
  → After deduplication (n=Y)
    → Full-text assessed (n=Z)
      → Included in ranking (n=W)
        → Tier 1 (n=A) | Tier 2 (n=B) | Tier 3 (n=C)
```

The deduplication log from Layer 2.5 provides the numbers for each stage.

### Citation Verification Gate

**MANDATORY — reject any paper that fails verification.**

Before including any paper in the final output:

1. **Verify DOI or PMID exists** — lookup via Semantic Scholar API or CrossRef
2. **Confirm title matches** — the paper you found must match the record
3. **Flag unverifiable citations** — mark as `⚠️ UNVERIFIED` in output

**Verification methods (in priority order):**

| Method | API | What it checks |
|--------|-----|----------------|
| DOI lookup | `https://api.crossref.org/works/{DOI}` | DOI exists, publisher metadata |
| PMID lookup | `https://pubmed.ncbi.nlm.nih.gov/{PMID}/` | PMID exists, title match |
| Semantic Scholar | `https://api.semanticscholar.org/graph/v1/paper/DOI:{DOI}` | Citations, verification |

**Hard reject criteria — paper MUST be excluded:**

1. No DOI, PMID, or arXiv ID can be found
2. Title does not match any database record
3. Appears only in model-generated text with no external source
4. DOI resolves to a different paper
5. Paper has been retracted (check CrossRef `assertion` field)

**Soft flag — include with `⚠️ UNVERIFIED`:**

1. DOI exists but abstract unavailable
2. Preprint only (no peer-reviewed version)
3. Conference abstract (not full paper)

This gate prevents fabricated citations from entering the evidence base.

## PDF Download

See [`resources/pdf-download-guide.md`](resources/pdf-download-guide.md) for download strategy.

**Quick reference:**

| Source | PDF | Note |
|--------|:---:|------|
| PLOS ONE | ✅ | `/article/file?id=DOI&type=printable` |
| BMC / Springer Open | ✅ | `/counter/pdf/DOI.pdf` |
| MDPI | ❌ | Blocks without session |
| Elsevier / JAMA / Wiley / Oxford | ❌ | Paywall |
| JMIR | ❌ | HTML only |
| Europe PMC | ❌ | Blocked from CLI |

If PDF fails: document as paywall. PMC full text has all the data.

## Final Checklist

Before delivering results:

- [ ] All papers have PMID/DOI
- [ ] Scores calculated with explicit formula
- [ ] Tier assigned to each paper
- [ ] PDFs downloaded (available ones)
- [ ] 1-line summary per paper
- [ ] TOP 5 identified with justification
- [ ] Evidence level distribution documented
- [ ] All papers have verified DOI/PMID (citation verification gate)
- [ ] No unverifiable or fabricated citations in output
- [ ] Literature matrix with coverage analysis generated
- [ ] Thesaurus captured (MeSH + DeCS)
- [ ] Files versioned in `apps/pae-wizard/outputs/research/`
- [ ] Deduplication log included

## Common Errors

| Error | Solution |
|-------|----------|
| Searching without a plan | Always do Phase 1 first |
| Not documenting criteria | Always show formula and scores |
| Batch PDF downloads without verifying | Check `%PDF-` header before accepting |
| Mixing populations | Adjust criterion A for actual population |
| Ignoring outcome language | Verify instrument validated in target language |
| Missing PMID | Always include PMID for traceability |
| Overwriting previous results | Use versioned filenames |
| No thesaurus capture | Extract MeSH terms during Phase 2 |
| Unverified citations | Run citation verification gate before export |
| No coverage analysis | Generate literature matrix to detect gaps |
| No RoB assessment | Use `resources/critical-appraisal.md` for risk of bias |
| No state persistence | Use `resources/openalex-search.md` state pattern |

## Phase 5: Synthesis & Verification

When the user asks to write/draft a marco teórico, literature review section, or theoretical framework based on ranked papers, execute [`resources/synthesis-protocol.md`](resources/synthesis-protocol.md).

**5 sub-phases:**

1. **5.1 Pre-Synthesis Verification** — For each Tier 1-2 paper: verify journal name, year, n=, study design, conclusion direction, and population context against PubMed/Semantic Scholar.
2. **5.2 Claim-to-Source Traceability Matrix** — Register every claim with ≥1 statistic in a traceability matrix. NO claim with 🔴 or ⬜ status may appear in final document.
3. **5.3 Literature Matrix** — Coverage analysis by topic category. Flag gaps as research justification.
4. **5.4 Writing Protocol** — Structured drafting with mandatory rules (one claim = one source, absolute claims require absolute evidence, qualitative studies state scope, context qualifiers mandatory).
5. **5.5 Post-Synthesis Audit** — Final checklist: all claims verified, matrix complete, journal names NLM format, word count within limits.

**Trigger:** When user says "redactar marco teórico", "escribir revisión bibliográfica", "draft theoretical framework", or any request to produce narrative text from the ranked papers.

---

## Resource Index

| Resource | Purpose | Source |
|----------|---------|--------|
| [`ranking-criteria.md`](resources/ranking-criteria.md) | Scoring A-E formula, tiers, weights | v1.0 original |
| [`search-protocol.md`](resources/search-protocol.md) | Database strategies, API usage, dedup | v1.2.0 |
| [`pdf-download-guide.md`](resources/pdf-download-guide.md) | PDF download + paywall strategy | v1.0 original |
| [`thesaurus-capture.md`](resources/thesaurus-capture.md) | MeSH/DeCS capture for reproducibility | v1.2.0 |
| [`examples.md`](resources/examples.md) | Worked examples, formulas | v1.1.1 |
| [`critical-appraisal.md`](resources/critical-appraisal.md) | RoB 2, ROBINS-I, NOS, GRADE, bias taxonomy | v1.3.0 🆕 |
| [`openalex-search.md`](resources/openalex-search.md) | OpenAlex API + state persistence pattern | v1.3.0 🆕 |
| [`external-skills-audit.md`](resources/external-skills-audit.md) | 33 skills auditadas, stack recomendado | v1.3.0 🆕 |
| [`synthesis-protocol.md`](resources/synthesis-protocol.md) | Phase 5: claim verification, traceability, writing protocol, post-audit | v1.4.0 🆕 |
| [`citation-format.md`](resources/citation-format.md) | APA 7th & Vancouver formatting, NLM abbreviations, conversion table | v1.4.0 🆕 |

## Research Skill Bank

Curated external skills: [`../research-skill-bank/CATALOG.md`](../research-skill-bank/CATALOG.md)

## Portability Note

This repository requires research outputs under `apps/pae-wizard/outputs/research/`. If you reuse this skill elsewhere, adapt the output root explicitly for that workspace instead of assuming a generic docs folder.

---

**Version:** 1.4.0 | **Updated:** 2026-05-23 | **Changes:** +Phase 5 Synthesis & Verification (synthesis-protocol.md), +citation formatting guide APA/Vancouver (citation-format.md), +claim traceability matrix, +conclusion direction audit, +context alignment check, +literature matrix, +writing protocol with absolute claim rules
