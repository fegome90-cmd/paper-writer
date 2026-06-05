# MCP Inspection Memo — paper-mcp → paper-writer integration

**Date**: 2026-06-05
**Status**: Pre-implementation contract. No code written.

---

## 1. Server Start Command (stdio)

```
node /Users/felipe_gonzalez/.openclaw/mcp-servers/paper-mcp/dist/server.js
```

No arguments required. Server listens on stdin/stdout (JSON-RPC 2.0 over MCP protocol).
Node >= 18 required. No API keys required (degraded rate limits without them).

StdioServerParameters for SDK:
```python
StdioServerParameters(
    command="node",
    args=["/Users/felipe_gonzalez/.openclaw/mcp-servers/paper-mcp/dist/server.js"],
)
```

Server info: `paper-mcp` v0.4.0. Capabilities: tools + resources + prompts.

---

## 2. Tool Name

**`search_papers`** — the primary search tool.

Secondary tools available but not needed for this batch:
- `fetch_paper` (id + source → single paper detail)
- `advanced_search` (boolean queries)
- `fetch_latest`, `trend_analysis`, `list_categories`, `manage_cache`, `smart_cache_search`

---

## 3. Input Schema (search_papers)

```json
{
  "type": "object",
  "required": ["query"],
  "properties": {
    "query":         { "type": "string",  "description": "Search query keywords" },
    "sources":       { "type": "array",   "items": { "type": "string", "enum": [
                       "arxiv","openalex","pmc","europepmc","biorxiv","medrxiv",
                       "core","semantic-scholar","crossref","pubmed","google-scholar","iacr"
                     ]}},
    "field":         { "type": "string",  "enum": ["all","title","abstract","author","keywords","fulltext"] },
    "categories":    { "type": "array",   "items": { "type": "string" } },
    "sortBy":        { "type": "string",  "enum": ["relevance","date","citations","title"] },
    "sortOrder":     { "type": "string",  "enum": ["asc","desc"] },
    "limit":         { "type": "number",  "description": "Max results per platform (default: 10, max: 100)" },
    "offset":        { "type": "number" }
  }
}
```

---

## 4. Output Schema (search_papers)

```json
{
  "results": [
    {
      "id":                "string",    // platform-specific ID (e.g., "2605.26355v1")
      "title":             "string",
      "authors":           ["string"],
      "abstract":          "string",
      "published":         "string",    // ISO 8601 datetime
      "source":            "string",    // e.g., "arxiv", "pubmed"
      "doi":               "string | undefined",     // NOT always present
      "pdfUrl":            "string | undefined",      // NOT always present
      "url":               "string | undefined",
      "categories":        ["string"] | undefined,    // NOT always present
      "fullTextAvailable":  "bool | undefined",       // NOT always present
      "citations":          "int | undefined"          // openalex only
    }
  ],
  "total":              "int",           // total matches across platforms
  "sources":            ["string"],      // platforms queried
  "totalBySource":      { "source": int }
}
```

### Field presence by source (verified empirically)

| Field        | arxiv | pubmed | openalex |
|-------------|-------|--------|----------|
| id          | ✅    | ✅     | ✅       |
| title       | ✅    | ✅     | ✅       |
| authors     | ✅    | ✅     | ✅       |
| abstract    | ✅    | ✅     | ✅       |
| published   | ✅    | ✅     | ✅       |
| source      | ✅    | ✅     | ✅       |
| doi         | ✅*   | ✅     | ✅       |
| pdfUrl      | ✅    | ❌     | ✅       |
| url         | ✅    | ✅     | ✅       |
| categories  | ✅    | ❌     | ✅       |
| fullTextAvailable | ✅ | ❌   | ✅       |
| citations   | ❌    | ❌     | ✅       |

`*` arXiv DOI not always present (preprints).

---

## 5. Real Payload (anonymized fixture)

```json
{
  "results": [
    {
      "id": "2605.26355v1",
      "title": "Energy-Gated Attention and Wavelet Positional Encoding",
      "authors": ["Author A"],
      "abstract": "Standard transformer attention computes pairwise token similarity...",
      "published": "2026-05-25T22:04:31.000Z",
      "source": "arxiv",
      "doi": null,
      "pdfUrl": "https://arxiv.org/pdf/2605.26355v1",
      "url": "https://arxiv.org/abs/2605.26355v1",
      "categories": ["cs.LG", "cs.CL"],
      "fullTextAvailable": true
    },
    {
      "id": "37979413",
      "title": "An overview of clinical machine learning applications in neurology",
      "authors": ["Author B", "Author C"],
      "abstract": "Machine learning techniques for clinical applications...",
      "published": "2023-12-15T03:00:00.000Z",
      "source": "pubmed",
      "doi": "10.1016/j.jns.2023.122799",
      "url": "https://pubmed.ncbi.nlm.nih.gov/37979413/",
      "pdfUrl": null,
      "categories": null,
      "fullTextAvailable": null
    }
  ],
  "total": 624756,
  "sources": ["arxiv", "pubmed"],
  "totalBySource": { "arxiv": 306084, "pubmed": 318672 }
}
```

