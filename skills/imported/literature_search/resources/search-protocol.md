# Search Protocol — Literature Search Skill

## Keywords Strategy

### Building Search Queries

**Structure:** `[population] + [intervention/outcome] + [filter]`

**Population keywords by specialty:**

| Area | Keywords |
|------|----------|
| Oncología HNC | "head and neck cancer", "laryngeal cancer", "oropharyngeal", "total laryngectomy", "HNC" |
| Neurología | "amyotrophic lateral sclerosis", "ALS", "motor neurone disease", "MND", "multiple sclerosis" |
| General | "speech impairment", "dysarthria", "communication disorder", "voice loss" |

**Intervention keywords:**

| Type | Keywords |
|------|----------|
| Tecnología | "speech recognition", "ASR", "text-to-speech", "TTS", "AAC", "mobile app", "mHealth" |
| Rehabilitación | "voice rehabilitation", "speech therapy", "prosthesis", "electrolarynx" |
| Cirugía | "tracheoesophageal puncture", "TEP", "partial laryngectomy" |

**Outcome keywords:**

| Type | Keywords |
|------|----------|
| Quality of life | "quality of life", "QoL", "VRQoL", "V-RQoL" |
| Psychological | "depression", "anxiety", "distress", "mental health" |
| Communication | "communication", "speech intelligibility", "voice handicap", "VHI" |
| Social | "social isolation", "participation", "social functioning" |

### Search Filters

**Temporal:** Append years: `2020 2021 2022 2023 2024 2025`

**Study type:**
- `"systematic review" OR "meta-analysis"`
- `"randomized controlled trial" OR "RCT"`
- `"prospective" OR "longitudinal"`
- `"cohort study"`

**Journal quality:** Verify SJR at https://www.scimagojr.com/journalsearch.php?q=JOURNAL_NAME

## Semantic Scholar API (Real-time Citation Data)

**Free, no auth required.** Use for live citation counts and paper discovery.

```
Endpoint: https://api.semanticscholar.org/graph/v1/paper/search
Params:
  query: search terms
  fields: title,authors,year,citationCount,abstract,externalIds,venue
  limit: 10-20
  year: 2020-2025
Rate limit: 100 requests/5 min (no key). Space requests 3s apart.
```

**Use cases in this skill:**
1. **Citation count for Criterion D** — replace estimated citations with real-time count
2. **Forward snowball** — find papers that CITE a given paper
3. **Related papers** — discover via `paper/search` with refined queries
4. **Paper lookup by DOI/PMID** — verify a reference exists and get metadata

**Example:**
```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/search?query=laryngectomy+voice+quality+of+life&fields=title,authors,year,citationCount,externalIds&limit=10&year=2020-2025"
```

**Forward snowball (papers citing a given paper):**
```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/PMID:38702757/citations?fields=title,year,citationCount&limit=20"
```

**DOI/PMID verification:**
```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/DOI:10.1186/s12955-025-02334-6?fields=title,year,citationCount,externalIds"
```

## OpenAlex API (Broad Academic Coverage)

**Free, no auth.** Complements Semantic Scholar with broader coverage.

```
Endpoint: https://api.openalex.org/works
Params:
  search: query terms
  filter: publication_year:2020-2025,type:article
  sort: cited_by_count:desc
  per_page: 25
```

**Use cases:**
1. Broad academic search beyond PubMed (includes social sciences, engineering)
2. Author profile and affiliation data
3. Concept/topic classification

## CrossRef API (DOI Verification)

**Free, no auth.** Use for DOI verification and metadata validation.

```bash
curl -s "https://api.crossref.org/works/10.1186/s12955-025-02334-6"
```

**Use case:** Verify DOI exists, get publisher metadata, check for retractions.

## Specialized Databases

To avoid exclusive PubMed/MEDLINE bias, route searches by project context:

### Mandatory by Context

| Database | When mandatory | What it covers |
|----------|---------------|----------------|
| **Cochrane Library** | Always (first stop for systematic reviews) | Maps existing systematic reviews before searching primary evidence |
| **LILACS / SciELO** | When `E_CONTEXT` includes "LatAm" or "Chile" | LatAm epidemiology, Spanish/Portuguese validations, local studies |
| **CINAHL** | When project involves nursing, rehabilitation, or allied health | Nursing and allied health literature |
| **PsycINFO** | When outcomes include mental health constructs | Psychology, behavioral science |
| **Embase** | When project involves pharmacology or European studies | European literature, drug studies (paywall) |

### Access Notes

| Database | Access |
|----------|--------|
| Cochrane | Partially free (abstracts), full via institutional login |
| LILACS | Free: https://lilacs.bvsalud.org/ |
| SciELO | Free: https://scielo.org/ |
| CINAHL | Paywall (EBSCO) — requires institutional login |
| PsycINFO | Paywall (APA) — requires institutional login |
| Embase | Paywall (Elsevier) — requires institutional login |

**Practical approach:** web_search covers PubMed + PMC (~80% of relevant medical literature). For formal FALP reviews, complement with institutional access for Cochrane/LILACS/CINAHL.

## Extraction Protocol

### What to extract from each paper

**Minimum required:**

1. Title (full)
2. Authors (first author + et al.)
3. Journal name + year
4. Study design (RCT, meta, cohort, etc.)
5. Sample size (n)
6. Population description
7. Key finding (1-2 sentences)
8. PMID
9. DOI

**If available (PMC full text):**

10. Complete abstract
11. Outcome measures used
12. Limitations stated by authors
13. Funding source
14. Conflict of interest declaration
15. MeSH terms (for thesaurus capture)

