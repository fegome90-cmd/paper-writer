# Vale

Vale is the editorial style linter.
It enforces scientific tone and blocks weak or exaggerated language.

## Quick path

1. Define Vale rules under `styles/vale/`.
2. Call Vale through `integrations/tools/vale.py`.
3. Feed results into the harness gate system.

## Role

| Topic | Decision |
|---|---|
| Purpose | Lint prose and style policy |
| Integration | `integrations/tools/vale.py` |
| Current status | Planned, not installed yet |
| Phase | Phase 2 |

## How it will be used

- Detect strong unsupported claims.
- Detect informal language.
- Enforce preferred scientific wording.
- Return structured warnings/errors to the harness.

## Inputs

- manuscript files
- Vale configuration
- custom rules under `styles/vale/paper-writer/`

## Outputs

- lint findings mapped to pass/warn/fail
- log artifacts under `outputs/logs/`

## Rules

- Vale is not the source of truth for methodology; it only governs language/style.
- Editorial failures should block delivery when severity is `error`.
- Until Vale is installed, equivalent checks may live in Python validators, but that is a bridge, not the final design.

## Next step

Define the initial rule categories: strong claims, informal language, evidence language, forbidden phrases.
