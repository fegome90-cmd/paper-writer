# Structured Output Complements

Use LLM providers as infrastructure, not as authority.

## Recommended complements

### 1. Structured outputs for the passport

When extracting `sources`, `notes`, `claims`, or `claim_links`, prefer structured outputs (JSON schema, tool use, or function calling) so the model must match `assets/evidence_passport.schema.json`.

Why:

- stronger shape control than freeform JSON
- easier validator integration
- safer handoff into claim-audit steps

Provider options:

- OpenAI: Structured Outputs via Responses API
- Anthropic: Tool use with `tool_choice` enforcement
- Google Gemini: Function calling with schema validation

### 2. Agent frameworks for multi-step essay pipelines

Prefer agent-style APIs for integrations that need tool use, stateful turns, or structured extraction. Options include OpenAI Responses API, Anthropic tool use, and Gemini function calling.

### 3. Batch processing for reviewer committees

If you need many independent reviews or claim audits, asynchronous batch processing is a good fit.

Why:

- lower cost
- separate rate-limit pool
- natural fit for reviewer packets and citation verification jobs

Provider options:

- OpenAI: Batch API
- Anthropic: Message Batches API
- Google Gemini: Batch prediction

## Suggested split

- high-stakes synthesis: frontier reasoning model
- bulk note extraction / claim splitting: smaller structured-output-capable model
- asynchronous reviewer packets: batch processing
