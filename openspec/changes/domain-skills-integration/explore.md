# SDD Exploration — Domain Skills Integration

## Purpose
Analyze the status of the imported skills (`literature-search` and `academic-writer`) in `paper-writer` compared to their source versions in `examen_grado`, and identify what is required to fully wire them into the orchestrator CLI pipeline.

---

## 1. Source Skill Analysis

### Literature Search
*   **Source Path**: `/Users/felipe_gonzalez/Developer/examen_grado/skills/literature-search/`
*   **Assets**:
    *   `SKILL.md`: Instructs the agent on systematic reviews across 5 phases.
    *   `resources/scoring.py`: Fully functional Python module with scoring weights, tier classification, and title-based/DOI deduplication.
    *   `resources/*.md`: Supplementary protocols (search, ranking, critical appraisal, synthesis).
*   **Adapted State**: Already imported `scoring.py` as `skills/imported/literature_search/scoring.py` and wrapped it with a runner interface in `search.py`.

### Academic Writer
*   **Source Path**: `/Users/felipe_gonzalez/Developer/examen_grado/skills/academic-writer/`
*   **Assets**:
    *   `SKILL.md`: Text-based prompts with placeholders and CARS/CONSORT structure guidelines.
*   **Adapted State**: Imported `SKILL.md` to `skills/imported/academic_writer/SKILL.md`. Derived `sections_manifest.json` as a machine-readable structure to drive `drafting.py` skeletons dynamically.

---

## 2. Gap Analysis (What is missing to complete Phase 3?)

1.  **CLI Execution & Inputs**:
    *   `paper search` requires `raw_papers` inputs to actually execute deduplication and scoring. Currently, if called without arguments, it only writes `search_plan.json`. We need a clean path for the CLI or the orchestrator to pass raw search inputs (e.g., from an external JSON or API mock) to feed the literature search pipeline.
2.  **State transitions validation**:
    *   Confirm that running `search` and `screen` successfully transitions `outputs/state.yaml` stages (`bootstrap` -> `search` -> `screen` -> `outline`).
    *   Verify that `paper draft section <name>` successfully updates `sections_completed` gate status.
3.  **Local integrations audit**:
    *   Ensure that the outputs directory hierarchy (`outputs/search/`, `outputs/drafts/`, `outputs/render/`, `outputs/logs/`) matches what is expected by the validators (`bibtex-tidy`, `vale`, `refs_validator`).
    *   Double check if local placeholder skills like `citation-pipeline` or `reporting-audit` (referenced in the architecture diagram) need scaffolding to avoid breaking the validations.

---

## 3. Technical Alternatives

### Option A: Manual CLI Feeding
Allow the CLI commands (`search`, `screen`, `draft`) to accept direct inputs via arguments (e.g., `--raw-papers path/to/raw.json`) to allow the user or external agent to easily plug in raw results and trigger the scoring pipeline locally.

### Option B: Auto-loading from convention paths
Have the adapter automatically look for inputs in convention paths (e.g., looking for `outputs/search/raw_papers.json` if none is passed) to simplify CLI invocations.

---

## 4. Verification Strategy
*   Run unit/integration tests (`pytest`) covering the CLI input parameters.
*   Validate that executing the complete sequence (`init` -> `search` -> `screen` -> `draft` -> `lint` -> `check` -> `render` -> `verify`) works end-to-end on local fixtures without blocking gates or producing silent failures.
