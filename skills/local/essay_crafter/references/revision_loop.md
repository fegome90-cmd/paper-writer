# Revision Loop Protocol

Route reviewer findings (step 7) back through the draft via a bounded revision cycle.

## Loop Definition

```
Reviewer findings → categorize → fix → re-verify affected gates → report
```

## Finding Categories

Each finding is classified into exactly one category:

- **Structural** — section ordering, missing components, thesis drift, claim-evidence mismatch
- **Evidential** — missing sources, weak support, citation errors, new evidence needed
- **Prose** — clarity, tone, transitions, register, AI-typical phrasing

Categories are processed independently. A structural fix does not block prose fixes.

## Round Limit

Max **2 rounds** per category. If all findings in a category are fixed in round 1, terminate that category early — no unnecessary second round.

## Status Taxonomy

| Status | Meaning |
|---|---|
| open | Finding not yet addressed |
| fixed | Finding resolved, gate re-passed |
| deferred-to-limitations | Finding unresolved after 2 rounds, converted to acknowledged limitation |

## Escalation Protocol

- **>50% findings unresolved** after 2 rounds → flag for user intervention at next checkpoint
- **Structural findings persist** → may require thesis/roadmap revision (escalate back to CP1)
- **Evidential findings** requiring new sources → route back to passport gate before re-drafting

## Revision Report Output

After the loop completes, produce:

```
Structural:  N fixed, M deferred-to-limitations, K open
Evidential:  N fixed, M deferred-to-limitations, K open
Prose:       N fixed, M deferred-to-limitations, K open
```

Any "open" items after round 2 MUST be converted to deferred-to-limitations. Zero items may remain open at loop end.
