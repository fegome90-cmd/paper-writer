# Proposal — Domain Skills Integration

We will wire the imported `literature-search` and `academic-writer` skills into the CLI and orchestrator. This involves exposing the required parameters (like raw papers, tiers, and directories) on the CLI level, ensuring they map cleanly to orchestrator actions, and confirming the fail-closed gates behave correctly.

## User Review Required

> [!IMPORTANT]
> To support programmatic execution of the literature search without real API keys, the `search` command will now accept raw input papers from a JSON file using a new `--raw-papers` flag. If this flag is omitted, the command will write a `search_plan.json` but won't produce `raw_results.json`, maintaining backwards compatibility.

> [!IMPORTANT]
> The `screen` command will be parameterized on the CLI to allow configuring `--min-tier` and `--search-dir`, giving more flexibility to the user and adapters without altering the inner harness rules.

---

## Open Questions

> [!NOTE]
> No major open questions remain. We will proceed with Interactive mode, presenting findings at each stage.

---

## Proposed Changes

### CLI
Expose flags for raw inputs and tier configurations in the command parser.

#### [MODIFY] [main.py](file:///Users/felipe_gonzalez/Developer/paper-writer/cli/paper/main.py)
* Add `--raw-papers` option to `paper search` command.
* Add `--min-tier` and `--search-dir` options to `paper screen` command.
* Map these command-line arguments to `OrchestratorRequest` arguments.

### Harness Verification & Tests
Ensure new CLI flags and orchestrator flows are thoroughly covered.

#### [MODIFY] [test_adapters.py](file:///Users/felipe_gonzalez/Developer/paper-writer/tests/skills/test_adapters.py)
* Add integration assertions validating CLI-to-adapter parameter mapping.

---

## Verification Plan

### Automated Tests
* Run `make verify` to ensure all typecheckers (Mypy), formatting checks (Ruff), and tests (Pytest) pass.
* Execute a target test for CLI arguments:
  `pytest tests/cli/`
