# Failure Paths

Per-gate failure modes, remediation steps, escalation triggers, and abort conditions.

| Gate | Failure Mode | Remediation | Escalation | Abort |
|---|---|---|---|---|
| Question | Topic is descriptive, not arguable | Rewrite as contested question with at least two defensible positions | User redirect at CP1 | User aborts |
| Roadmap | Introduction lacks thesis or navigation | Add explicit thesis statement + roadmap sentence | User redirect at CP1 | User aborts |
| Passport | Notes lack source_id or locator anchors | Quarantine orphan notes; map each to a source | If >50% notes unanchored | User aborts |
| Structure | Sections mix analytical dimensions | Split into separate blocks per dimension | User redirect at CP2 | Cannot split without thesis change |
| Density | Paragraphs perform multiple rhetorical jobs | Rewrite or split into single-job paragraphs | Auto-fix sufficient | — |
| Drafting | Claim_id traceability lost during drafting | Re-link claims to evidence clusters | If >30% claims orphaned | User aborts |
| Counterargument | No opposing position addressed | Add steel-man + rebuttal per counterargument.md | User redirect at CP2 | — |
| Reviewer | Reviewer findings reveal thesis drift | Re-align sections to thesis or revise thesis | Structural findings persist after round 2 | Back to CP1 |
| Revision loop | >50% findings unresolved after 2 rounds | Convert to acknowledged limitations; flag for user | User redirect at CP3 | User aborts |
| Editorial | Orphan tokens, placeholders, truncation remain | Scan and remove all blockers per editorial_cleanup.md | Auto-fix sufficient | — |
| Claim audit | Claims lack citation support or misaligned evidence | Re-verify citations; re-map claim_links | If core claim fails verification | Rebuild evidence passport |
| Provider audit | Structured output schema mismatch | Re-format output to match evidence_passport.schema.json | Auto-fix sufficient | — |

## General Rules

- Auto-fix gates (density, editorial, provider) never require user intervention
- User-facing gates (question, roadmap, structure, reviewer, revision) escalate to the nearest checkpoint
- Any gate may abort if the user sends an abort signal at a checkpoint
