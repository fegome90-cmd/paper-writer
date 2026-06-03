# paper-writer - Harness & State Machine Specification

## 1. Purpose

The Harness is the core control layer of the `paper-writer` repository. It acts as a strict guard dog (gatekeeper) that prevents the agent (or user) from taking shortcuts, skipping validation, or delivering an unverified manuscript.

The Harness maintains the execution state in `outputs/state.yaml` and evaluates preconditions before executing any workflow commands.

---

## 2. Dependencies & Components

To remain robust and lightweight, the Harness uses:
- **Python 3.10+** (standard library only, except `PyYAML` for parsing/writing state).
- **`harness/state_manager.py`**: Reads, validates, and serializes state transitions to `outputs/state.yaml`.
- **`harness/gates.py`**: Executes filesystem checks, validator scripts, and wrapper tools to confirm if a gate is passed.
- **`harness/orchestrator.py`**: Evaluates transition rules and coordinates execution.

---

## 3. Workflow Stages & State Schema

The file `outputs/state.yaml` tracks two things:
1. **`stage`**: The current logical phase of the manuscript.
2. **`gates`**: Key boolean flags representing verification milestones.

### State Schema (`outputs/state.yaml`)

```yaml
# Schema version: 1.0
stage: bootstrap          # [bootstrap | search | screen | outline | drafting | validating | rendering | rendered]
gates:
  repo_initialized: true  # Base repo structure exists
  search_completed: false # Literature search completed, raw results saved
  screened_evidence: false # Screened set exists with valid DOI/PMID keys
  outline_drafted: false   # Outline exists mapped to evidence keys
  sections_completed: false # Introduction, Methods, Results, Discussion drafted
  bib_normalized: false    # references.bib linted and sorted
  citations_resolved: false # All citations in drafts exist in references.bib
  refs_validated: false    # All bibliography entries pass DOI/URL resolver gates
  style_passed: false      # Vale linter passes with zero errors
  reporting_passed: false  # Reporting guidelines checklist is fully checked
  render_passed: false     # Pandoc/Quarto successfully compiled the document
  ready_for_delivery: false # Final confirmation check passed
```

---

## 4. Transition Matrix & Gating Rules

The table below defines what is required to **enter** a stage, what command initiates it, what output files are produced, and what **postconditions** must be satisfied to move to the next stage.

| Stage | Command | Preconditions (Gates Required) | Core Action | Expected Output Artifacts | Postconditions (Gates Unlocked) |
|---|---|---|---|---|---|
| **bootstrap** | `paper init` | None | Scaffold repository base and templates. | `outputs/state.yaml`<br>`templates/manuscript.qmd`<br>`templates/references.bib` | `repo_initialized: true` -> Move to **search** |
| **search** | `paper search` | `repo_initialized: true` | Run literature search plan. | `outputs/search/search_plan.json`<br>`outputs/search/raw_results.json` | `search_completed: true` -> Move to **screen** |
| **screen** | `paper screen` | `search_completed: true` | Screen results, validate DOIs/PMIDs. | `outputs/search/screened_evidence.json` | `screened_evidence: true` -> Move to **outline** |
| **outline** | `paper draft outline` | `screened_evidence: true` | Create manuscript outline using evidence keys. | `outputs/drafts/outline.md` | `outline_drafted: true` -> Move to **drafting** |
| **drafting** | `paper draft section <name>` | `outline_drafted: true` | Draft manuscript sections using citation keys only. | `outputs/drafts/introduction.md`<br>`outputs/drafts/methods.md`<br>`outputs/drafts/results.md`<br>`outputs/drafts/discussion.md` | `sections_completed: true` -> Move to **validating** |
| **validating** | `paper lint bib`<br>`paper check refs`<br>`paper lint style`<br>`paper audit reporting` | `sections_completed: true` | Run validators: check references, styles, claim policy, and structure. | `outputs/logs/bib_tidy.log`<br>`outputs/logs/refs_check.log`<br>`outputs/logs/style_lint.log`<br>`outputs/logs/reporting_audit.log` | `bib_normalized: true`<br>`citations_resolved: true`<br>`refs_validated: true`<br>`style_passed: true`<br>`reporting_passed: true` -> Move to **rendering** |
| **rendering** | `paper render` | All validations `true` | Compile draft + bibliography using Pandoc/Quarto. | `outputs/render/manuscript.docx`<br>`outputs/render/manuscript.pdf` | `render_passed: true` -> Move to **verified** |
| **verified** | `paper verify` | `render_passed: true` | Final gate check, locking the delivery manifest. | `outputs/manifest.yaml` | `ready_for_delivery: true` |

---

## 5. Fail-Closed Policy (Políticas de Fallo Seguro)

The Harness operates under a strict **Fail-Closed** rule. If any verification fails, the system blocks forward progress and marks delivery as disabled:

1. **Gate Reset on Edit**: If a section draft is modified after validation has passed, the validation gates (`citations_resolved`, `style_passed`, `reporting_passed`, `render_passed`, `ready_for_delivery`) are automatically reset to `false` in `outputs/state.yaml`.
2. **Missing Dependencies**: If a required external tool (e.g. `vale`, `pandoc`, or python packages) is missing from the environment, the Harness command must block execution immediately, output an error to stderr detailing the missing tool, and exit with `code 1`. It must **NOT** bypass the validation.
3. **Citation Guard**: The rendering process is gated by `citations_resolved` and `refs_validated`. If any inline citation key like `[@jones2024]` doesn't exist in `references.bib`, rendering is blocked.
4. **Claim Guard**: Custom validators looking for forbidden/unbacked strong-claim language (e.g. "We prove for the first time in history that...") will fail the `reporting_passed` gate.

---

## 6. Interaction Sequence

Whenever a CLI command is run:

```
[User/Agent CLI Command]
        │
        ▼
[State Manager] ──► Read outputs/state.yaml
        │
        ▼
[Orchestrator] ──► Validate Preconditions for requested command
        │
        ├──► [FAIL] ──► Print Error & Exit Code 1 (State unchanged)
        │
        └──► [PASS]
                │
                ▼
         [Run Core Action / Tools]
                │
                ▼
         [Run Gates Verification]
                │
                ├──► [FAIL] ──► Set specific gate to FALSE (Exit Code 1)
                │
                └──► [PASS] ──► Set specific gate to TRUE
                        │
                        ▼
                 [Update outputs/state.yaml] ──► Move to next stage (if applicable)
```
