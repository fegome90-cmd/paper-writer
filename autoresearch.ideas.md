# Autoresearch Ideas — Session 7 (2026-06-05): Consensus OpenAPI Audit

## Applied (11 experiments, 11 kept, 0 discarded)

### OpenAPI Spec Alignment (#365-#368)
1. **Baseline: 0/3 gaps** — limit sent to API but spec has no limit param, pages+volume not parsed, 0/6 filter params
2. **3 gaps resolved** (#366) — removed limit from API params, added pages+volume to extra_fields, added 8 filter params
3. **Baseline: 0/5 remaining gaps** — 4 missing filter params + sjr_max no validation
4. **5 gaps resolved** (#368) — added duration_min/max, publisher_name, clinical_guideline + sjr_max 1-4 validation

### Filter Passthrough (#369-#374)
5. **Baseline: 0 filters accessible via search()** — _call_api had 12 filters but search() didn't forward
6. **12 filters via search()** (#370) — added **kwargs to search(), forwarded to _call_api
7. **Baseline: adapter extracts 0 filter params** — provider.search(query, limit) with no filters
8. **12 filters through adapter** (#372) — _FILTER_KEYS extraction + **kwargs forwarding
9. **Baseline: CLI exposes 0 filter args** — only --query and --raw-papers
10. **12 CLI filter args** (#374) — all OpenAPI params as argparse args

### Critical Bug Fix (#375)
11. **CRITICAL: non-Consensus providers crash** — FixturePaperSearchProvider/McpPaperSearchProvider
    don't accept **kwargs → TypeError when adapter forwards filters. Fixed by adding **kwargs
    to ABC and all 3 implementations.

## Audit Summary

| Layer | Status | Details |
|-------|--------|---------|
| OpenAPI Spec | FULL | 12/12 params, 12/12 response fields, auth, enum, validation |
| Provider | FULL | search(**filters) → _call_api(**filters) |
| Adapter | FULL | _FILTER_KEYS extraction + **kwargs forwarding |
| CLI | FULL | 12 --filter args in argparse |
| Cross-provider | FIXED | **kwargs in ABC, Fixture, MCP providers |
| Tests | 1416 pass | 30 consensus-specific + 1 adapter filter test |

## Remaining ideas (deferred)

- **R1: Response schema validation** — validate API responses against QueryResult spec
- **R2: Rate limiting** — parse Retry-After header on 429, backoff strategy
- **R3: 422 Validation Error** — spec defines HTTPValidationError, parse detail array
- **R4: Provider capability query** — method to check which filters a provider supports
- **R5: Integration test with real API** — extend smoke test to cover filter params
