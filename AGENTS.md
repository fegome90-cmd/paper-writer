# AGENTS.md - paper-writer

## Constitutional Anchor

This repository is governed by the Agentic Constitution.

- **Canonical source:** `~/Developer/constitucion-ai/constitution/AGENTIC-CONSTITUTION.md`
- **Source role:** read-only governance source
- **Target repo:** this repository only
- **Rule:** never mix source-repo paths with target-repo output paths

## Mission

Build a constrained system for:

1. scientific literature search
2. manuscript drafting
3. bibliographic validation
4. editorial verification
5. reproducible render

This repository is NOT a free-form "AI writer".
It is an evidence-first editorial pipeline.

## Minimal Source of Truth

Until stronger tooling exists, the source of truth is:

1. `README.md` — project purpose and bootstrap
2. `AGENTS.md` — agent operating rules
3. `TECHNICAL_BOOTSTRAP.md` — project bootstrap and import plan
4. `outputs/state.yaml` — workflow state and gate status

## Mandatory Delivery Rules

- The agent MUST NOT write bibliography entries manually.
- Citations in manuscript text MUST use citation keys only.
- Bibliography MUST come from `references.bib` through the render pipeline.
- Drafting MUST NOT start without evidence inputs.
- Delivery MUST fail if references, style, structure, or render gates fail.
- If a required CLI is missing, the agent must block and report the missing dependency.

## Minimum Workflow Order

1. Define research question and scope
2. Run literature search workflow
3. Produce screened evidence set
4. Draft outline
5. Draft manuscript sections
6. Validate references
7. Run style/editorial checks
8. Render output
9. Verify all gates before delivery

The agent MUST NOT skip steps 6-9.

## Base Construction Order

Before integrating domain writing/search skills, build the repository base in this order:

1. initialize git and repository structure
2. create the `paper` CLI skeleton
3. create `harness/` and `validators/`
4. create `outputs/state.yaml` as the workflow source of truth
5. add CLI and harness tests
6. only then import domain skills like `literature-search` and `academic-writer`

The agent MUST prioritize this construction order for the MVP.

## Repository Conventions

- Keep generated outputs inside `outputs/`
- Keep reusable prompts/skills inside `skills/`
- Keep manuscript scaffolds inside `templates/`
- Keep custom checks inside `validators/`
- Keep orchestration logic inside `harness/` or `cli/`
- Prefer adopting existing CLI tools over rebuilding them

## Initial Tooling Policy

Start with the simplest verifiable stack:

- `pandoc` first
- one reference validator first
- local validators for gaps
- stronger tools like `quarto`, `vale`, or `manubot` can be added later

## Closed-Fail Conditions

Block delivery if any of these are true:

- no evidence set exists
- `references.bib` is missing
- citation keys do not resolve
- reference validation fails
- style or structure validation fails
- render fails
- output path escapes this repository

## What Not to Do

- Do not turn this repo into a giant cloned skill warehouse
- Do not trust model-generated references without validation
- Do not add ornamental architecture before a working MVP exists
- Do not treat this repository as a scratchpad for unrelated work
