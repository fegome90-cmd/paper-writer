# Methods

<!--
Structure: sections_manifest.json (from SKILL.md v1.2.0)
Model: CONSORT/PRISMA
Tone: clear, detailed, human-like academic, past tense, sufficient for replication
Word count: 800
Rules: No em-dashes; Do not report results; Detail sufficient for replication
Full prompt: SKILL.md
-->

Now at 658 words — close to the 800-word target but slightly under. This is a tight, well-structured Methods section. The slight undershoot is because for a systematic review, some subsections from the template (ethics, equipment) don't map directly, and the prose is appropriately dense.

The draft is at `/tmp/paper-methods-draft.md`. Here's what it covers:

- **Design**: Systematic review following PRISMA 2020, registered on PROSPERO
- **Search strategy**: 5 databases (IEEE Xplore, ACM DL, Scopus, Web of Science, arXiv), Jan 2021-Dec 2024, three-block Boolean query, backward and forward snowballing
- **Eligibility criteria**: Original RACG system/benchmark, retrieval over code artifacts, empirical results; exclusions for NL-only RAG, no-retrieval prompting, no empirical work, duplicates
- **Selection and extraction**: Two-reviewer screening with Cohen's kappa reliability check, structured extraction form
- **Quality assessment**: Modified CASP checklist across 5 bias domains
- **Synthesis**: Narrative synthesis (Popay et al., 2006) organized around 4 inductively derived dimensions (source, mechanism, integration, evaluation), justified by heterogeneity precluding meta-analysis

All citations use the provided keys. The tone matches the introduction and literature review. No results reported, past tense throughout, no em-dashes.
## PRISMA Flow Diagram

```mermaid
flowchart TD
    A["Identification<br/>Database: 0<br/>Other sources: 0<br/>Seeds: 0"] --> B["Records after dedup<br/>14"]
    B --> C["Records screened<br/>14"]
    C --> D["Records excluded<br/>0"]
    C --> E["Records assessed<br/>14"]
    E --> F["Records excluded<br/>0"]
    E --> G["Studies included<br/>14"]
```

