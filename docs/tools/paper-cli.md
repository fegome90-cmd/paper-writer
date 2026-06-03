# paper CLI

Defines the command surface implemented in `cli/paper/main.py`.
This document describes the current parser and routing behavior.

## Role

| Topic | Decision |
|---|---|
| Purpose | Provide a single entrypoint for repository operations |
| Location | `cli/paper/main.py` |
| Owns | argument parsing, project-root resolution, request mapping, terminal summaries |
| Must not own | stage policy, gate policy, wrapper execution rules |

## Execution model

The CLI has two execution paths.

### Direct commands

These commands execute local handler functions in `cli/paper/main.py` and do not create an `OrchestratorRequest`:

- `paper doctor`
- `paper audit prose <file>`
- `paper audit claims <file>`
- `paper audit citations <file>`
- `paper audit ethics <file>`
- `paper audit writing-quality <file>`
- `paper audit code-health`
- `paper gate method <file>`
- `paper trace <symbol>`
- `paper graph-overview`

Direct execution is evidenced by `args.func` dispatch and the special-case `doctor` branch in `cli/paper/main.py` lines 688-706.

### Orchestrated commands

These commands are parsed by the CLI and then mapped to `OrchestratorRequest` objects:

| CLI command | Orchestrator command | Failure policy |
|---|---|---|
| `paper init [--preset <name>]` | `init` | `stop_on_error` |
| `paper search [--raw-papers <json>]` | `search` | `stop_on_error` |
| `paper screen` | `screen` | `stop_on_error` |
| `paper draft outline` | `draft_outline` | `stop_on_error` |
| `paper draft section <name>` | `draft_section` | `stop_on_error` |
| `paper lint bib` | `lint_bib` | `continue_on_error` |
| `paper lint style` | `lint_style` | `continue_on_error` |
| `paper check refs` | `check_refs` | `continue_on_error` |
| `paper audit reporting` | `audit_reporting` | `continue_on_error` |
| `paper import bib <source> [--target <path>]` | `import_bib` | `stop_on_error` |
| `paper render [--format docx|pdf] [--csl <path>] [--reference-doc <path>]` | `render` | `stop_on_error` |
| `paper verify` | `verify` | `stop_on_error` |

This mapping is exercised by `tests/cli/test_cli_request_mapping.py`.

## Public command surface

### Project and workflow commands

- `paper init`
- `paper search`
- `paper screen`
- `paper draft outline`
- `paper draft section <name>`
- `paper lint bib`
- `paper lint style`
- `paper check refs`
- `paper audit reporting`
- `paper import bib <source>`
- `paper render`
- `paper verify`
- `paper doctor`

### Phase 0 / direct audit commands

- `paper audit prose <file>`
- `paper audit claims <file>`
- `paper audit citations <file>`
- `paper audit ethics <file>`
- `paper audit writing-quality <file>`
- `paper gate method <file>`

### Repository inspection commands

- `paper audit code-health`
- `paper trace <symbol>`
- `paper graph-overview`

## Contractual notes

- The CLI resolves project root via explicit `--project/-C`, then ascending search for `outputs/state.yaml`, then current working directory.
- For orchestrated commands, the CLI only maps arguments and failure policy; stage progression and gate evaluation live in the harness.
- `paper doctor` reports environment state and degraded-mode conditions through `harness/services/doctor.py`.
- `paper render` defaults to `docx` and `pdf` when no `--format` flags are provided.
- `paper render` forwards repeated `--format` flags exactly as parsed; de-duplication is not done in the CLI layer.

## Evidence scope

This document is grounded in:

- `cli/paper/main.py` lines 465-772 for parser and dispatch behavior
- `tests/cli/test_cli_request_mapping.py` for request mapping
- `tests/cli/test_paper_cli.py` and `tests/cli/test_doctor_and_degraded.py` for exercised commands
