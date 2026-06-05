# Integrity Pipeline

This skill is designed to sit on top of the repository's existing audit surfaces.

Gate order mirrors SKILL.md Execution Steps. SKILL.md is the authoritative pipeline definition. This file adds repo-anchor context only.

## Local repo anchors

- `schemas/claim_audit.schema.json` defines the current claim-audit output shape.
- `validators/citation_verify.py` verifies citations across Crossref, Semantic Scholar, OpenAlex, and arXiv, then emits an aggregate verification verdict.
- `validators/claim_alignment.py` checks whether claims have citation support.
- `validators/claim_evidence.py` adds a second pass that compares claim text against evidence abstracts.
- `validators/writing_quality.py` and `validators/style.py` catch AI-typical patterns, inflated certainty, forbidden phrases, and weak academic style.

## Recommended gate order

1. **Question gate** — reject descriptive prompts with no arguable thesis.
2. **Roadmap gate** — require thesis plus explicit navigation at the end of the introduction.
   // CP1: Thesis + Roadmap Approval
3. **Passport gate** — reject notes without locator anchors.
4. **Structure gate** — reject sections that mix empirical, ethical, regulatory, and normative dimensions in one block.
5. **Paragraph density gate** — reject paragraphs that perform more than one rhetorical job.
6. **Drafting gate** — allow verbosity, but preserve `claim_id` traceability.
6a. **Counterargument gate** — verify at least one opposing position is addressed (argumentative and problem-solution types).
   // CP2: Structure + Counterargument Approval
7. **Reviewer gate** — simulate editor, method critic, devil's advocate, and architecture editor.
7a. **Revision loop gate** — route reviewer findings back through relevant gates per `references/revision_loop.md`.
   // CP3: Revision Review
8. **Editorial cleanup gate** — remove orphan tokens, truncation artifacts, and placeholders.
9. **Claim audit gate** — verify claims against linked evidence before final delivery.
10. **Provider audit gate** — verify structured output matches `assets/evidence_passport.schema.json`.

## Important limitation

The local repository already has useful citation and claim validators, but they are not yet identical to the full ARS claim-faithfulness audit. Treat this skill as the orchestration layer that prepares the data model those stricter gates need.
