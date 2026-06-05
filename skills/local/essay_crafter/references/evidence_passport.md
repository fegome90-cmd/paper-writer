# Evidence Passport

Use one normalized passport per essay.

## Core model

- `sources[]` = canonical bibliography records.
- `notes[]` = atomic evidence units written in your own words after reading.
- `claims[]` = final assertions that appear in the essay.
- `claim_links[]` = join table between claims and notes.

## Non-negotiable invariants

1. A note is invalid without `source_id` and `locator`.
2. A claim is invalid without at least one linked note.
3. Strong argumentative claims should have at least one `direct` or `partial` support note.
4. If one sentence contains multiple assertions, split it into multiple `claim_id`s.

## Mapping to final citation audit

At compile time:

1. `claim_id` identifies the sentence or micro-argument.
2. `claim_links` resolves the supporting `note_id`s.
3. Each note resolves its `source_id` and `locator`.
4. The emitter renders:
   - reference slug from `sources.ref_slug`
   - anchor payload from `notes.locator`
5. The audit compares claim text against the retrieved anchored passage.

## Minimal locator policy

Prefer these anchor kinds in order:

1. `quote`
2. `page`
3. `section`
4. `paragraph`

Use `none` only for sources where a precise locator is impossible, and treat those as weaker evidence.
