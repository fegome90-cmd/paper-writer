# OpenAI Complements

Use OpenAI as infrastructure, not as authority.

## Recommended complements

### 1. Structured Outputs for the passport

When extracting `sources`, `notes`, `claims`, or `claim_links`, prefer OpenAI Structured Outputs so the model must match `assets/evidence_passport.schema.json`.

Why:

- stronger shape control than freeform JSON
- easier validator integration
- safer handoff into claim-audit steps

Official docs:

- Responses API: https://platform.openai.com/docs/api-reference/responses/create
- Structured Outputs: https://platform.openai.com/docs/guides/structured-outputs
- Responses migration guide: https://platform.openai.com/docs/guides/migrate-to-responses

### 2. Responses API for multi-step essay agents

Prefer Responses for new integrations that need tool use, stateful turns, or structured extraction.

### 3. Batch API for reviewer committees

If you need many independent reviews or claim audits, Batch is a good fit for asynchronous runs.

Why:

- lower cost
- separate rate-limit pool
- natural fit for reviewer packets and citation verification jobs

Official docs:

- Batch API: https://platform.openai.com/docs/guides/batch/

## Suggested split

- high-stakes synthesis: frontier reasoning model
- bulk note extraction / claim splitting: smaller structured-output-capable model
- asynchronous reviewer packets: Batch API
