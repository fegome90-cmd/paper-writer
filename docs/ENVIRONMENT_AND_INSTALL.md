# paper-writer - Environment and Install Policy

Defines the MVP dependency policy for `paper-writer`.

## Quick path

1. Keep the base repo light.
2. Install external tools; do not clone them by default.
3. Add hard dependencies only when the matching workflow stage is implemented.

## Dependency Policy

| Surface | Policy |
|---|---|
| Python runtime | required for harness implementation |
| `pandoc` | first render backend when render stage is implemented |
| `vale` | required when style gate is implemented |
| `bibtex-tidy` | required when bibliography normalization is implemented |
| `reference-validator` or `refchecker` | one primary reference checker first; add redundancy later |
| external skill repos | import or vendor only when actually needed |

## Install Principles

- Prefer package managers or virtual environments over vendoring full tool repos.
- A tool becomes mandatory only when its workflow stage is active.
- Missing required tools must fail closed once that stage exists.

## MVP Staging

| Phase | Mandatory |
|---|---|
| Documentation/base phase | Python only |
| Render MVP | Python + `pandoc` |
| Editorial hardening | add `vale`, `bibtex-tidy`, reference checker |

## Rules

- Do not assume optional tools are already installed.
- Do not let installation state silently downgrade gate behavior.
- Document whether a missing tool is blocking now or only for a later phase.

## Audit Checklist

- [ ] Dependencies are staged by workflow maturity.
- [ ] Tools are installed, not cloned, by default.
- [ ] Blocking vs optional tools are explicit.
