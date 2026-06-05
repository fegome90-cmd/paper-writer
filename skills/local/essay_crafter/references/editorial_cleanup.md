# Editorial Cleanup Gate

Run this immediately before final audit.

## Blockers

The final audit must stop if the draft contains:

- orphan tokens or stray initials
- truncated sentences or cut-off fragments
- duplicated placeholders
- copy-paste residue
- malformed citation spacing
- unresolved template markers

## Checklist

1. Scan for isolated short tokens that do not belong syntactically.
2. Read every heading and first/last sentence of each paragraph for truncation.
3. Search for placeholder patterns such as `{...}`, `TODO`, `TBD`, `XXX`, or duplicated labels.
4. Verify citation spacing and punctuation are consistent.
5. Re-check transitions after any late-stage cut or paste.

## Output

Return one of:

- `cleanup: pass`
- `cleanup: rework` with concrete residue items

Do not allow `cleanup: pass` if even one blocker remains.
