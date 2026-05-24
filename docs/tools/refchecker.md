# RefChecker

RefChecker is the secondary reference-checking option.
It exists as a fallback or comparison layer for reference validation.

## Quick path

1. Use only if we decide to run a second checker.
2. Wrap it behind the same normalized interface as `reference-validator`.
3. Keep the harness unaware of vendor-specific output.

## Role

| Topic | Decision |
|---|---|
| Purpose | Cross-check bibliography integrity |
| Integration | `integrations/tools/refs_validator.py` or dedicated adapter |
| Current status | Candidate, not installed yet |
| Phase | Phase 2+ |

## How it will be used

- confirm suspicious entries found by the primary validator
- act as a fallback when the primary validator is unavailable
- provide defense-in-depth for fabricated or inconsistent references

## Inputs

- `references.bib`

## Outputs

- secondary validation findings
- comparison signal for manual review if tools disagree

## Rules

- RefChecker is not mandatory for the MVP.
- If both validators are used, the harness must define conflict policy clearly.
- Do not couple the repository workflow to two validators until one-validator flow is stable.

## Next step

Keep this documented now, but prioritize `reference-validator` first for actual integration work.
