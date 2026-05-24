# paper CLI

Defines the public command surface of the repository.
This is the only command users or agents should invoke directly.

## Quick path

1. Run `paper <command>`.
2. The CLI delegates to the harness.
3. The harness decides if the action is allowed.

## Role

| Topic | Decision |
|---|---|
| Purpose | Provide one stable entrypoint for the system |
| Location | `cli/paper/` |
| Owns | argument parsing, command routing, user-facing summaries |
| Must not own | workflow rules, direct subprocess logic, validation policy |

## Command surface

### Bootstrap and finalization
- `paper init`
- `paper render`
- `paper verify`

### Evidence workflow
- `paper search`
- `paper screen`

### Drafting workflow
- `paper draft outline`
- `paper draft section <name>`

### Validation workflow
- `paper lint bib`
- `paper check refs`
- `paper lint style`
- `paper audit reporting`

## Usage contract

- Commands call harness functions, not external binaries directly.
- CLI output should be short and status-oriented.
- Failures should explain which gate or dependency blocked progress.

## Wrapper boundary

The CLI never decides whether a bibliography is valid or whether rendering may proceed.
It asks the harness.

## Next step

Implement `cli/paper/main.py` only after `harness/state_manager.py`, `harness/gates.py`, and `harness/orchestrator.py` exist.
