# ARS → paper-writer: Porting Opportunities

> Generated from deep code comparison (2026-06-03)
> ARS source: `/tmp/academic-research-skills/scripts/`
> paper-writer: `clients/`, `validators/`, `rules/`

---

## Executive Summary

| Category | Items | Priority |
|----------|-------|----------|
| Bug fixes (429 refresh) | 2 | 🔴 Critical |
| Error handling hardening | 2 | 🔴 High |
| Resiliency patterns | 2 | 🟡 Medium |
| Feature parity gaps | 2 | 🟡 Medium |
| Testability improvements | 1 | 🟢 Low |
| New capability (temporal audit) | 1 system | 🔵 Feature |

---

## 🔴 Critical — Bug Fixes

### 1. 429 Refresh Anchor (CrossrefClient)

**File**: `clients/crossref.py` → `_get()`

**Problem**: After 429 backoff sleep, `_last_request_at` is NOT refreshed. The next outer `_get()` call's throttle calculates elapsed time from the original entry, not the actual wake time. This can cause:
- Under-sleeping (elapsed counts backoff time → thinks more time passed → skips throttle)
- Re-triggering 429

**ARS Pattern** (crossref_client.py:149):
```python
# After backoff sleep:
self._last_request_at = time.monotonic()
```

**Our Current Code**:
```python
except urllib.error.HTTPError as e:
    if e.code == 429 and attempt < MAX_RETRIES:
        time.sleep(BACKOFF_SECONDS * (2**attempt))
        # ← Missing: refresh anchor after sleep
        raise  # or continue
```

**Fix**: Add `self._last_request_at = time.monotonic()` after backoff sleep in `_retry.py` or in each client's error handler.

**Lines affected**: `clients/_retry.py` (shared), or `clients/crossref.py` + `clients/semantic_scholar.py`

---

### 2. 429 Refresh Anchor (SemanticScholarClient)

**File**: `clients/semantic_scholar.py` → `_get()`

**Same issue as #1**. ARS handles it at semantic_scholar_client.py:194.

**Lines affected**: `clients/semantic_scholar.py`

---

## 🔴 High — Error Handling Hardening

### 3. Granular Body Read Error Handling (Crossref)

**File**: `clients/crossref.py` → `_get()`

**Problem**: Uses `except Exception` which catches everything — network errors, parsing errors, programming bugs. ARS distinguishes:

| Exception Type | Meaning | Action |
|----------------|---------|--------|
| `OSError` | Socket drop mid-stream | → `CrossrefUnavailable` (degradation) |
| `http.client.HTTPException` | IncompleteRead (truncated body) | → `CrossrefUnavailable` |
| `UnicodeDecodeError` | Garbled response body | → `CrossrefUnavailable` |
| `json.JSONDecodeError` | Non-JSON response (HTML error page) | → `CrossrefUnavailable` |
| `urllib.error.HTTPError` | HTTP status error | Handle by code (404/429/5xx) |
| `urllib.error.URLError` | Network unreachable | → `CrossrefUnavailable` |

**ARS Pattern** (crossref_client.py:125-140):
```python
try:
    body = resp.read()
    return json.loads(body.decode("utf-8"))
except (OSError, http.client.HTTPException, UnicodeDecodeError, json.JSONDecodeError) as e:
    raise CrossrefUnavailable(f"Crossref response read/parse failed: {e}") from e
```

**Our Current Code**:
```python
def _do_request() -> dict:
    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))
# ↑ Catches ALL exceptions identically
```

**Fix**: Wrap body read in narrow except, re-raise as client-specific error.

**Lines affected**: `clients/crossref.py:174-176`, `clients/semantic_scholar.py:139-141`

---

### 4. Granular Body Read Error Handling (Semantic Scholar)

**File**: `clients/semantic_scholar.py` → `_get()`

**Same pattern as #3**. ARS also latches the client on `OSError`/`TimeoutError` during response read (semantic_scholar_client.py:210-228).

**Lines affected**: `clients/semantic_scholar.py`

---

## 🟡 Medium — Resiliency Patterns

