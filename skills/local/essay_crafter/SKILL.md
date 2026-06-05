---
name: essay_crafter
description: "Trigger: essay, ensayo, academic essay, claim audit, citation check, reviewer. Build essays with evidence passports, ARS-style integrity gates, and OpenAI-ready structured outputs."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "2.0"
---

## Activation Contract

Use this skill when writing or revising an academic essay that must survive claim, citation, and prose scrutiny. Prefer it for deterministic essay pipelines, not freeform brainstorming.

## Hard Rules

- Start by converting the topic into an arguable research question.
- Do not draft from loose notes. Every note MUST have `source_id` plus a locator anchor.
- Keep `sources`, `notes`, `claims`, and `claim_links` separate. Claims never point directly to bibliography entries.
- Reject any claim that lacks mapped evidence or only has weak contextual support.
- Run prose calibration before final formatting: remove AI-typical phrasing, inflated certainty, and broken paragraph flow.

## Decision Gates

| If | Then |
|---|---|
| Topic is descriptive only | Rewrite it as a contested question before proceeding |
| Note has no locator | Quarantine it; do not cite or reuse it |
| Claim bundles multiple assertions | Split into atomic `claim_id`s |
| Evidence only provides context | Use it for framing, not as primary support |
| Final draft changes wording materially | Re-run claim audit on affected claims |

## Execution Steps

1. Define the essay question and success criteria.
2. Build the evidence passport using `assets/evidence_passport.schema.json`.
3. Map each note to the outline; drop tangential branches.
4. Draft long first, then refine line by line.
5. Run reviewer simulation: editor, method critic, devil’s advocate.
6. Compile `claims` + `claim_links` for final audit.
7. Use local audit references plus OpenAI complements from `references/openai_complements.md` when structured outputs or batch review help.

## Output Contract

Return:
- Final research question.
- Evidence passport path or object.
- Outline tied to evidence clusters.
- Claim-to-evidence map.
- Reviewer findings and required rewrites.
- Final audit status: pass, rework, or blocked.

## References

- `assets/evidence_passport.schema.json`
- `references/evidence_passport.md`
- `references/integrity_pipeline.md`
- `references/openai_complements.md`