---

## 6. Mapping: MCP field → paper-writer field

The adapter must normalize MCP results into the paper dict format consumed by `search.py`.
Current format (from `_make_paper` in tests):

```python
{
    "title": str,
    "doi": str | None,
    "pmid": str | None,
    "year": int,
    "authors": str,         # "Author et al." — free-form string
}
```

After scoring (`raw_results.json`), papers have additional fields:
```python
{
    "title": str,
    "doi": str | None,
    "pmid": str | None,
    "year": int,
    "authors": str,
    "abstract": str,         # Used by CS scoring
    "_search_query": str,    # Injected by search pipeline
    "scoring": { ... },      # Added by scoring pipeline
}
```

### Normalization matrix

| paper-writer field | MCP source                | Transform                     |
|--------------------|---------------------------|-------------------------------|
| `title`           | `result.title`            | Direct copy                   |
| `doi`             | `result.doi`              | `None` if absent              |
| `pmid`            | `result.id`               | Only if `source == "pubmed"`  |
| `year`            | `result.published`        | `int(published[:4])`          |
| `authors`         | `result.authors`          | `", ".join(authors[:3]) + (" et al." if len>3 else "")` |
| `abstract`        | `result.abstract`         | `""` if absent                |
| `url`             | `result.url`              | Direct copy                   |
| `pdf_url`         | `result.pdfUrl`           | `None` if absent              |
| `source_platform` | `result.source`           | Direct copy (new field)       |
| `source_id`       | `result.id`               | Direct copy (new field)       |
| `categories`      | `result.categories`       | `[]` if absent                |
| `citations_count` | `result.citations`        | `0` if absent                 |

---

## 7. Fields required by scoring that MCP does NOT provide

### Clinical scoring (PaperMetrics) — ALL fields are synthetic

The clinical scoring path reads `paper["metrics"]` dict:
- `population_score`, `intervention_score`, `outcome_score`, `context_score`
- `evidence_score`, `sample_score`, `journal_score`, `citations_score`, `coi_penalty`

**None of these come from MCP.** They must be computed or defaulted.

Current behavior: `_extract_metrics()` falls back to `m.get("score_field", 0.0)` for each.
When `metrics` key is absent from the paper dict, **all scores default to 0.0**.

### CS scoring (CSMetrics) — partially available from MCP

| CS field         | MCP source            | Available? |
|------------------|-----------------------|------------|
| `venue_tier`     | inferred from source  | Partial (arXiv ≠ journal) |
| `recency_score`  | `published` year      | ✅ Can compute |
| `citation_score` | `result.citations`    | Partial (OpenAlex only) |
| `relevance_score`| keyword overlap       | ✅ Computed from abstract + query |
| `rigor_score`    | keywords in abstract  | ✅ Computed |

**Decision**: Domain detection (`detect_domain`) routes automatically. CS papers from MCP
get CS scoring (partial data). Clinical papers get clinical scoring (all zeros without LLM).
This is the EXISTING behavior — the provider integration does NOT change scoring.

---

## 8. Error / Null / Timeout / Unavailability Policy

### Explicit modes via `PAPER_SEARCH_PROVIDER` env var

| Mode       | Behavior                                           |
|-----------|-----------------------------------------------------|
| `fixture`  | Deterministic data from JSON file. No network. Default for tests. |
| `mcp`      | Call paper-mcp server. **Fail visibly** if unavailable. Never degrade to mock. |

### Error handling (MCP mode)

| Condition              | Behavior                                           |
|------------------------|----------------------------------------------------|
| Server process fails to start | `RuntimeError("MCP server failed to start: ...")` — propagate, do NOT fall back |
| Session init timeout (>10s)    | `TimeoutError("MCP server initialization timed out")` — propagate |
| Tool call timeout (>30s)       | `TimeoutError("MCP search_papers timed out")` — propagate |
| Server returns error response  | `RuntimeError("MCP tool error: {message}")` — propagate |
| Zero results from MCP          | Valid response — return empty list. Do NOT fall back. |
| MCP field is `null`/absent     | Normalize to sensible default (see §6 transforms) |

### Key principle: NO silent degradation in MCP mode

If the user selected MCP mode and it fails, the error reaches the CLI output.
The user chose real data — they want to know if it's unavailable.

