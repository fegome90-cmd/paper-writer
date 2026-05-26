# OpenAlex Search Resource

> **Source:** dsebastien/ai-skill-scholar (adaptado)
> **Version:** 1.0.0 | **Created:** 2026-05-22
> **Purpose:** Patrón de búsqueda OpenAlex con state persistence para literature-search

---

## OpenAlex API

**Base URL:** `https://api.openalex.org`
**Rate limit:** 10 requests/sec (no API key needed; with `mailto` param: 100/sec)
**Coverage:** 250M+ works, 90M+ authors, 130K+ venues
**License:** CC0 (public domain)

### Setup

```bash
# Polite pool (10x rate limit) — add your email
export OPENALEX_MAILTO="fegome.90@gmail.com"
```

### Basic Search

```bash
# Search works by keyword
curl -s "https://api.openalex.org/works?search=head+and+neck+cancer+speech+impairment&filter=from_publication_date:2020-01-01&per_page=50&mailto=$OPENALEX_MAILTO" | jq '.results[].doi'

# Search with filters
curl -s "https://api.openalex.org/works?filter=concepts.id:C2777956513,from_publication_date:2020-01-01,type:article&sort=cited_by_count:desc&per_page=25&mailto=$OPENALEX_MAILTO" | jq '.results[] | {title, doi, cited_by_count, publication_year}'
```

### Filter Examples

```bash
# By concept (oncology = C2777956513)
filter=concepts.id:C2777956513

# By publication date range
filter=from_publication_date:2020-01-01,to_publication_date:2025-12-31

# By work type (article, review, book_chapter)
filter=type:article

# By DOI
filter=doi:10.1234/example

# By PMID (via.ids)
filter=ids.pmid:12345678

# Open access only
filter=is_oa:true

# Min citations
filter=cited_by_count:>10

# By venue (journal)
filter=primary_location.source.id:S12345

# Combined filters (comma-separated)
filter=concepts.id:C2777956513,from_publication_date:2020-01-01,type:article,cited_by_count:>5
```

### Citation Tracking

```bash
# Works that CITE a given work (forward snowball)
curl -s "https://api.openalex.org/works?filter=cites:W1234567890&mailto=$OPENALEX_MAILTO"

# Works CITED BY a given work (backward snowball)
curl -s "https://api.openalex.org/works/W1234567890/referenced_works?mailto=$OPENALEX_MAILTO"

# Related works
curl -s "https://api.openalex.org/works/W1234567890/related?mailto=$OPENALEX_MAILTO"
```

### Concepts Lookup

```bash
# Search concepts (for filtering)
curl -s "https://api.openalex.org/concepts?search=head+and+neck+cancer&mailto=$OPENALEX_MAILTO" | jq '.results[] | {id, display_name, level}'

# Concept hierarchy levels:
# Level 0: Most general (Medicine, Biology)
# Level 1: Subfield (Oncology, Surgery)
# Level 2-5: Increasingly specific (Head and Neck Cancer)
```

### Output Fields

```bash
# Select specific fields
curl -s "https://api.openalex.org/works?select=id,doi,title,publication_year,cited_by_count,authorships,primary_location&mailto=$OPENALEX_MAILTO"
```

**Key fields per work:**
- `id` — OpenAlex ID (W + digits)
- `doi` — DOI URL
- `title` — Title
- `publication_year` — Year
- `cited_by_count` — Citation count
- `authorships` — Authors with affiliations
- `primary_location` — Journal/source info
- `type` — article, review, etc.
- `open_access` — OA status + PDF URL
- `concepts` — Linked concepts with scores
- `ids` — DOI, PMID, PMCID, MagID
- `referenced_works` — Cited works (backward)
- `related_works` — Related works

---

## State Persistence Pattern (from ai-skill-scholar)

### Why State Persistence?
Searches take time. State files let you:
- Pause and resume searches
- Track what's been found vs screened vs included
- Avoid duplicate searches
- Build a reproducible audit trail

### File Structure

