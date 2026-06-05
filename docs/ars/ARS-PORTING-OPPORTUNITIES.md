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
| New capability (temporal audit) | 5 passes + bootstrap + 15 tests | 🔵 Feature (~1,160 lines, ~7 days) |

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

**Status**: NOT ported. Complete new capability — 840-line Python script + 438-line test file + 52 fixture files.

**ARS Source Files**:
- `scripts/temporal_integrity_audit.py` (840 lines) — main implementation
- `scripts/test_temporal_integrity_audit.py` (438 lines) — test suite
- `scripts/bootstrap_timeline_yaml.py` (137 lines) — timeline bootstrap from Crossref
- `tests/fixtures/v3.9.4-temporal/` — 11 fixture directories, 52 files

### Architecture: 5-Pass Verifier

The temporal audit runs 5 sequential passes over the draft, each detecting a different class of temporal integrity issue:

```
Pass 1 → TEMPORAL-ARITHMETIC-IMPOSSIBLE (Mode 1)
Pass 2 → TEMPORAL-ANACHRONISTIC-CITATION (Mode 2)
Pass 3 → TEMPORAL-COMPARATOR-UNMATERIALIZED (Mode 3)
Pass 4 → TEMPORAL-CAUSAL-INVERSION (Mode 4)
Pass 5 → TEMPORAL-DEICTIC (Mode 5)
+ TEMPORAL-METADATA-MISSING (cross-cutting)
```

### Pass 1: Future-as-Past Arithmetic (Mode 1)

**Finding Kind**: `TEMPORAL-ARITHMETIC-IMPOSSIBLE`
**Severity**: HIGH | **Block eligible**: YES

**What it catches**: Claims where the event date is after the anchor date, making the statement physically impossible.

**Two regex patterns**:

```python
# Pattern A: retrospective "as of X ... had already Y"
PATTERN_A = re.compile(
    r"(?:as of|on|in|reported in|stated in|noted in)\s+"
    r"(?P<anchor>" + DATE_REGEX + r")"
    r".*?\b(?:had already|already|completed|finished|delivered)\b.*?"
    r"(?P<event>" + DATE_REGEX + r")",
    re.IGNORECASE | re.DOTALL,
)

# Pattern B: prospective "X (will be) ... (as of Y)"
PATTERN_B = re.compile(
    r"(?P<event>" + DATE_REGEX + r")"
    r".*?\b(?:will be|to be|scheduled for|forthcoming|upcoming|planned)\b.*?"
    r"(?:as of|in|by)\s+"
    r"(?P<anchor>" + DATE_REGEX + r")",
    re.IGNORECASE | re.DOTALL,
)
```