### PMC Full Text Extraction

```
URL pattern: https://pmc.ncbi.nlm.nih.gov/articles/PMCXXXXXXX/
```

**Extract in order:**
1. Article title
2. Authors
3. Abstract
4. Methods section (study design, n, inclusion criteria)
5. Results (key statistics, p-values)
6. Discussion (limitations, clinical implications)
7. MeSH terms (for thesaurus — see resources/thesaurus-capture.md)

## Search Layers

```
Capa 1: Broad search (web_search, 10 results)
  → Identify keywords, key authors, relevant journals

Capa 2: Targeted fetch (web_fetch top 5-10)
  → Extract abstracts, n, design, key findings

Capa 2.5: Deduplication
  → Group by PMID (primary) or DOI (secondary)
  → If no PMID/DOI: compare title strings for near-match
    → Simple approach: normalize (lowercase, strip punctuation) and check equality
    → Advanced: Levenshtein ratio > 0.95 via `from Levenshtein import ratio`
    → Or use Python `difflib.SequenceMatcher` (stdlib, no deps): `SequenceMatcher(None, a, b).ratio() > 0.95`
  → Keep most complete metadata entry
  → Log: "X unique papers from Y total results (Z duplicates)"

Capa 2.6: Thesaurus capture
  → Extract MeSH terms + author keywords from each paper
  → Build DeCS equivalents
  → Save to apps/pae-wizard/outputs/research/thesaurus.md
  → (See resources/thesaurus-capture.md for protocol)

Capa 3: Author mining (web_search by key author)
  → Find research group, additional publications

Capa 4: Snowball (references from top papers)
  → Search papers cited BY top results (backward)
  → Search papers THAT CITE top results (forward, via Scholar)
```

Typically: 3-5 web searches + 5-10 fetches + 1 author mining per topic.

## Citation Tracking (Snowball)

After identifying top 3-5 papers:

1. Search papers **cited BY** them (backward snowball)
2. Search papers **that cite** them (forward snowball via Google Scholar)
3. Search **same author's** other publications

This typically adds 5-10 relevant papers not found in initial search.

## 10-Database Lookup Table

Quick reference for database selection by use case.

### Database Reference

| Database | Auth | Rate Limit | Best For |
|----------|------|------------|----------|
| **PubMed** | API key optional | 3-10/sec | Biomedical search |
| **PMC** | API key optional | 3-10/sec | Full text biomedical |
| **bioRxiv** | None | No documented | Biology preprints |
| **medRxiv** | None | No documented | Medical preprints |
| **arXiv** | None | 1 req/3sec | Physics/CS/math preprints |
| **OpenAlex** | API key recommended | 10-100/sec | Cross-domain, broad coverage |
| **Crossref** | mailto param | 5-10/sec | DOI verification, metadata |
| **Semantic Scholar** | API key optional | Variable (429 common) | Citations, recommendations |
| **CORE** | API key required | — | Full text any field |
| **Unpaywall** | email param | — | Open access PDFs |

### Identifier Cross-Reference

| Identifier | Format | Example | Used By |
|------------|--------|---------|--------|
| DOI | `10.xxxx/xxxxx` | `10.1038/nature12373` | All databases |
| PMID | Integer | `34567890` | PubMed, PMC, S2 |
| PMCID | `PMC` + digits | `PMC7029759` | PMC, Europe PMC |
| arXiv ID | `YYMM.NNNNN` | `2103.15348` | arXiv, S2 |
| OpenAlex ID | `W` + digits | `W2741809807` | OpenAlex |
| S2 ID | 40-char hex | `649def34f8be...` | Semantic Scholar |
| ORCID | `0000-XXXX-XXXX-XXXX` | `0000-0001-6187-6610` | OpenAlex, Crossref |

**Cross-referencing:** S2 accepts `DOI:`, `PMID:`, `ARXIV:` prefixes. OpenAlex accepts `doi:`, `pmid:` prefixes.

### Cross-Database Query Patterns

| Need | Databases to Query |
|------|-------------------|
| Everything about a paper | Crossref + S2 + Unpaywall |
| Comprehensive literature search | PubMed + OpenAlex + S2 |
| Find and read a paper | PubMed (find) + Unpaywall (OA) + PMC/CORE (full text) |
| Preprint → published version | bioRxiv/medRxiv + Crossref |
| Author overview with metrics | S2 + OpenAlex |
| DOI verification | Crossref (primary) + S2 (secondary) |
| Open access PDF | Unpaywall (primary) + CORE (fallback) |

### API Key Fallback Chain

```
1. Check environment variable (e.g., $NCBI_API_KEY)
2. Check .env in current working directory
3. Proceed without key (lower rate limits)
4. Log which key is missing + registration URL
```

| Service | Env Variable | Registration |
|---------|-------------|-------------|
| NCBI | `NCBI_API_KEY` | https://www.ncbi.nlm.nih.gov/account/settings/ |
| CORE | `CORE_API_KEY` | https://core.ac.uk/services/api |
| Semantic Scholar | `S2_API_KEY` | https://www.semanticscholar.org/product/api |
| OpenAlex | `OPENALEX_MAILTO` | No registration needed |
| Crossref | `CROSSREF_MAILTO` | No registration needed |
| Unpaywall | `UNPAYWALL_EMAIL` | No registration needed |

---

**Version:** 1.3.0 | **Updated:** 2026-05-22 | **Added:** 10-database lookup table, identifier cross-reference, API key management, cross-database query patterns (from K-Dense paper-lookup)
