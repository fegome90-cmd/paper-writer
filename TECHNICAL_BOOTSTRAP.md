# Paper Writer - Technical Bootstrap

## Goal

Build a dedicated repository for automated scientific search, drafting, validation, and rendering.

This repository should NOT reinvent existing tools. It should orchestrate:

- internal skills for search and drafting
- external CLI tools for style, references, and rendering
- a harness that forces the agent to complete the required steps before delivery

## Core Principle

The system is not "an agent that writes papers".

The system is:

1. an evidence pipeline
2. a drafting pipeline
3. an editorial CI
4. a delivery harness

No manuscript is accepted unless it passes evidence, references, style, structure, and render gates.

## What Already Exists and Should Be Reused

### From `examen_grado`

These should be reused first:

1. `skills/literature-search/`
   - core evidence workflow
   - search planning
   - ranking
   - DOI/PMID verification gate
   - matrix/thesaurus outputs
   - synthesis protocol
   - packaging contract tests

2. `skills/academic-writer/`
   - prompt library for IMRAD sections
   - should be wrapped into a controlled drafting workflow
   - should NOT remain as a free-form prompt dump

3. `skills/research-skill-bank/`
   - curated decision support
   - external-skill audit memory
   - use as reference documentation, not as runtime engine

### External tools to adopt, not rebuild

Preferred stack:

- `pandoc` or `quarto`
- `vale`
- `bibtex-tidy`
- `reference-validator` or `refchecker`
- optional later: `manubot`
- optional later: Zotero + Better BibTeX

## Recommended Clone/Import Strategy

Do NOT clone everything blindly.

### Required imports from local work

Copy or subtree-import these directories into the new repo:

- `skills/literature-search/`
- `skills/academic-writer/`

Optional but useful:

- `skills/research-skill-bank/`

### Optional external clones

Only clone these if the repo needs vendored reference material or reusable assets:

1. `K-Dense-AI/scientific-agent-skills`
   - reference only
   - do not make the runtime depend on the whole suite
   - extract only the relevant writing/review patterns if needed

2. `Aperivue/medsci-skills`
   - reference for reporting/audit checklists
   - use to design reporting validators, not as the only quality authority

3. reference-validation tools
   - clone only if the chosen validator is not stable enough as a package install
   - prefer installable CLI over vendoring source when possible

## What Should Be Built in This New Repo

## 1. CLI Wrapper

Create a project CLI named `paper`.

Target commands:

```bash
paper init
paper search
paper screen
paper draft outline
paper draft section introduction
paper draft section methods
paper audit reporting
paper lint style
paper lint bib
paper check refs
paper render
paper verify
```

The CLI should call skills, scripts, and external tools in a deterministic order.

## 2. Execution Harness

The harness is the most important custom layer.

It should enforce a state machine like:

```yaml
# Schema version: 1.0
stage: validating
gates:
  repo_initialized: true
  search_completed: true
  screened_evidence: true
  outline_drafted: true
  sections_completed: true
  bib_normalized: false
  citations_resolved: false
  refs_validated: false
  style_passed: false
  reporting_passed: false
  render_passed: false
  ready_for_delivery: false
```

Rules:

- drafting cannot start without evidence inputs
- rendering cannot start without references
- delivery cannot happen if any gate fails
- bibliography cannot be written manually by the agent

## 3. Validators

Custom validators should fail the pipeline when:

- a citation appears in text but no matching key exists in `references.bib`
- a `.bib` entry lacks a DOI, PMID, PMCID, arXiv ID, or valid URL where required
- forbidden strong-claim language appears
- required manuscript sections are missing
- reporting checklist items are incomplete

## 4. Templates

Create templates for:

- `manuscript.qmd`
- `references.bib`
- journal-specific CSL and structure presets
- reporting checklist manifests

## 5. CI Pipeline

The repository should expose a strict CI path:

```bash
make lint-style
make lint-bib
make check-refs
make audit-reporting
make render
make verify
```

`make verify` should fail if any upstream gate fails.

## Recommended Repository Layout

```text
paper-writer/
  skills/
    imported/
      literature-search/
      academic-writer/
      research-skill-bank/
    local/
      reporting-audit/
      citation-pipeline/
  cli/
    paper
  harness/
    state_manager.py
    gates.py
    orchestrator.py
  validators/
    refs.py
    style.py
    structure.py
    reporting.py
  templates/
    manuscript.qmd
    references.bib
    journals/
  styles/
    vale/
    csl/
  tests/
  docs/
  Makefile
  README.md
```

## Recommended Phase Plan

### Phase 1 - Repository Base

Status: COMPLETE

Verified deliverables:

- new repo initialized
- base directories created (`cli/`, `harness/`, `validators/`, `templates/`, `outputs/`, `tests/`, `docs/`)
- `paper` CLI skeleton
- `outputs/state.yaml` defined as workflow source of truth
- seeded base templates (`templates/manuscript.qmd`, `templates/references.bib`)
- minimal test runner path working
- fresh verification path passing (`pytest`, `ruff`, `mypy`)

### Phase 2 - Harness and Verification

Status: COMPLETE

Verified deliverables:

- hardened state machine and gate authority model
- validation logic extracted into dedicated `validators/` modules
- real Pandoc wrapper replacing placeholder render behavior
- assembled manuscript flow from `outputs/drafts/*.md` to render input
- artifact manifest and delivery blocking rules preserved as fail-closed surfaces
- expanded CLI, integration, and validator tests around real validator/render behavior