### 5. Outage Latch (SemanticScholarClient)

**File**: `clients/semantic_scholar.py`

**Problem**: Without outage latch, a network failure causes every subsequent entry in a batch to wait full timeout (10s × N entries). ARS latches after first failure:

```python
# ARS semantic_scholar_client.py:95
self._latched_unavailable: bool = False

# On URLError:
self._latched_unavailable = True  # fail fast for rest of batch

# On subsequent calls:
if self._latched_unavailable:
    raise SemanticScholarUnavailable("S2 API latched unavailable")

# Reset between batches:
def reset_outage_latch(self):
    self._latched_unavailable = False
```

**Impact**: For a 50-citation manuscript with S2 outage, current code = 50 × 10s = 500s wait. With latch = 1 × 10s + 49 × instant = 10s.

**Lines affected**: `clients/semantic_scholar.py` (add latch state + check in `_get()`)

---

### 6. OSError/TimeoutError Latch on Read Failure

**File**: `clients/semantic_scholar.py` → `_get()`

**Problem**: ARS latches not just on `URLError` (connection failure) but also on `OSError`/`TimeoutError` during `resp.read()` (socket timeout, connection reset mid-stream). These are transport-level failures that should also trigger fail-fast.

**ARS Pattern** (semantic_scholar_client.py:210-228):
```python
except (OSError, TimeoutError) as e:
    self._latched_unavailable = True
    raise SemanticScholarUnavailable(f"S2 API I/O failure: {e}") from e
```

**Lines affected**: `clients/semantic_scholar.py`

---

## 🟡 Medium — Feature Parity

### 7. Year Tiebreaker in Title Search

**File**: `clients/crossref.py` → `search_by_title()`

**Problem**: ARS gives +0.05 score bonus to candidates with matching publication year. We don't. This means when two titles have similar similarity scores, ARS picks the one with the right year, we pick arbitrarily.

**ARS Pattern** (crossref_client.py:190-191):
```python
year_match = year is not None and _extract_year(cand) == year
score = sim + (0.05 if year_match else 0.0)
```

**Our Code**:
```python
results.sort(key=lambda r: -r.score)
# ↑ No year consideration
```

**Fix**: Add optional `year` param to `search_by_title()`, apply +0.05 bonus.

**Lines affected**: `clients/crossref.py:121-158`, `clients/semantic_scholar.py:86-128`

---

### 8. Polite Email Environment Variable

**File**: `clients/crossref.py` → `__init__()`

**Problem**: ARS automatically reads `CROSSREF_POLITE_EMAIL` from environment. We only accept it via constructor. This means users must pass it explicitly in code rather than just setting an env var.

**ARS Pattern** (crossref_client.py:84):
```python
self._polite_email = polite_email or os.environ.get("CROSSREF_POLITE_EMAIL")
```

**Our Code**:
```python
def __init__(self, email: str | None = None, ...):
    self.email = email  # ← No env var fallback
```

**Fix**: `self.email = email or os.environ.get("CROSSREF_POLITE_EMAIL")`

**Lines affected**: `clients/crossref.py:71-79`

---

## 🟢 Low — Testability

### 9. Dependency Injection (SemanticScholarClient)

**File**: `clients/semantic_scholar.py`

**Problem**: ARS injects `sleep` and `clock` as constructor params, making it trivial to test time-dependent behavior. We hardcode `time.sleep` and `time.monotonic`.

**ARS Pattern** (semantic_scholar_client.py:73-78):
```python
def __init__(self, ..., sleep: Any = time.sleep, clock: Any = time.monotonic):
    self._sleep = sleep
    self._clock = clock
```

**Our Code**:
```python
def __init__(self, ...):
    # time.sleep used directly in _get()
```

**Fix**: Add optional `sleep`/`clock` params with defaults.

**Lines affected**: `clients/semantic_scholar.py:43-51`

---

## 🔵 Feature — Temporal Audit System (NEW)

**Status**: NOT ported. This is a complete new capability.

**ARS Source**: `tests/fixtures/v3.9.4-temporal/` (52 fixture files across 11 modes)