---

## 9. Dependencies

### New dependency: `mcp[cli]`

```toml
[project.optional-dependencies]
mcp = ["mcp[cli]>=1.0"]
```

**Justification**: Official Python MCP SDK. Handles:
- Session initialization (`ClientSession.initialize()`)
- Capability negotiation (`get_server_capabilities()`)
- Tool invocation (`call_tool()`)
- Process lifecycle management (`stdio_client` context manager)
- stderr capture via `errlog` parameter
- Timeout via `asyncio.timeout()` wrapping calls

No subprocess hacking. No manual JSON-RPC. The SDK manages the Node.js child process.

### Not needed
- `httpx`, `aiohttp`, `requests` — SDK handles transport
- No changes to existing dependencies

---

## 10. Proposed File Changes

### New files

| File | Purpose |
|------|---------|
| `harness/ports/paper_search_provider.py` | Protocol + two implementations (~150 lines) |
| `integrations/tools/mcp_paper_client.py` | MCP SDK wrapper (~80 lines) |
| `tests/integrations/test_mcp_paper_client.py` | Unit tests with mock provider (~100 lines) |
| `tests/integrations/test_paper_search_provider.py` | Provider interface tests (~80 lines) |
| `tests/fixtures/search_fixture.json` | Deterministic fixture data (~50 lines) |
| `tests/smoke/test_mcp_search_smoke.py` | Real MCP smoke test (marked slow) (~40 lines) |

### Modified files

| File | Change | Lines changed |
|------|--------|---------------|
| `skills/local/adapters.py` | `LiteratureSearchAdapter._handle_search()` injects provider when no `raw_papers` | ~20 lines added |
| `pyproject.toml` | Add `mcp[cli]` optional dependency | ~3 lines |
| `.env.example` | Document `PAPER_SEARCH_PROVIDER`, `MCP_SERVER_PATH` | ~5 lines |

### NOT modified (explicitly)

- `harness/services/orchestrator.py` — no changes
- `harness/domain/state.py` — no changes
- `harness/services/gates.py` — no changes
- `harness/adapters/filesystem_action_runner.py` — no changes (adapter already registered)
- `skills/imported/literature_search/scoring*.py` — no scoring changes
- `cli/paper/main.py` — no changes (adapter already wired)

### Architecture diagram

```
┌─────────────┐     ┌──────────────────────┐     ┌──────────────┐
│  CLI main   │────▶│  Orchestrator        │────▶│  Action      │
│  (untouched)│     │  (untouched)         │     │  Runner      │
└─────────────┘     └──────────────────────┘     │  (untouched) │
                                                  └──────┬───────┘
                                                         │ skill_adapters
                                                  ┌──────▼───────┐
                                                  │  Literature  │
                                                  │  Search      │
                                                  │  Adapter     │
                                                  └──────┬───────┘
                                                         │ NEW: injects provider
                                    ┌────────────────────▼────────────────────┐
                                    │         PaperSearchProvider             │
                                    │  (Protocol)                             │
                                    ├──────────────────┬──────────────────────┤
                                    │  FixtureProvider │  McpPaperProvider    │
                                    │  (deterministic) │  (calls paper-mcp    │
                                    │                  │   via SDK)           │
                                    └──────────────────┴──────────────────────┘
```

### Provenance metadata (normalized_results.json)

```json
{
  "provenance": {
    "provider": "mcp",
    "query": "transformer attention",
    "retrieved_at": "2026-06-05T10:34:33Z",
    "tool_name": "search_papers",
    "sources": ["arxiv", "pubmed"],
    "schema_version": "1.0",
    "server_info": { "name": "paper-mcp", "version": "0.4.0" }
  },
  "results": [ ... normalized paper dicts ... ]
}
```

### Separation: raw_results.json vs normalized_results.json

- `raw_results.json`: MCP response as-is (provenance + raw MCP data). Written by provider.
- `normalized_results.json`: papers in paper-writer format, ready for scoring pipeline.
  Written by the adapter after normalization. This is what `search.py` reads.

---

## Open questions for user decision

1. **Default sources**: Which platforms should `mcp` mode query by default?
   Proposal: `["arxiv", "openalex", "pubmed"]` — broad coverage, no API keys needed.

2. **Default limit**: How many papers per search?
   Proposal: `20` (enough for scoring diversity, not excessive).

3. **MCP server path**: Hardcode or configurable?
   Proposal: `PAPER_MCP_SERVER_PATH` env var with sensible default.

4. **Fixture file location**: `tests/fixtures/search_fixture.json` or `skills/imported/literature_search/fixtures/`?
   Proposal: `tests/fixtures/` — test-only data stays in tests.