### Phase 3 - Domain Skill Integration

Status: COMPLETE (real import, no surrogates)

Verified deliverables:

- vendored `resources/scoring.py` from source into `skills/imported/literature_search/scoring.py` — 340+ lines of real scoring engine (PaperMetrics, ScoringWeights, deduplicate, classify_tier, calculate_final_score, verify_citation)
- vendored 6 resource `.md` files and `SKILL.md` from literature-search source
- vendored `SKILL.md` from academic-writer source (prompt collection only — no Python code in source)
- `search.py` wraps real scoring engine for dedup+tier+score pipeline
- `drafting.py` extracts section structures (CARS model, CONSORT flow) from academic-writer prompts
- adapters in `skills/local/adapters.py` bridge real imports to `SkillAdapter` port
- 56 scoring tests vendored from source (`tests/skills/test_scoring.py`) + 14 adapter tests
- all architectural invariants verified: no harness→skills imports, skills write no state

**Adaptation truth:**
- literature-search scoring code is used verbatim — no invented code
- academic-writer is a prompt collection — adapter generates structural skeletons, NOT LLM content
- The agent following SKILL.md collects papers; the scoring engine processes them
- Fallback papers are provided by the action runner for CLI testing without an agent

### Phase 4 - Editorial Gates and Hardening

Status: COMPLETE

Verified deliverables:

- Vale rule packs added under `styles/vale/` and connected to the style wrapper
- bibliography normalization hardened with domain validation fallback rules
- reference validation preserved as distinct gates (`bib_normalized`, `citations_resolved`, `refs_validated`)
- journal presets added under `templates/journals/` with preset schema validation
- multi-output render wired through Pandoc with `output_formats`, `csl`, and `reference_doc`
- optional Zotero/Better BibTeX `.bib` ingestion wired through CLI → orchestrator → wrapper
- negative-path behavior verified for preset fallback, bad imports, malformed DOI, and invalid render formats
- smoke-level real artifact generation verified for scaffold copy, `.bib` import, and DOCX render

## First Implementation Decisions

### Decision 1 - Start Pandoc-first

If Quarto is not installed yet, start with `pandoc`.

Reason:

- `pandoc` is already available in the current environment
- it is enough for an MVP render pipeline
- Quarto can be added later without changing the harness design

### Decision 2 - Use one reference checker first

Pick one of:

- `reference-validator`
- `refchecker`

Do not integrate both on day one.
Use one as the primary gate, then add redundancy later if needed.

### Decision 3 - Keep bibliography machine-generated

The agent may insert citation keys only, for example:

```text
[@smith2024voice]
```

The final bibliography must come from `references.bib` through the render pipeline.

## Anti-Goals

Do NOT do these in v1:

- rebuild Quarto, Pandoc, Vale, or citation managers
- import huge external skill suites as runtime dependencies
- allow free-form manuscript generation with no evidence gate
- let the agent write references manually

## Initial Clone/Copy Checklist

### Mandatory

- [x] initialize git repository `paper-writer`
- [x] create `cli/`, `harness/`, `validators/`, `templates/`, `outputs/`, `tests/`, `docs/`
- [x] create CLI skeleton `paper`
- [x] create `Makefile`
- [x] create `outputs/state.yaml`
- [x] create `templates/manuscript.qmd`
- [x] create baseline tests for CLI/harness

### Optional

- [ ] copy `skills/research-skill-bank/`
- [ ] clone K-Dense repo as reference material
- [ ] clone Aperivue repo as audit reference material
- [ ] add Zotero integration later

## Bootstrap Commands

Use this exact start sequence:

```bash
cd ~/Developer/paper-writer
git init
mkdir -p cli harness validators templates outputs tests docs skills
touch cli/__init__.py harness/__init__.py validators/__init__.py
cat > outputs/state.yaml <<'YAML'
# Schema version: 1.0
# Pre-init state. Run `paper init` to scaffold the repository.
stage: bootstrap
gates:
  repo_initialized: false
  search_completed: false
  screened_evidence: false
  outline_drafted: false
  sections_completed: false
  bib_normalized: false
  citations_resolved: false
  refs_validated: false
  style_passed: false
  reporting_passed: false
  render_passed: false
  ready_for_delivery: false
YAML
```

Then build the repo with this exact scope:

1. create `paper init` and `paper verify` first
2. create `harness/state_manager.py`, `harness/gates.py`, and `harness/orchestrator.py`
3. add baseline CLI and harness tests
4. wire `pandoc` as the first render backend
5. only then import `literature-search` and `academic-writer`
6. fail delivery if `.bib` or reference validation is missing

That is enough to create a serious MVP.


## Recommended Next Work

After Phase 4, do Phase 5 in this order:

1. build a full end-to-end smoke pipeline covering `init -> import/search/screen/draft/lint/render/verify`
2. add CI automation (GitHub Actions) for `ruff`, `mypy`, `pytest`, and smoke checks
3. make external-tool degraded mode explicit for Vale, LaTeX, and `bibtex-tidy` so production readiness is observable
4. strengthen render verification for CSL and `reference_doc` outputs, ideally with artifact inspection or golden checks
5. finalize operator-facing documentation so `smoke-verified`, `degraded mode`, and `production-ready` have precise meanings
