# `science-bundle`

Third-party skills cloned from
[google-deepmind/science-skills](https://github.com/google-deepmind/science-skills)
(Apache 2.0, Copyright 2026 Google LLC).

## What's here

- `scienceskillscommon/` — shared HTTP client (transitive dep)
- `literature_search_arxiv/` — arXiv search + preprint download
- `literature_search_openalex/` — OpenAlex bibliometric search
- `literature_search_europepmc/` — Europe PMC full-text + citation graph
- `workflow_skill_creator/` — meta-skill for creating new skills
- `pubmed_database/` — PubMed/PMC search + full-text retrieval
- `literature_search_biorxiv/` — bioRxiv/medRxiv preprint browse

## Integration with `essay_crafter`

These skills complement, NOT duplicate, the existing
`skills/local/essay_crafter/validators/citation_verify.py` which verifies
citations against Crossref / Semantic Scholar / OpenAlex / arXiv. The
imported skills add:

- **Discovery** — find papers by query (not just verify a known citation)
- **Full-text retrieval** — download PDFs / abstracts for note-taking
- **Citation graph** — forward and backward references from Europe PMC
- **Bibliometrics** — h-index, citation counts from OpenAlex

## License

See `LICENSE` and `THIRD_PARTY_LICENSES.md` in this directory.
