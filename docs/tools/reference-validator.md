# reference-validator

`reference-validator` is the primary reference metadata validator.
It checks that bibliography entries point to real, inspectable sources.

## Quick path

1. Run after bibliography cleanup.
2. Call through `integrations/tools/refs_validator.py`.
3. Use results as part of the final verification gate.

## Role

| Topic | Decision |
|---|---|
| Purpose | Validate DOI and reference metadata quality |
| Integration | `integrations/tools/refs_validator.py` |
| Current status | Planned, not installed yet |
| Phase | Phase 2 |

## How it will be used

- verify DOI presence and validity where applicable
- detect incomplete or inconsistent metadata
- flag entries that need manual review

## Inputs

- `references.bib`

## Outputs

- structured validation results
- failing entries list for the harness and logs

## Rules

- This tool is for metadata validation, not prose style.
- Validation findings should block delivery when required identifiers are missing or inconsistent.
- The wrapper must normalize tool output so the harness can treat all validators consistently.

## Next step

Decide the minimum metadata contract per reference type: DOI, PMID, PMCID, arXiv ID, or URL.