```
research-state/
├── search-log.json          # All searches executed
├── candidates.json          # All papers found (pre-screening)
├── shortlist.json           # Papers passing abstract screen
├── included.json            # Papers passing full-text screen
├── excluded.json            # Papers excluded with reasons
├── extraction.json          # Data extraction per paper
└── search-config.json       # Search parameters
```

### search-config.json

```json
{
  "research_question": "Effectiveness of TTS communication apps for HNC patients with speech impairment",
  "pico": {
    "population": "Head and neck cancer patients",
    "intervention": "Text-to-speech / AAC communication apps",
    "comparison": "Standard care / no intervention",
    "outcome": "Quality of life, communication satisfaction, speech-related QoL"
  },
  "period": "2020-2025",
  "databases": ["PubMed", "OpenAlex", "Semantic Scholar"],
  "languages": ["English", "Spanish"],
  "date_created": "2026-05-22",
  "last_updated": "2026-05-22"
}
```

### search-log.json

```json
[
  {
    "timestamp": "2026-05-22T14:30:00Z",
    "database": "OpenAlex",
    "query": "head and neck cancer speech impairment TTS",
    "filter": "from_publication_date:2020-01-01,type:article",
    "results_count": 47,
    "notes": "Initial broad search"
  },
  {
    "timestamp": "2026-05-22T14:35:00Z",
    "database": "PubMed",
    "query": "\"head and neck neoplasms\"[MeSH] AND \"speech\"[MeSH] AND \"communication\"",
    "filter": "5 years, English/Spanish",
    "results_count": 23,
    "notes": "MeSH search with speech + communication"
  }
]
```

### candidates.json

```json
[
  {
    "openalex_id": "W1234567890",
    "doi": "10.1234/example",
    "pmid": "12345678",
    "title": "Example paper title",
    "year": 2024,
    "citations": 45,
    "source": "OpenAlex",
    "found_by_search": "2026-05-22T14:30:00Z",
    "status": "candidate",
    "abstract": "..."
  }
]
```

### Deduplication Across Sources

```bash
# Deduplicate by DOI (primary key)
# Then by PMID
# Then by title similarity (Levenshtein distance > 0.85)
jq -s 'unique_by(.doi)' candidates.json
```

---

## Integration with literature-search Skill

### When to Use OpenAlex vs Other Sources

| Source | When to Use | Rate Limit | Coverage |
|--------|-------------|------------|----------|
| **PubMed** | Biomedical, clinical | 10/sec (API key) | 35M+ biomedical |
| **OpenAlex** | Broad academic, citation tracking | 10-100/sec | 250M+ all fields |
| **Semantic Scholar** | AI/ML, CS, fast citation data | Variable (429 common) | 200M+ |
| **CrossRef** | DOI verification, retraction check | 50/sec | 140M+ |

### Recommended Search Order

1. **OpenAlex** — Broad sweep, citation counts, concept filtering
2. **PubMed** — Clinical precision, MeSH terms, clinical trials
3. **Semantic Scholar** — Forward snowball, TLDR summaries
4. **CrossRef** — DOI verification, retraction check

### Bash One-Liners for Quick Searches

```bash
# Quick citation count for a DOI
curl -s "https://api.openalex.org/works/doi:10.1234/example?mailto=$OPENALEX_MAILTO" | jq '.cited_by_count'

# Get all works by author
curl -s "https://api.openalex.org/works?filter=author.id:A1234567890&sort=cited_by_count:desc&mailto=$OPENALEX_MAILTO"

# Get highly-cited papers in a field (last 5 years)
curl -s "https://api.openalex.org/works?filter=concepts.id:C2777956513,from_publication_date:2020-01-01,cited_by_count:>50&sort=cited_by_count:desc&per_page=25&mailto=$OPENALEX_MAILTO"
```

---

**Sources:**
- dsebastien/ai-skill-scholar SKILL.md — OpenAlex search patterns, state persistence
- OpenAlex API docs — https://docs.openalex.org
- literature-search v1.2.0 — existing API integration