**Violation logic**:
- Pattern A: `event_start > anchor_end` → impossible (event hasn't happened yet at anchor time)
- Pattern B: `event_start <= anchor_end` → impossible (forthcoming event already past at anchor time)

**Fixture examples**:
| Draft | Verdict | Why |
|-------|---------|-----|
| "As of March 2025, the system had already completed June 2025 deliverables" | VIOLATION | Event (June 2025) > Anchor (March 2025) |
| "Smith (2026) reports that programme X completed its 2025 cycle in December 2025" | OK | No "as of" anchor pattern |

### Pass 2: Version-as-Evidence Anachronism (Mode 2)

**Finding Kind**: `TEMPORAL-ANACHRONISTIC-CITATION`
**Severity**: HIGH | **Block eligible**: YES

**What it catches**: Citing a version of a document that didn't exist yet at the time of the event being described.

**How it works**:
1. Find all `<!--ref:slug-->` markers in draft
2. Look up slug in `timeline.yaml` → get `effective_date_range`
3. Find nearest date in ±200 chars around ref marker (the "event date")
4. Check two predicates:
   - **Future-version**: `edr_start > event_end` → version postdates the event
   - **Superseded-version**: `edr_end < event_start` → version was superseded before event

**Requires**: `timeline.yaml` with `effective_date_range` per source.

**Fixture examples**:
| Draft | Timeline | Verdict |
|-------|----------|---------|
| "The 2026 Handbook governed the 2022 review cycle" | handbook-2026ed starts 2026-09-15 | VIOLATION — 2026 version didn't exist in 2022 |
| "The 2020 Handbook governed the 2022 review cycle" | handbook-2020ed range 2020-10-01..2024-09-30 | OK — version was in effect during 2022 |

**Provenance gate** (v3.9.4.1 hotfix): If `citation_provenance` confidence is `low` or `conflict`, emits `TEMPORAL-METADATA-MISSING` instead — doesn't use unverified dates as ground truth.

### Pass 3: Comparator Unmaterialized (Mode 3)

**Finding Kind**: `TEMPORAL-COMPARATOR-UNMATERIALIZED`
**Severity**: MEDIUM | **Block eligible**: NO

**What it catches**: Prose references a specific year/edition that doesn't exist in the timeline.

**Three regex forms**:
```python
# Form A: "prior/previous/earlier edition"
COMPARATOR_FORM_A = re.compile(
    r"(?P<adj>prior|previous|earlier|older|preceding)\s+"
    r"(?P<noun>edition|version|...)", re.IGNORECASE)

# Form B: "YYYY edition/version/standard"
COMPARATOR_FORM_B = re.compile(
    r"\b(?P<year>(?:19|20)\d{2})\s+"
    r"(?P<noun>edition|version|standard|handbook|guideline)", re.IGNORECASE)

# Form C: "edition/version of YYYY"
COMPARATOR_FORM_C = re.compile(
    r"(?P<noun>edition|version|standard)\s+(?:of|from)\s+"
    r"(?P<year>(?:19|20)\d{2})", re.IGNORECASE)
```

**Logic**: For each match, resolve `version_family_id` via nearest `<!--ref:slug-->`. Check if any source in that family has a `published_date` matching the comparator year. If not → emit finding.

**Fixture examples**:
| Draft | Timeline | Verdict |
|-------|----------|---------|
| "This differs from the 1998 edition" + ref:standard-2020ed | standard-family has only 2020 | VIOLATION — 1998 edition not in timeline |
| "This differs from the 2018 edition" + ref:standard-2020ed | standard-family has 2018 + 2020 | OK |

### Pass 4: Causal Inversion (Mode 4)

**Finding Kind**: `TEMPORAL-CAUSAL-INVERSION`
**Severity**: MEDIUM | **Block eligible**: NO

**What it catches**: Causal claims where the cause comes after the effect.

**8 causal trigger verbs with required ordering**:
```python
CAUSAL_TRIGGERS = [
    (r"\benabled\b",          "left<right"),  # cause before effect
    (r"\bcaused\b",           "left<right"),
    (r"\bled\s+to\b",         "left<right"),
    (r"\bin\s+response\s+to\b", "left>right"),  # effect after cause
    (r"\bsuperseded\b",       "left>right"),
    (r"\bpreceded\b",         "left<right"),
    (r"\bfollowed\s+by\b",    "left<right"),
    (r"\bfollowed\b(?!\s+by)", "left>right"),
]
```

**Binding logic**: For each trigger, bind left argument (nearest `<!--ref:slug-->` BEFORE trigger, or direct date) and right argument (nearest `<!--ref:slug-->` AFTER trigger, or direct date). Then verify required ordering.

**v3.9.4.1 hotfix**: Also binds to direct date captures when ref markers are absent (not just slugs).

**Fixture examples**:
| Draft | Timeline | Verdict |
|-------|----------|---------|
| "Policy A enabled Policy B" | A=2026, B=2020 | VIOLATION — cause (2026) > effect (2020) |
| "Policy A enabled Policy B" | A=2020, B=2026 | OK — cause before effect |

### Pass 5: Deictic Time-Bomb (Mode 5)

**Finding Kind**: `TEMPORAL-DEICTIC`
**Severity**: LOW | **Block eligible**: NO

**What it catches**: Temporal deictic expressions that anchor claims to writing time, making them stale over time.

**Regex pattern**:
```python
DEICTIC_PATTERN = re.compile(
    r"\b(currently|now|at present|most recent|the latest|new(?:est)?|recently|"
    r"last\s+year|this\s+year|nowadays|presently|today|emerging|recent\s+cycle|"
    r"latest\s+available)\b",
    re.IGNORECASE,
)
```

**Fixture examples**:
| Draft | Verdict |
|-------|---------|
| "Currently, the framework is under review" | VIOLATION — "Currently" is deictic |
| "Currently, the most recent edition prescribes" | VIOLATION — "Currently" + "most recent" (2 findings) |
| "As of 2026-05-18, the 2024 edition prescribes" | OK — anchored to specific date |

### Cross-Cutting: TEMPORAL-METADATA-MISSING

**Severity**: LOW | **Block eligible**: NO

**Fires when** (in P2 or P4):
- `<!--ref:slug-->` has no entry in `timeline.yaml`
- `effective_date_range` is absent
- `effective_date_range.start` is null or low/unverified confidence
- `citation_provenance` confidence is `low` or `conflict`

### Date Normalization: `_date_to_interval()`

Handles 5 schema-valid date shapes:

| Input | Output | Precision |
|-------|--------|-----------|
| `2024-09-15` | `(2024-09-15, 2024-09-15)` | Day |
| `2024-09` | `(2024-09-01, 2024-09-30)` | Month |
| `2024` | `(2024-01-01, 2024-12-31)` | Year |
| `March 2025` | `(2025-03-01, 2025-03-31)` | Prose month |
| `2022-04-01..2022-12-31` | `(2022-04-01, 2022-12-31)` | Interval |

### Input File Schemas

**`timeline.yaml`**:
```yaml
schema_version: "1.0"
sources:
  - citation_key: handbook-2026ed
    type: institutional-document
    published_date:
      value: "2026-09-15"
      precision: day
      open_ended: false
      provenance:
        method: crossref_lookup
        confidence: high
    effective_date_range:
      start:
        value: "2026-09-15"
        precision: day
        open_ended: false
        provenance: {method: crossref_lookup, confidence: high}
      end:
        value: null
        precision: unknown
        open_ended: true
        provenance: {method: user_override, confidence: high}
    version_family_id: handbook-family  # optional
events: []
```

**`citation_provenance.yaml`**:
```yaml
schema_version: "1.0"
audit_run_id: "2026-05-18T12:34:56Z-a1b2"
entries:
  - citation_key: handbook-2026ed
    crossref_issued: null
    pdftotext_cover_first_line: null
    verification_method: none
    confidence: low  # high | medium | low | conflict
    notes: null
```

### Output Schema

```yaml
schema_version: "1.0"
audit_run_id: "2026-05-18T12:34:56Z-a1b2"
report_reference_date: "2026-05-18"
findings:
  - finding_id: "TF-001"
    finding_kind: "TEMPORAL-ARITHMETIC-IMPOSSIBLE"
    severity: "HIGH"
    mode: 1
    block_eligible: true
    draft_locator:
      file: "phase4_composition/draft.md"
      line: 1
      sentence: "As of March 2025, ..."
    matched_span: {text: "currently", char_start: 0, char_end: 9}
    bound_refs: [{ref_slug: "slug", timeline_entry: "slug"}]
    bound_event: {event_id: null, date: "2022-01-01..2022-12-31"}
    bound_dates:
      left: {role: "anchor", value: "2025-03-01..2025-03-31", source: "draft_capture"}
      right: {role: "event", value: "2025-06-01..2025-06-30", source: "draft_capture"}
    rationale: "Pattern A: anchor 'March 2025' before event 'June 2025'"
    suggested_fix: "Restate the claim to match the anchor's true time horizon"
```

### Test Suite Patterns (438 lines)

| Test | What it verifies |
|------|-----------------|
| `test_p5_currently_emits_deictic_finding` | "Currently" → TEMPORAL-DEICTIC |
| `test_p5_anchored_phrase_no_finding` | "As of 2026-05-18" → no finding |
| `test_p1_future_as_past_emits_arithmetic_impossible` | Pattern A violation |
| `test_p1_prospective_already_past` | Pattern B violation |
| `test_p2_2026_handbook_governing_2022_event` | Anachronistic citation |
| `test_p3_unmaterialized_comparator` | "1998 edition" not in timeline |
| `test_p4_causal_inversion` | "enabled" with wrong ordering |
| `test_positive_fixture_golden` | 5 parametrized golden tests (modes 1-5) |
| `test_negative_fixture_golden` | 5 parametrized legitimate tests (modes 1-5) |
| `test_audit_writes_markdown_report` | YAML + MD output |
| `test_metadata_missing_fixture` | Missing effective_date_range |
| `test_freeze_regression_byte_identical` | Same date → byte-identical output |
| `test_date_to_interval_parses_all_shapes` | 8 date format parametrized tests |
| `test_p2_provenance_low_emits_metadata_missing` | Provenance confidence gate |
| `test_p4_direct_date_causal_inversion_no_refs` | Direct date binding (no slugs) |

### Bootstrap Timeline Script

`bootstrap_timeline_yaml.py` — Populates `timeline.yaml` from `literature_corpus[]`:
1. For each entry with `doi`: calls Crossref API for `published_date`
2. For each entry with local PDF: runs `pdftotext` for first-line scan
3. Emits skeleton with `effective_date_range`, `supersedes`, etc. as null
4. Supports `--dry-run` (no API calls, uses corpus year fallback)

### Fixture Directory Structure (11 fixtures)

```
tests/fixtures/v3.9.4-temporal/
├── mode_1_future_as_past/          # P1 VIOLATION
│   ├── draft.md                    # "As of March 2025, ... June 2025 deliverables"
│   ├── citation_provenance.yaml    # Empty entries
│   ├── timeline.yaml               # Empty sources
│   └── expected_temporal_audit_results.yaml  # 1 TEMPORAL-ARITHMETIC-IMPOSSIBLE
├── mode_1_legitimate/              # P1 OK
│   ├── draft.md                    # "Smith (2026) reports ... December 2025"
│   └── expected_temporal_audit_results.yaml  # 0 findings
├── mode_2_version_as_evidence_past/ # P2 VIOLATION
│   ├── draft.md                    # "2026 Handbook governed 2022 review cycle"
│   ├── timeline.yaml               # handbook-2026ed starts 2026-09-15
│   └── expected_temporal_audit_results.yaml  # 1 TEMPORAL-ANACHRONISTIC-CITATION
├── mode_2_legitimate/              # P2 OK
│   ├── draft.md                    # "2020 Handbook governed 2022 review cycle"
│   ├── timeline.yaml               # handbook-2020ed range 2020-10-01..2024-09-30
│   └── expected_temporal_audit_results.yaml  # 0 findings
├── mode_3_comparator_unmaterialized/ # P3 VIOLATION
│   ├── draft.md                    # "differs from the 1998 edition"
│   ├── timeline.yaml               # standard-family has only 2020
│   └── expected_temporal_audit_results.yaml  # 1 METADATA-MISSING + 1 COMPARATOR-UNMATERIALIZED
├── mode_3_legitimate/              # P3 OK
│   ├── draft.md                    # "differs from the 2018 edition"
│   ├── timeline.yaml               # standard-family has 2018 + 2020
│   └── expected_temporal_audit_results.yaml  # 1 METADATA-MISSING (no edr)
├── mode_4_causal_inversion/        # P4 VIOLATION
│   ├── draft.md                    # "Policy A enabled Policy B"
│   ├── timeline.yaml               # A=2026, B=2020 (wrong order)
│   └── expected_temporal_audit_results.yaml  # 2 METADATA-MISSING + 1 CAUSAL-INVERSION
├── mode_4_legitimate/              # P4 OK
│   ├── draft.md                    # "Policy A enabled Policy B"
│   ├── timeline.yaml               # A=2020, B=2026 (correct order)
│   └── expected_temporal_audit_results.yaml  # 2 METADATA-MISSING (no edr)
├── mode_5_time_bomb/               # P5 VIOLATION
│   ├── draft.md                    # "Currently, the most recent edition..."
│   └── expected_temporal_audit_results.yaml  # 2 TEMPORAL-DEICTIC
├── mode_5_legitimate/              # P5 OK
│   ├── draft.md                    # "As of 2026-05-18, the 2024 edition..."
│   └── expected_temporal_audit_results.yaml  # 0 findings
├── metadata_missing_p2/            # Cross-cutting
│   ├── draft.md                    # "handbook governed 2022 review cycle"
│   ├── timeline.yaml               # handbook-2024ed has no effective_date_range
│   └── expected_temporal_audit_results.yaml  # 1 METADATA-MISSING
└── report_reference_date_freeze/   # Regression
    ├── draft.md                    # "Currently, the framework..."
    └── expected_temporal_audit_results.yaml  # 1 TEMPORAL-DEICTIC
```

### Key Implementation Details

1. **Sentence splitting**: Uses `re.split(r"(?<=[.!?])\s+", draft)` — splits on sentence terminators
2. **Line numbers**: Computed via `draft[:char_pos].count("\n") + 1`
3. **Ref markers**: `<!--ref:slug-->` HTML comments — parsed via `REF_MARKER_PATTERN`
4. **Event window**: ±200 chars around ref marker for nearest-date binding
5. **Report reference date**: Frozen via CLI arg — not `datetime.now()` — ensures deterministic output
6. **Markdown output**: `_render_markdown()` generates human-readable `.md` alongside YAML
7. **Dependencies**: `pyyaml` + stdlib only (no external packages)

### Effort Estimate (Revised)

| Phase | Tasks | Lines | Days |
|-------|-------|-------|------|
| `_date_to_interval()` + helpers | 1 | 60 | 0.5 |
| Pass 1: Deictic regex (P5) | 1 | 30 | 0.5 |
| Pass 2: Future-as-past (P1) | 1 | 80 | 0.5 |
| Pass 3: Anachronism (P2) | 1 | 120 | 1 |
| Pass 4: Comparator (P3) | 1 | 90 | 0.5 |
| Pass 5: Causal inversion (P4) | 1 | 150 | 1 |
| `audit()` orchestrator | 1 | 20 | 0.5 |
| Timeline bootstrap script | 1 | 140 | 0.5 |
| Tests (adapt ARS fixtures) | 15 | 440 | 1 |
| CLI subcommand | 1 | 30 | 0.5 |
| **Total** | **~20** | **~1,160** | **~7 days** |

---

## 🟡 Medium — Additional ARS Components (Not Yet Ported)

### 10. Contamination Signals (`contamination_signals.py`, 221 lines)

**Purpose**: Compute contamination signals for literature entries per v3.7.3 spec.

**Two signals**:
1. **Preprint signal** (`compute_preprint_signal`): True iff `year >= 2024 AND venue resolves to a preprint server`. Uses a 10-venue closed list (arXiv, bioRxiv, medRxiv, SSRN, etc.) + source_pointer inference.
2. **SS unmatched** (`compute_ss_unmatched_signal`): True if Semantic Scholar returns no match. None if `obtained_via='manual'` or API degradation.

**Also provides**:
- `resolve_openalex_unmatched()` — DOI-first then title-search fallback
- `resolve_crossref_unmatched()` — Same pattern as OpenAlex
- `build_signals_object()` — Constructs the full `contamination_signals` dict
- `reset_client_outage_latch()` — Best-effort latch reset helper

**Relevance to paper-writer**: The preprint detection logic (10-venue list + source_pointer inference) could enhance our citation verification to flag preprint contamination. The `build_signals_object()` pattern is a clean interface we could adopt.

**Lines affected**: New module `clients/contamination_signals.py`

---

### 11. Uncited Assertion Detector (`uncited_assertion_detector.py`, 254 lines)

**Purpose**: Detect sentences that make empirical claims without citations (D4-c rule).

**Three conditions** (ALL must hold):
1. Quantifier or empirical verb present (numbers, percentages, "most", "several", "showed", "demonstrated", etc.)
2. No `<!--ref:slug-->` marker on the sentence
3. Not a definitional sentence ("refers to", "is defined as", "we define", "for the purposes of")

**Guard pass**: Rejects bare numbers that are years, version triples, or section numbers (e.g., "Table 2", "v3.7.3", "2024").

**Key constants** (from `_claim_audit_constants.py`):
```python
UNCITED_EMPIRICAL_VERBS = {"showed", "demonstrated", "observed", "proved", "confirmed"}
UNCITED_FUZZY_QUANTIFIERS = {"most", "several", "two-thirds"}
UNCITED_DEFINITION_PHRASES = ("refers to", "is defined as", "we define", "for the purposes of")
```

**Relevance to paper-writer**: This is a valuable writing quality check — detect claims without evidence. Could be a new validator: `validators/uncited_assertion.py`.

**Lines affected**: New module `validators/uncited_assertion.py` + constants

---

### 12. Three-Layer Citation Lint (`check_v3_7_3_three_layer_citation.py`, 318 lines)

**Purpose**: Static lint for `<!--ref:slug-->` + `<!--anchor:kind:value-->` marker pairs.

**Checks**:
1. Every `<!--ref:slug-->` is followed by `<!--anchor:kind:value-->` where kind ∈ {quote, page, section, paragraph, none}
2. Quote anchors: URL-decoded value ≤ 25 words
3. No orphan anchor markers without preceding ref
4. No raw `--` in quote values (must be `%2D` encoded)
5. No premature HTML comment termination in quote anchors
6. Malformed ref markers (3+ status tokens)
7. Fenced code blocks excluded from lint

**Relevance to paper-writer**: If we adopt the `<!--ref:slug-->` + `<!--anchor:kind:value-->` convention, this lint ensures structural integrity. Currently paper-writer doesn't use this convention — it would be a new feature.

**Lines affected**: New module `linters/three_layer_citation.py`

---

### 13. Claim Audit Pipeline (`claim_audit_pipeline.py`, 1373 lines)

**Purpose**: Full claim-faithfulness audit pipeline — the most complex module in ARS.

**Architecture**:
- Dependency-injected `retrieve_fn` / `judge_fn` (not hardcoded to any LLM)
- Cache layer with stable JSON hashing
- 6-step pipeline: claim extraction → retrieval → judge invocation → verdict routing → constraint checking → result aggregation
- Handles: SUPPORTED, UNSUPPORTED, AMBIGUOUS, VIOLATED, NOT_VIOLATED, audit_tool_failure
- Negative constraint checking (NC-C###, MNC-### patterns)
- Sampling strategy (stratified_buckets_v1)

**Relevance to paper-writer**: This is the "deep" claim verification that goes beyond our current `ClaimAlignmentValidator`. Our validator checks if claims have references; this pipeline checks if the references actually support the claims. It's a much deeper analysis but requires LLM judge integration.

**Lines affected**: Large new module — likely not a direct port, but patterns could inform a simpler version.

---

### 14. OpenAlex Client (`openalex_client.py`, 166 lines)

**Purpose**: Third bibliographic index API client (alongside Crossref and Semantic Scholar).

**Features**:
- DOI lookup with title cross-check
- Title search with year tiebreaker (+0.05)
- Polite email via `OPENALEX_POLITE_EMAIL` env var
- Rate limiting: 10 req/s (polite), 1 req/s (anonymous)
- Same error handling patterns as Crossref/S2

**Relevance to paper-writer**: Adding OpenAlex would give us 3-way triangulation (Crossref + S2 + OpenAlex) instead of 2-way. This would significantly improve citation verification confidence.

**Lines affected**: New module `clients/openalex.py` (~166 lines)

---

### 15. API Protocol Documentation (`deep-research/references/`)

**22 reference docs** covering:
- `crossref_api_protocol.md` — Full Crossref API contract
- `semantic_scholar_api_protocol.md` — Full S2 API contract
- `openalex_api_protocol.md` — Full OpenAlex API contract
- `ethics_checklist.md` — Research ethics guidelines
- `systematic_review_protocol.md` — SLR methodology
- `argumentation_reasoning_framework.md` — Logical reasoning patterns
- `methodology_patterns.md` — Research methodology templates
- `source_quality_hierarchy.md` — Source quality tiers
- `equator_reporting_guidelines.md` — Medical research reporting

**Relevance to paper-writer**: These docs define the exact API contracts we ported. They're the authoritative reference for behavior, not the code. If we ever need to verify our implementation matches ARS, these are the source of truth.

---

### 16. Adapters (`scripts/adapters/`)

**Components**:
- `zotero.py` — Zotero library integration
- `obsidian.py` — Obsidian vault integration
- `folder_scan.py` — Generic folder scanning
- `_common.py` — Shared adapter utilities

**Relevance to paper-writer**: These are input adapters for ingesting citations from different sources. Not directly relevant to our current scope (we parse markdown manuscripts), but could be useful for future expansion.

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
| 10 | Contamination signals | ~100 lines | Medium | Low | New module |
| 11 | Uncited assertion detector | ~150 lines | Medium | Low | New validator |
| 12 | Three-layer citation lint | ~200 lines | Medium | Medium | New linter (requires ref convention) |
| 13 | OpenAlex client | ~166 lines | Medium | Low | New client (3-way triangulation) |
| 14 | Temporal audit system | ~1,160 lines | High | Medium | Feature scope (~7 days) |
| 15 | Claim audit pipeline | ~1,373 lines | High | High | Major feature (requires LLM judge) |
| 16 | Adapters (Zotero/Obsidian) | ~300 lines | Low | Low | Future expansion |

---

## Quick Wins (< 5 min each)

1. **Polite email env var** — 1 line change in `crossref.py:71`
2. **429 refresh anchor** — 1 line each in `_retry.py` or both clients
3. **Year tiebreaker** — Add `year` param to `search_by_title()` in both clients

---

*Last updated: 2026-06-03*
