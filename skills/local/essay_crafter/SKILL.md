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
- Define an explicit thesis and make the introduction close with a roadmap sentence.
- Do not draft from loose notes. Every note MUST have `source_id` plus a locator anchor.
- Keep `sources`, `notes`, `claims`, and `claim_links` separate. Claims never point directly to bibliography entries.
- Keep one primary analytical dimension per section or paragraph cluster. Do not mix empirical evidence, ethics, regulation, and normative synthesis in the same block.
- Each paragraph should do one rhetorical job only. Split paragraphs that change function midstream.
- Reject any claim that lacks mapped evidence or only has weak contextual support.
- Run prose calibration before final formatting: remove AI-typical phrasing, inflated certainty, and broken paragraph flow.
- Block final audit if orphan tokens, truncated fragments, or leftover placeholders remain.

## Decision Gates

| If | Then |
|---|---|
| Topic is descriptive only | Rewrite it as a contested question before proceeding |
| Note has no locator | Quarantine it; do not cite or reuse it |
| Introduction lacks roadmap | Block progression to drafting |
| A paragraph mixes evidence, regulation, ethics, or synthesis | Split into separate sections or paragraphs |
| Claim bundles multiple assertions | Split into atomic `claim_id`s |
| A paragraph performs more than one rhetorical job | Rewrite or split it |
| Evidence only provides context | Use it for framing, not as primary support |
| Orphan token or truncated fragment appears | Block final audit until cleaned |
| Final draft changes wording materially | Re-run claim audit on affected claims |

## Execution Steps

1. Define the essay question and success criteria.
2. State the thesis and build the roadmap with `assets/outline_template.md`.
3. Build the evidence passport using `assets/evidence_passport.schema.json`.
4. Map each note to one analytical dimension and drop tangential branches.
5. Draft long first, then run the structure gate from `references/structure_gate.md`.
6. Run the paragraph-density pass from `references/paragraph_density.md`.
7. Simulate four reviewers: editor, method critic, devil’s advocate, and architecture editor.
8. Run editorial cleanup with `references/editorial_cleanup.md`.
9. Compile `claims` + `claim_links` for final audit.
10. Use local audit references plus OpenAI complements from `references/openai_complements.md` when structured outputs or batch review help.

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
- `assets/outline_template.md`
- `references/evidence_passport.md`
- `references/structure_gate.md`
- `references/paragraph_density.md`
- `references/editorial_cleanup.md`
- `references/integrity_pipeline.md`
- `references/openai_complements.md`