### What It Detects

| Mode | Finding Kind | Severity | Block? | Description |
|------|-------------|----------|--------|-------------|
| 1 | `TEMPORAL-ARITHMETIC-IMPOSSIBLE` | HIGH | ✅ | "As of March 2025, the system completed June 2025 deliverables" |
| 2 | `TEMPORAL-VERSION-EVIDENCE` | MEDIUM | ❌ | Using version X to prove something about version Y |
| 3 | `TEMPORAL-METADATA-MISSING` | LOW | ❌ | Missing date metadata prevents anachronism check |
| 4 | `TEMPORAL-CAUSAL-INVERSION` | MEDIUM | ❌ | "Policy A (2026) enabled Policy B (2020)" |
| 5 | `TEMPORAL-DEICTIC` | LOW | ❌ | "Currently", "most recent", "today" |

### Required Infrastructure

| Component | Description | Effort |
|-----------|-------------|--------|
| `timeline.yaml` parser | Load citation publication dates with precision/confidence | Small |
| `citation_provenance.yaml` parser | Load provenance metadata | Small |
| Deictic detector | Regex-based: "currently", "today", "most recent", "as of" | Medium |
| Temporal arithmetic checker | Compare date ranges: anchor vs event | Medium |
| Causal verb lexicon | "enabled", "caused", "preceded", "followed" + ordering rules | Medium |
| `temporal_audit()` validator | Main orchestrator | Large |
| YAML rule file | `rules/temporal/deictic.yml`, `rules/temporal/causal_inversion.yml`, etc. | Medium |

### Fixture Structure (ARS)

```
tests/fixtures/v3.9.4-temporal/
├── mode_1_future_as_past/
│   ├── draft.md                    # Manuscript with temporal issue
│   ├── citation_provenance.yaml    # Citation metadata
│   ├── timeline.yaml               # Publication dates
│   └── expected_temporal_audit_results.yaml  # Expected findings
├── mode_4_causal_inversion/
│   ├── draft.md
│   ├── citation_provenance.yaml
│   ├── timeline.yaml
│   └── expected_temporal_audit_results.yaml
├── mode_5_time_bomb/
│   └── ... (same structure)
└── report_reference_date_freeze/
    └── ... (same structure)
```

### Effort Estimate

| Phase | Tasks | Days |
|-------|-------|------|
| Parsers (timeline + provenance) | 2 | 0.5 |
| Deictic detector | 1 | 0.5 |
| Temporal arithmetic | 1 | 1 |
| Causal inversion | 1 | 1 |
| YAML rules | 3-4 | 0.5 |
| Validator orchestrator | 1 | 1 |
| Tests (using ARS fixtures) | 5-6 | 1 |
| CLI subcommand | 1 | 0.5 |
| **Total** | | **~6 days** |

---

## Implementation Priority Matrix

| # | Item | Effort | Impact | Risk | Do First? |
|---|------|--------|--------|------|-----------|
| 1 | 429 refresh anchor (Crossref) | 2 lines | Critical | None | ✅ YES |
| 2 | 429 refresh anchor (S2) | 2 lines | Critical | None | ✅ YES |
| 3 | Body read errors (Crossref) | 10 lines | High | Low | ✅ YES |
| 4 | Body read errors (S2) | 10 lines | High | Low | ✅ YES |
| 5 | Outage latch (S2) | 15 lines | Medium | Low | Next |
| 6 | OSError/TimeoutError latch | 5 lines | Medium | Low | Next |
| 7 | Year tiebreaker | 10 lines | Medium | None | Next |
| 8 | Polite email env var | 1 line | Low | None | Quick win |
| 9 | DI for testability | 5 lines | Low | None | When testing |
| 10 | Temporal audit system | ~500 lines | High | Medium | Feature scope |

---

## Quick Wins (< 5 min each)

1. **Polite email env var** — 1 line change in `crossref.py:71`
2. **429 refresh anchor** — 1 line each in `_retry.py` or both clients
3. **Year tiebreaker** — Add `year` param to `search_by_title()` in both clients

---

*Last updated: 2026-06-03*
