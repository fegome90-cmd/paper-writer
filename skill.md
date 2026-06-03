---
name: paper-writer
description: Use when working on Bootstrap
---

# Paper Writer

## Overview
Bootstrap

## When to Use
Working on `/Users/felipe_gonzalez/Developer/paper-writer/paper-writer/`

## Core Pattern

### Session Evidence Persistence (5 Steps)

1) **Persist intention** (CLI proactive):
```bash
trifecta session append --segment . --summary "<action>" --files "<csv>" --commands "<csv>"
```

2) **Sync context**:
```bash
trifecta ctx sync --segment .
```

3) **Read** session.md (confirm objective logged)

4) **Execute** context cycle:
```bash
trifecta ctx search --segment . --query "<topic>" --limit 6
trifecta ctx get --segment . --ids "<id1>,<id2>" --mode excerpt --budget-token-est 900
```

5) **Log result**:
```bash
trifecta session append --segment . --summary "Completed <task>" --files "<touched>" --commands "<executed>"
```

### Mandatory Validation Protocol (Law V)

**STALE FAIL-CLOSED**: If `ctx validate` fails or `stale_detected=true`:
- **STOP** immediately. Do NOT guess.
- Run: `trifecta ctx sync --segment .` + `trifecta ctx validate --segment .`
- Continue ONLY if state is **VALID**.
- **Evidence**: All mutations MUST be followed by a verification command.

## Common Mistakes
- Skipping session logging (Law I violation)
- Writing before reading (Law II violation)
- Continuing with stale pack (Law VI violation)
- Model-specific bias in naming (Law VII violation)

## Resources (On-Demand)
- `@_ctx/prime_paper-writer.md` - Reading list
- `@_ctx/agent_paper-writer.md` - Tech stack & gates
- `@_ctx/session_paper-writer.md` - Session log

---
**Profile**: `impl_patch` | **Updated**: 
