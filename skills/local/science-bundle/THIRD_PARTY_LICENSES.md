# Third-Party Licenses — `science-bundle`

This directory contains skills imported from
[google-deepmind/science-skills](https://github.com/google-deepmind/science-skills)
(Apache License 2.0, Copyright 2026 Google LLC).

The original LICENSE is preserved at `./LICENSE` in this directory.

## Bundled skills

| Skill | Upstream path | Purpose | License |
|-------|---------------|---------|---------|
| `scienceskillscommon` | `skills/scienceskillscommon/` | Shared HTTP client, rate-limiting, retries (transitive dep) | Apache 2.0 |
| `literature_search_arxiv` | `skills/literature_search_arxiv/` | Search arXiv + download preprints | Apache 2.0 |
| `literature_search_openalex` | `skills/literature_search_openalex/` | OpenAlex bibliometric search + DOI lookup | Apache 2.0 |
| `literature_search_europepmc` | `skills/literature_search_europepmc/` | Europe PMC full-text + citation graph | Apache 2.0 |
| `workflow_skill_creator` | `skills/workflow_skill_creator/` | Meta-skill for creating new API-wrapping skills | Apache 2.0 |
| `literature_search_biorxiv` | `skills/literature_search_biorxiv/` | bioRxiv / medRxiv preprint browse + search by date/DOI | Apache 2.0 |
| `pubmed_database` | `skills/pubmed_database/` | PubMed / PMC search + full-text retrieval via E-utilities | Apache 2.0 |

## Upstream API Terms of Service

Each skill consumes a public API. At first use, the agent MUST honor upstream
ToS and create a `LICENSE_NOTIFICATION.txt` per the instructions in each
`SKILL.md` (see the "License Notification" section in each skill's docs).

| API | ToS | Rate limit | Notes |
|-----|-----|------------|-------|
| arXiv | https://info.arxiv.org/help/api/index.html | 1 req / 3s | Attribution required |
| OpenAlex | https://developers.openalex.org/ | Free pool: $0.01/day credit; Premium with API key | Polite-pool email required |
| Europe PMC | https://europepmc.org/ | 1 req/s | Open Access only |
| ClinicalTrials.gov (not bundled) | https://clinicaltrials.gov/ | Generous | |
| PubMed E-utilities | https://www.ncbi.nlm.nih.gov/books/NBK25500/ | 3 req/s without API key, 10 req/s with | Email in User-Agent recommended |
| bioRxiv / medRxiv | https://api.biorxiv.org/ + https://www.biorxiv.org/content/about-biorxiv | Narrow date ranges required | |

## Modifications

None at clone time. Future modifications will be tracked in this file with
a dated changelog entry below.

### Changelog
- 2026-06-05: Initial bundle import. Five skills cloned as-is from upstream.
- 2026-06-05: Added `pubmed_database` and `literature_search_biorxiv`. Bundle now has 7 skills.
