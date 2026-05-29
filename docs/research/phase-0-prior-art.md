# Phase 0 — Prior Art Report: Local Scientific Linting

> Comparative analysis of 13 open-source / published projects to inform the design of
> `paper audit claims`, `paper audit prose`, and `paper gate method`.
>
> Date: 2026-05-29
> Scope: Local-only, no APIs, no LLM, no web search in runtime, no MCP.

---

<a name="current-phase-0-recommendation"></a>
## Current Phase 0 Recommendation — reconciled with implementation

> **Last reconciled:** 2026-05-29  
> **Reconciliation reason:** Corrected selection criteria applied post-implementation. The previous version mixed "useful today" tools with "interesting future" papers. This section supersedes the original "Projects by Influence" table (see §1) and select individual project recommendations marked throughout.

### Selection Criteria

For Phase 0, every referenced project must pass **all five** questions:

| # | Question | Meaning |
|---|----------|---------|
| 1 | **¿Corre local?** | No SaaS, no cloud dependency, no API key required |
| 2 | **¿Es determinístico o casi determinístico?** | Same input → same output, every time |
| 3 | **¿Da hallazgos ubicables?** | Each finding has file/line/column/span |
| 4 | **¿Tiene reglas auditables?** | Rules are readable YAML/regex, not black-box models |
| 5 | **¿No requiere LLM, API ni búsqueda externa?** | Zero runtime network calls |

Projects that fail any of these are **not** Phase 0 base material. They may still be conceptual references or future roadmap items.

### Classification by Use in Phase 0

| Proyecto | Categoría | Uso en Phase 0 | Comando relacionado | Qué tomar | Qué NO tomar | Estado |
|---|---|---|---|---|---|---|
| **LanguageCheck** | Arquitectura | Modelo de auditoría por niveles (word/sentence/paragraph/paper) | `audit prose` | Checks por nivel de granularidad; advertencia explícita de falsos positivos | Stack no reusable como librería; reglas no curadas para contexto biomédico | **adoptado** |
| **Academic-Writing-Check** | Reglas directas | Checks chicos, explícitos, baratos y diff-friendly | `audit prose` | passive, weasel, dups, abbr, typography como checks independientes | Lista de reglas como autoridad absoluta (depende de disciplina/revista) | **adoptado** |
| **Vale** | Arquitectura | Diseño del motor de reglas: YAML rules, severidad, scoping, check types | `audit prose` / `gate method` | Reglas externalizadas, severidad configurable, markup-aware, CI-friendly | Engine completo; reglas genéricas de documentación técnica no científicas | **adoptado** |
| **write-good** | Schema | Schema mínimo de findings con ubicación | todos | `{reason, index, offset}` — ampliado a `{rule_id, severity, line, column, span, message, recommendation}` | Reglas naïve no científicas | **adoptado** |
| **proselint** | Arquitectura | Check Registry pattern con namespacing | `audit prose` | Registro modular, namespacing (`scientific.hedging`), JSON output, configuración granular | Reglas literarias/generalistas; mixed JS/Python codebase | **adoptado** |
| **TeXtidote** | Arquitectura | Offset mapping / source map | todos | Source map: limpiar markup → analizar → reubicar en original | Dependencia Java; LanguageTool bundling (100MB+) | **adoptado** |
| **EQUATOR** | Contenido | Checklists YAML para method gate | `gate method` | Checklist-as-YAML, critical items, section-to-item mapping | Evaluación LLM; formatos propietarios | **adoptado** |
| **Chrisper** | Pipeline | Pipeline LaTeX minimalista | `audit prose` | Flujo austero: LaTeX → detex → texto → reglas → salida | Dominio orientado a Computer Science; dependencia de `detex` | **inspiración** |
| **detecting-scientific-claim** | Concepto | Claim detection conceptual y taxonomía de secciones | `audit claims` | Section-aware claim risk; sentence-level approach; trigger lexicon | AllenNLP, modelos BERT entrenados, Flask web demo | **inspiración** |
| **markdownlint** | Pre-check | Higiene estructural de manuscritos Markdown | `audit format` (opcional) | Frontmatter handling, custom rules engine, CI integration | No audita contenido científico; solo estructura Markdown | **futuro** |
| **statcheck** | Patrón | Extract-recompute-compare para estadísticas | `audit stats` (futuro) | Patrón de verificación estadística; APA regex battle-tested; rounding tolerance model | APA-only scope; no debe ser gate universal en Fase 0 | **futuro** |
| **SciFact** | Taxonomía | SUPPORT/REFUTE/NOINFO schema para post-MVP | `audit claims` (post-MVP) | Taxonomía de verificación; pipeline retrieval → rationale → label | BERT/RoBERTa fine-tuning; evidence retrieval externo | **futuro** |
| **RIGOURATE** | Concepto | Proporcionalidad evidencial como filosofía | `audit claims` (post-MVP) | Overstatement score como concepto; evidential proportionality | VLMs fine-tuned (Qwen3-VL, InternVL3.5, 8B params) | **futuro** |
| **SciScore** | Producto cerrado | Taxonomía de rigor (blinding, randomization, power, sex, RRIDs) | `gate method` (inspiración taxonómica) | Rigor criteria checklist items; "Not Detected" vs "Not Applicable" | NLP propietario; SaaS (no corre local); código 100% cerrado | **descartado** |
| **Penelope.ai** | Producto cerrado | Check taxonomy editorial y section mapping | `gate method` (inspiración taxonómica) | "Every check linked to evidence in text"; sección → ítem mapping | SaaS cerrado; 30+ check system no replicable sin LLM | **descartado** |
| **sciwrite-lint** | Prototipo alpha | Visión de verificación científica local | `evidence-map` (roadmap lejano) | SHA-256 caching de manuscript + rules; claim verification vision | GPU requirement (vLLM); GROBID; 3★ alpha | **descartado** |
| **Ripeta** | Producto cerrado | Dimensiones como weighted gates | `gate method` (concepto) | Dimensiones como weighted gates, no score global | Código cerrado; spaCy models por indicador; overengineered | **descartado** |

### Implementation Alignment

The current Phase 0 implementation maps directly to the reconciled recommendation:

| Component | File(s) | Status |
|---|---|---|
| **Parser + Source Map** | `parsers/manuscript.py`, `parsers/source_map.py` | ✅ Implemented |
| **Prose Validator** | `validators/prose.py` | ✅ Implemented (Check Registry, YAML rules, section-aware) |
| **Method Gate** | `validators/method_gate.py` | ✅ Implemented (YAML checklists per study type, fail-closed) |
| **Claims Validator** | `validators/claims.py` | ✅ Implemented (trigger lexicon, section-aware risk, evidence_required) |
| **Deduplication SSOT** | `engine/deduplicator.py` | ✅ Implemented (sweep-line algorithm, single source of truth) |
| **Rule Engine** | `engine/loader.py`, `engine/formatter.py` | ✅ Implemented |
| **Rules (YAML)** | `rules/claims/*.yml`, `rules/prose/*.yml`, `rules/method_gate/*.yml` | ✅ 12+ rule files |
| **Schemas** | `schemas/finding.schema.json`, `schemas/claim_audit.schema.json`, `schemas/prose_audit.schema.json`, `schemas/method_gate.schema.json` | ✅ 4 schemas |

**Dead code removed:** `engine/registry.py` and `engine/matcher.py` were eliminated during Phase 0 cleanup — dedup is centralized in `engine/deduplicator.py` as the SSOT.

**Current test status:** 522 tests passing (full project suite, 0 failures).

### Phase 0 Boundary

Phase 0 explicitly does **NOT** do:

- ❌ No LLM (local or remote)
- ❌ No APIs (no runtime network calls)
- ❌ No external search (no PubMed, Semantic Scholar, OpenAlex, CrossRef)
- ❌ No MCP (Model Context Protocol is out of scope)
- ❌ No truth verification (Phase 0 detects risk, does not verify truth)
- ❌ No global score (no "paper scored 8.5/10" — only per-finding severity + gate pass/fail)
- ❌ No evidence retrieval (no abstract fetching, no full-text lookup)
- ❌ No automatic support/refute (no claim-against-evidence classification)
- ❌ No Phase 1 features (no LLM-assisted claim decomposition, no discourse-level analysis)

**Governing principle:** Phase 0 detects risk; it does not verify truth.

### Superseded or Weakened Recommendations

The following original document positions are weakened or superseded by the reconciled classification above:

| Original Position | Location | Superseded By | Action |
|---|---|---|---|
| SciFact listed as "Primary influence" in Projects by Influence table | §1, line 56 | Now classified as **futuro** — Phase 0 does not do evidence retrieval | Marked in §2.11 below |
| RIGOURATE listed as "Conceptual only" without distinguishing philosophical value vs implementation incompatibility | §1, line 56 | Now classified as **futuro** — concept is valuable, implementation is antithetical to Phase 0 | Marked in §2.10 below |
| sciwrite-lint classified only as "Not usable" / "Discard" without noting its vision value for later phases | §1, line 57, §2.12 | Now classified as **descartado** for Phase 0, but acknowledged as roadmap vision | Marked in §2.12 below |
| SciScore and Penelope listed as "Secondary influence" suggesting they are base material | §1, line 56 | Both are **descartado** (closed SaaS, not auditable, not local) | Marked in §2.7 and §2.8 below |
| statcheck suggested for Phase 0 `audit claims` and `gate method` | §2.5, line 249 | Deferred to post-MVP `paper audit stats`; not a Phase 0 gate | Marked in §2.5 below |
| Score/global lint treated as risk but partially tolerated in original analysis | Throughout | Explicitly banned: ADR-005 strengthened, Phase 0 Boundary added | Confirmed in §4.1 and §10 |
| Projects by Influence table used Primary/Secondary/Conceptual/Not Usable categories | §1, line 54 | Replaced by 5-state classification: adoptado / inspiración / futuro / descartado (with criterion-driven selection) | Original table kept for historical reference, deprecated by new section |

---

## Table of Contents

0. [Current Phase 0 Recommendation](#current-phase-0-recommendation)
    - [Implementation Alignment](#implementation-alignment)
    - [Phase 0 Boundary](#phase-0-boundary)
    - [Superseded or Weakened Recommendations](#superseded-or-weakened-recommendations)
1. [Executive Summary](#1-executive-summary)
2. [Project Profiles](#2-project-profiles)
3. [Cross-Cutting Synthesis](#3-cross-cutting-synthesis)
4. [Architecture Decisions](#4-architecture-decisions)
5. [Design: `paper audit claims`](#5-design-paper-audit-claims)
6. [Design: `paper audit prose`](#6-design-paper-audit-prose)
7. [Design: `paper gate method`](#7-design-paper-gate-method)
8. [Common Infrastructure](#8-common-infrastructure)
9. [Prioritization & Roadmap](#9-prioritization--roadmap)
10. [Anti-Patterns & Risk Register](#10-anti-patterns--risk-register)

---

## 1. Executive Summary

### Core Finding

**There is no single open-source tool that does what Phase 0 needs.** Each project solves a related but distinct subproblem. The value is in their **patterns, taxonomies, and architectures**, not in their code.

### What Phase 0 Is Not

Phase 0 is NOT:
- A claim verification system (that requires evidence retrieval)
- A style checker (Vale already does that)
- A journal compliance tool (that requires journal-specific rules)
- A reproducibility score (too easy to get wrong)

### What Phase 0 Is

A **local scientific linting system** with three commands:

| Command | What It Detects | What It Does NOT Do |
|---|---|---|
| `audit claims` | Claim candidates, types, risk levels | Verify claims against evidence |
| `audit prose` | Overclaim, hedging, weasel words, nominalization | Judge writing quality |
| `gate method` | Missing methodological items per study type | Evaluate scientific validity |

**Governing principle: Phase 0 detects risk; it does not verify truth.**

> **⚠ Superseded by Current Phase 0 Recommendation** — see top of document for reconciled classification (5-state: adoptado / inspiración / futuro / descartado). The table below mixes auditable repos with closed SaaS products and assigns "Primary influence" to projects incompatible with Phase 0 (no LLM, no APIs, local-only constraint).

### Projects by Influence

| Primary influence | Secondary influence | Conceptual only | Not usable |
|---|---|---|---|
| Vale, proselint, write-good, TeXtidote | SciScore, Penelope.ai | SciFact, RIGOURATE | sciwrite-lint, Ripeta |
| statcheck, EQUATOR | detecting-scientific-claim | ReClaim, CLLM | ExecutableClaims |

---

## 2. Project Profiles

### 2.1 Vale

| Attribute | Value |
|---|---|
| **URL** | https://github.com/vale-cli/vale |
| **Stars** | ~5,400 — very active (v3.14.2, May 2026) |
| **License** | MIT |
| **Language** | Go (single binary) |
| **Runs locally** | Yes — CLI via binary, Homebrew, Docker |
| **Requires API/LLM** | No — 100% rule-based |

**Architecture:**
- Check types as extension points: `existence`, `substitution`, `occurrence`, `repetition`, `consistency`, `conditional`, `capitalization`, `metric`, `spelling`, `sequence`
- YAML-based rules — no-code rule definition
- Markup-aware via tree-sitter (understands Markdown, AsciiDoc, reStructuredText, LaTeX)
- Scoping: rules can target headings, sentences, code blocks
- Config inheritance: `.vale.ini` with format-specific sections
- Output: CLI text, JSON, custom templates
- Package system: `vale sync` installs shared styles

**Reusable patterns for paper-writer:**
- Check types as extension points — directly applicable to all three validators
- YAML rule files — non-programmers can write rules
- Scoping — critical for scientific text (abstract vs methods vs discussion)
- Output JSON format — CI-friendly
- Configuration inheritance — project-level + user-level overrides

**What NOT to copy:**
- The entire engine (reimplementing Vale would take months)
- Multi-format markup support (start with Markdown + LaTeX only)
- Tengo scripting engine (overkill)
- Package hub dependency

**Fase 0 command:** `audit prose` (primary), `gate method` (config pattern)

**Overengineering risk:** Medium (if copied whole) / Low (if adapted selectively)

**Recommendation:** **Adapt** — use Vale's architecture as the model for paper-writer's rule engine, but implement as native Python for scientific-specific checks. Do NOT shell out to Vale as a dependency.

---

### 2.2 proselint

| Attribute | Value |
|---|---|
| **URL** | https://github.com/amperser/proselint |
| **Stars** | ~4,515 — active (80+ contributors) |
| **License** | BSD 3-Clause |
| **Language** | Python |
| **Runs locally** | Yes — `pip install proselint`, CLI or library |
| **Requires API/LLM** | No — dual regex engine (RE2 + Python `re`) |

**Architecture:**
- Check Registry pattern: modular checks registered via `__register__`, grouped by source (garner, wallace, butterick, etc.)
- Dual engine: `Fast` (RE2) for simple checks, `Fancy` (Python `re`) for lookahead/backreferences
- Config hierarchy: `proselint.json` with file-tree walk
- Output: text (`file:line:col: check: message`) or JSON with `check_path`, message, span, pos, replacements
- Each check has: `path` (namespaced), `message`, `severity`, `replacements`

**Reusable patterns:**
- Check Registry pattern with namespacing — e.g. `scientific.hedging`, `scientific.weasel`
- Modular checks per source — paper-writer could group by linguistic phenomenon
- JSON output format — directly reusable
- Config granularity — enable/disable at module or check level
- Pre-commit hook support

**What NOT to copy:**
- JavaScript/Python mixed codebase (33% JS, 30% Python, 32% HTML)
- Not markup-aware — doesn't understand LaTeX or markdown syntax
- 248 open issues — maintenance debt
- Some rules are too literary/periodistic for scientific writing

**Fase 0 command:** `audit prose` (direct fit)

**Overengineering risk:** Low

**Recommendation:** **Adapt** — implement the Check Registry pattern in Python for scientific-specific checks. Use proselint's namespacing and modularity as the model.

---

### 2.3 write-good

| Attribute | Value |
|---|---|
| **URL** | https://github.com/btford/write-good |
| **Stars** | ~5,072 — low maintenance (last commit Mar 2025) |
| **License** | MIT |
| **Language** | JavaScript (npm, ~49K weekly downloads) |
| **Runs locally** | Yes — `npx write-good`, also a library |
| **Requires API/LLM** | No — pure regex. Each check is a function. |

**Architecture:**
- Check functions are independent npm packages: `passive-voice`, `weasel-words`, `too-wordy`, `no-cliches`, `e-prime`, `adverb-where`
- Plugin system — anyone can create extension modules
- Output: `[{ index, offset, reason }]` — minimal but sufficient
- Whitelist mechanism for technical terms
- CLI with flags: `--weasel --no-passive`

**Built-in checks:**
passive, weasel, so, thereIs, adverbs, cliches, eprime, tooWordy, wordy, illusions, repeats, startsWithSo

**Reusable patterns:**
- Simplest possible output format: `{ index, offset, reason }`
- Plugin system for third-party rulesets
- Whitelist for domain-specific vocabulary
- CLI flag system for enabling/disabling check groups

**What NOT to copy:**
- JS ecosystem (paper-writer is Python)
- "Naive" by design — not markup-aware, gives false positives on code
- Not maintained actively

**Fase 0 command:** `audit prose` (check categories directly applicable)

**Overengineering risk:** Lowest of all projects

**Recommendation:** **Copy pattern** — the check function signature and output format are the gold standard for simplicity.

---

### 2.4 TeXtidote

| Attribute | Value |
|---|---|
| **URL** | https://github.com/sylvainhalle/textidote |
| **Stars** | ~1,000 — active (v0.9, Mar 2026) |
| **License** | Proprietary-ish (free to use) |
| **Language** | Java |
| **Runs locally** | Yes — CLI via `java -jar textidote.jar`, Homebrew |
| **Requires API/LLM** | No — rule-based + LanguageTool (local Java lib) |

**Architecture:**
1. LaTeX cleaner: parses `.tex`, strips commands/environments, produces clean text + offset map (`AnnotatedString`)
2. Built-in rules: Java `Rule` interface for structural checks (figure references, section order, stacked headings)
3. LanguageTool bridge: passes clean text to LT, remaps error positions via offset map
4. Output: HTML, console, single-line (machine-parseable)
5. Config: `.textidote` file in project root

**Reusable patterns:**
- **Offset mapping**: strip markup → analyze → remap to original positions. Critical for any markup-aware linter.
- **Rule interface**: abstract `Rule` with `getEverything()` → `LintMessage` list. Clean separation.
- **Structural rules**: "every figure must be referenced", "section ordering" — directly applicable to `gate method`
- **Multi-format output**: HTML for review, plain for CI

**What NOT to copy:**
- Java dependency (paper-writer is Python)
- LanguageTool bundling (100MB+ of XML rules)
- Hardcoded rules as Java classes (paper-writer should use data-driven YAML)

**Fase 0 command:** `audit prose` (offset mapping) + `gate method` (structural rules)

**Overengineering risk:** Medium

**Recommendation:** **Adapt** — take the offset mapping pattern and Rule interface, implement as Python. Skip LanguageTool integration.

---

> **⚠ Superseded by Current Phase 0 Recommendation** — statcheck is classified as **futuro** (`paper audit stats`). It is NOT a Phase 0 gate nor a base dependency. The "Fase 0 command" note below is weakened; only the "minimal rule: if manuscript reports effect without CI/p-value/estimator → warning/blocker" survives in Phase 0.

### 2.5 statcheck

| Attribute | Value |
|---|---|
| **URL** | https://github.com/MicheleNuijten/statcheck |
| **Stars** | ~186 — active (v1.5.0, CRAN, Python port exists) |
| **License** | GPL-3 |
| **Language** | R (Python port: `pip install statcheck`) |
| **Runs locally** | Yes — both R and Python versions |
| **Requires API/LLM** | No — pure regex + statistical computation (pt, pf, pchisq, pnorm) |

**Architecture:**
1. Text extraction (PDF via Xpdf, or HTML direct)
2. Regex extraction of NHST results matching APA format (t, F, χ², Z, r, Q)
3. P-value recomputation from test statistic + df
4. Classification: error vs decision error (significant ↔ not)
5. Rounding tolerance model (reported values are rounded → possible range)

**Reusable patterns:**
- "Extract → recompute → compare" pattern
- APA regex patterns for statistical results — battle-tested
- Rounding tolerance model — subtle and already solved
- Decision error classification (not just "numbers don't match" but "conclusion would change")

**What NOT to copy:**
- APA-only scope (paper-writer should support configurable style guides)
- Xpdf dependency for PDF (use Python-native `pypdf` or `pdftotext` wrapper)
- R dependency (use the Python port)

**Fase 0 command:** `audit claims` (statistical claim validation) + `gate method` (statistical reporting gate)

**Overengineering risk:** Low (core logic is ~300 lines)

**Recommendation:** **Copy pattern** — but defer to post-MVP (`paper audit stats`). For Phase 0, only use a minimal rule: "if the manuscript reports an effect without CI/p-value/estimator → warning/blocker."

---

### 2.6 EQUATOR Network & Reporting Guidelines

| Attribute | Value |
|---|---|
| **URL** | https://www.equator-network.org |
| **Guidelines** | 700+ reporting guidelines (CONSORT, STROBE, PRISMA, SPIRIT, COREQ, SRQR, etc.) |
| **Runs locally** | Yes — guidelines are PDF/DOCX documents |
| **Machine-readable** | No official JSON/YAML. Third-party conversions exist (PRISMA-AI-Share, PRISMA.jl) |

**Architecture of guidelines (all follow this):**

```
Section/Topic → Item # → Checklist Item Description → "Reported on page #"
```

Each guideline has:
- Checklist (table form)
- Expanded checklist (bullet points per item)
- Explanation & Elaboration document (rationale + examples)
- Optional flow diagram (PRISMA, CONSORT)

**Example structure (CONSORT 2025, 30 items across 6 sections):**
Title/Abstract, Open Science, Introduction, Methods, Results, Discussion

**Reusable patterns:**
- **Checklist as YAML** — transcoding guidelines into structured YAML is the foundation of `gate method`
- **Section-based item organization** — each item maps to an expected manuscript section
- **Critical items** — some items are "must-report" (trial registration, randomization method, sample size)
- **Three-state per item**: present, missing, not_applicable

**Open-source reference implementations:**
- **PRISMA-AI-Share** (`youkiti/PRISMA-AI-Share`): canonical YAML checklists + LLM evaluation pipeline
- **PRISMA.jl** (`cecoeco/PRISMA.jl`): DataFrame-based checklist (49x4) with keyword section mapping
- **CONSORT-NLP** (Wang et al., JAMA 2020): section → sentence → item mapping via SVM. Architecture pattern still valid.

**What NOT to copy:**
- LLM-dependent evaluation pipelines (post-MVP)
- Proprietary formats or vendor lock-in
- Journal-specific formatting checks (scope creep)

**Fase 0 command:** `gate method` (primary)

**Overengineering risk:** Low (checklists-as-YAML is simple)

**Recommendation:** **Copy pattern** — transcribe core guidelines (CONSORT, STROBE, PRISMA) into YAML. Build a simple rule engine that checks each item against manuscript sections via heading-parsing + keyword presence.

---

> **⚠ Superseded by Current Phase 0 Recommendation** — SciScore is **descartado** for Phase 0. Closed SaaS, not auditable, not local. Only its rigor criteria taxonomy survives as inspiration.

### 2.7 SciScore

| Attribute | Value |
|---|---|
| **URL** | https://sciscore.com — commercial, SaaS |
| **Code** | 100% closed |
| **Runs locally** | No |
| **Requires API/LLM** | Proprietary NLP algorithm (seed phrases + trained classifier + fuzzy matching for RRIDs) |

**Value for paper-writer:**
- **Rigor criteria taxonomy**: blinding, randomization, sex of subjects, power analysis, RRIDs
- **Three-table report structure**: Rigor Adherence, Key Resources, Statistical Tests
- **"Not Detected" vs "Not Applicable" distinction** — don't penalize if not applicable

**Recommendation:** **Adapt** — take the rigor criteria taxonomy as YAML checklist items. Ignore the proprietary NLP.

---

> **⚠ Superseded by Current Phase 0 Recommendation** — Penelope.ai is **descartado** for Phase 0. Closed SaaS, not auditable, not local. Only its section-to-item mapping pattern survives as architectural inspiration.

### 2.8 Penelope.ai

| Attribute | Value |
|---|---|
| **URL** | https://www.penelope.ai — commercial, SaaS |
| **Code** | 100% closed |
| **Runs locally** | No |
| **Requires API/LLM** | Probabilistic algorithms (not ML, not LLM) — pattern matching + rules |

**Value for paper-writer:**
- **Check taxonomy**: Ethics, COI, Data Availability, Funding, Author Contributions, Section Structure, Citation Matching, Reporting Checklists
- **Section mapping pattern**: heading-based IMRAD detection → per-section rule execution
- **"Every check linked to evidence in text"** — not a black box score

**Recommendation:** **Adapt** — take 8-10 essential checks. Implement as rules, not as a full 30+ check system.

---

### 2.9 detecting-scientific-claim

| Attribute | Value |
|---|---|
| **URL** | https://github.com/titipata/detecting-scientific-claim |
| **Stars** | ~250 — archival (last commit 2022) |
| **License** | Apache-2.0 |
| **Language** | Python (AllenNLP) |
| **Runs locally** | Yes — but requires AllenNLP + model download |
| **Requires API/LLM** | Yes — BERT-based sequence classifier |

**Value for paper-writer:**
- **Sentence-level claim detection**: each sentence classified as claim or non-claim
- **Discourse labels**: RESULTS, METHODS, CONCLUSIONS, BACKGROUND, OBJECTIVE
- **Claim triggers by section**: claims in Results vs Conclusions have different risk profiles
- **Dataset**: 1,500 abstracts, 11,702 sentences, 2,276 annotated as claims

**Reusable patterns:**
- Section-aware claim risk (a claim in Methods has different weight than one in Conclusions)
- Sentence segmentation as first step
- Trigger lexicon approach for claim candidate detection

**What NOT to copy:**
- AllenNLP dependency (outdated, v2 compatible but heavy)
- Trained models (overkill for Phase 0)
- Web service Flask app (not needed)

**Fase 0 command:** `audit claims`

**Overengineering risk:** Medium (if copying full stack) / Low (if adapting trigger lexicon approach)

**Recommendation:** **Adapt** — use the discourse section mapping (claim risk varies by section) and sentence-level approach. Implement with lightweight regex patterns, not models.

---

> **⚠ Superseded by Current Phase 0 Recommendation** — RIGOURATE is **futuro** (conceptual only). Its implementation (fine-tuned VLMs, multimodal retrieval) is antithetical to Phase 0. Only the concept of evidential proportionality survives.

### 2.10 RIGOURATE

| Attribute | Value |
|---|---|
| **URL** | arXiv: 2601.04350 |
| **Code** | Promised but not yet published |
| **Runs locally** | Not applicable |
| **Requires API/LLM** | Fine-tuned VLMs (Qwen3-VL, InternVL3.5, 8B parameters) |

**Value for paper-writer:**
- **Evidential proportionality**: a claim should not exceed what the evidence supports
- **Overstatement score**: continuous [0,1] scale

**Recommendation:** **Only inspiration** — the concept of evidential proportionality is the philosophical foundation for `audit claims`. But the implementation (fine-tuned VLMs, multimodal retrieval) is antithetical to Phase 0 constraints.

---

> **⚠ Superseded by Current Phase 0 Recommendation** — SciFact is **futuro** (post-MVP taxonomía). Requires BERT/RoBERTa fine-tuning and evidence retrieval — incompatible with Phase 0 constraints. ReClaim/CLLM remain future references.

### 2.11 SciFact & ReClaim/CLLM (Grouped)

**SciFact** (`allenai/scifact`, ~254★, archival):
- SUPPORT/REFUTE/NOINFO taxonomy — reusable for post-MVP
- Pipeline: abstract retrieval → rationale selection → label prediction
- Requires BERT/RoBERTa fine-tuning — not Phase 0 compatible

**ReClaim** (`stat-ml/reclaim`, small, active 2025):
- Atomic claim decomposition from prose
- LLM-prompted extraction (gpt-4o) — not Phase 0 compatible

**CLLM** (`OpenEvalProject/cllm`, small, active 2025):
- CLI workflow: extract → eval → compare
- Evidence type taxonomy: DATA, CITATION, KNOWLEDGE, INFERENCE, SPECULATION
- Requires Anthropic API — not Phase 0 compatible

**Recommendation (all three):** **Only inspiration** — save the taxonomies (SUPPORT/REFUTE/NOINFO, evidence types) for post-MVP when LLM becomes available. In Phase 0, these are architectural references, not code sources.

---

> **⚠ Superseded by Current Phase 0 Recommendation** — sciwrite-lint is **descartado** for Phase 0 (alpha, GPU-dependent). Its vision of local claim verification is a roadmap reference, not a Phase 0 dependency. Ripeta remains **descartado** (closed code).

### 2.12 sciwrite-lint & Ripeta (Grouped)

**sciwrite-lint** (`authentic-research-partners/sciwrite-lint`, ~3★, alpha):
- Full pipeline: text checks → LLM consistency → API verification → claim verification
- Requires GPU + vLLM + GROBID — antithetical to Phase 0
- **One good idea**: SHA-256 caching of manuscript + rules to know when an audit is stale

**Ripeta** (commercial, code closed):
- Score composite: ResearchCheck × (Professionalism + Reproducibility)
- spaCy models per indicator — overkill for Phase 0
- **One good idea**: dimensions as weighted gates, not a global score

**Recommendation (both):** **Discard** for Phase 0. Neither has usable code or a compatible architecture. Note the caching idea and gate-weighting concept for future reference.

---

## 3. Cross-Cutting Synthesis

### 3.1 Patterns That Recur Across Projects

| Pattern | Projects Using It | Applies To |
|---|---|---|
| Check Registry (modular checks) | proselint, write-good, Vale | All three commands |
| YAML/JSON rule files | Vale, EQUATOR derivatives | All three commands |
| Offset mapping (markup → clean text → remap) | TeXtidote | `audit prose` (critical) |
| Section-based item checking | Penelope.ai, CONSORT-NLP, EQUATOR | `gate method` |
| Sentence-level analysis | detecting-scientific-claim, SciFact | `audit claims` |
| Severity levels (error/warn/suggestion) | proselint, Vale, write-good | All three commands |
| Namespaced rule IDs | proselint (`typography.punctuation.hyperbole`) | All three commands |
| Configurable per project | Vale (`.vale.ini`), proselint (`proselint.json`) | All three commands |
| Whitelist for technical terms | Vale (vocab), write-good | `audit prose` |
| Three-state reporting (present/missing/NA) | SciScore, EQUATOR, Penelope.ai | `gate method` |

### 3.2 What Each Project Does Best

| Best At | Project | Why |
|---|---|---|
| Rule engine architecture | Vale | Check types, scoping, config inheritance |
| Check modularity | proselint | Namespaced registry, per-source grouping |
| Output simplicity | write-good | `{index, offset, reason}` — minimal, sufficient |
| Markup handling | TeXtidote | Offset mapping is the correct pattern |
| Statistical verification | statcheck | Extract → recompute → compare |
| Methodological checklists | EQUATOR | Gold standard, structured, citable |
| Claim candidate detection | detecting-scientific-claim | Section-aware, sentence-level |
| Taxonomy of rigor | SciScore | Blinding, randomization, power, sex, RRIDs |
| Editorial check taxonomy | Penelope.ai | Ethics, COI, data avail., funding |

### 3.3 The Gap Phase 0 Fills

No existing tool combines:
1. Scientific claim candidate detection (not verification)
2. Academic prose overclaim/hedging analysis
3. Methodological gate based on EQUATOR checklists
4. All local, deterministic, CI-integratable

Phase 0 is a **novel combination** of existing patterns, not a reimplementation of any single tool.

---

## 4. Architecture Decisions

### 4.1 Decision Record

| ID | Decision | Rationale | Source |
|---|---|---|---|
| ADR-001 | **YAML-based rule files** for all three commands | Non-programmers can contribute, CI-reviewable, versionable | Vale, proselint |
| ADR-002 | **Python-native rule engine** (no Vale subprocess dependency) | Avoid external CLI dependency for core functionality | Constraint |
| ADR-003 | **Check Registry pattern** with namespaced rule IDs | Modular, testable, extensible per project/journal | proselint |
| ADR-004 | **ManuscriptParser** as shared infrastructure | Strip markup once, analyze with offset mapping | TeXtidote |
| ADR-005 | **No global score** — only per-finding severity | Avoid false authority and gaming the score | RIGOURATE anti-pattern |
| ADR-006 | **Three findings per finding**: critical/warning/info mapped to P0/P1/P2 | Simple, actionable, CI-gateable | Vale, proselint |
| ADR-007 | **`audit claims` detects claim candidates only** — no verification | Phase 0 detects risk, does not verify truth | User constraint |
| ADR-008 | **`gate method` uses YAML checklists** transcribed from EQUATOR | Deterministic, citable, extensible per study type | EQUATOR |
| ADR-009 | **`audit prose` separate from Vale** — complement, not replace | Vale handles general style; Phase 0 handles scientific-specific | User decision |
| ADR-010 | **Prioritize prose first, then gate, then claims** | Prose is easiest and proves the engine; gate is most deterministic; claims is most valuable but most risky | User analysis |

### 4.2 Rule Engine Architecture

```
manuscript.md/.tex
       │
       ▼
ManuscriptParser
  ├── clean_text (strip markup)
  ├── sentences (sentence segmentation)
  ├── sections (heading-based IMRAD detection)
  └── source_map (original ↔ clean positions)
       │
       ▼
RuleEngine
  ├── load rules from rules/<command>/*.yml
  ├── filter by scope / enabled checks
  ├── for each rule:
  │     apply pattern to appropriate scope (sentence/section/document)
  │     if match → create Finding
  └── return Findings[]
       │
       ▼
OutputFormatter
  ├── JSON (for CI, programmatic consumption)
  └── Markdown/terminal (for human review)
```

### 4.3 Finding Schema (Common to All Three Commands)

```json
{
  "$schema": "https://json-schema.org/draft/07/schema#",
  "title": "Finding",
  "description": "A single finding from any Phase 0 command.",
  "type": "object",
  "properties": {
    "finding_id": {
      "type": "string",
      "description": "Unique identifier (F-001, F-002, ...)."
    },
    "command": {
      "type": "string",
      "enum": ["audit_claims", "audit_prose", "gate_method"]
    },
    "rule_id": {
      "type": "string",
      "description": "Namespaced rule identifier, e.g. 'claims.causal.definitive_verb'",
      "pattern": "^[a-z]+\\.[a-z]+\\.[a-z_]+$"
    },
    "severity": {
      "type": "string",
      "enum": ["P0", "P1", "P2"],
      "description": "P0=critical (blocks gate), P1=warning, P2=suggestion"
    },
    "file": {
      "type": "string",
      "description": "Source file path (relative to project root)."
    },
    "line": {
      "type": "integer",
      "description": "Line number in original file."
    },
    "column": {
      "type": "integer",
      "description": "Column offset in original file."
    },
    "span": {
      "type": "array",
      "items": { "type": "integer" },
      "minItems": 2,
      "maxItems": 2,
      "description": "Character offset span [start, end] in original file."
    },
    "message": {
      "type": "string",
      "description": "Human-readable description of the finding."
    },
    "recommendation": {
      "type": "string",
      "description": "Actionable suggestion for the author."
    },
    "evidence_required": {
      "type": "array",
      "items": { "type": "string" },
      "description": "What evidence would be needed to verify/resolve this finding (post-MVP)."
    }
  },
  "required": ["finding_id", "command", "rule_id", "severity", "message"]
}
```

---

## 5. Design: `paper audit claims`

### 5.1 Purpose

Detect **claim candidates** in a scientific manuscript and classify them by type and risk level. This is NOT claim verification — it's claim-adjacent linting.

### 5.2 What It Detects

| Category | Description | Example Trigger |
|---|---|---|
| **Causal claims** | Statements asserting cause-effect | "led to", "caused", "resulted in", "increased" |
| **Comparative claims** | Statements comparing groups/treatments | "higher than", "superior to", "compared with" |
| **Descriptive claims** | Statements describing findings | "we observed", "we found", "the rate was" |
| **Prescriptive claims** | Statements recommending action | "should", "must", "recommend", "require" |

### 5.3 What It Does NOT Detect (Phase 0)

- Semantic claim boundaries (atomic claim decomposition)
- Support/refute status against evidence
- Claim novelty or significance
- Implicit claims not matching trigger patterns

### 5.4 Rule Files

```
rules/claims/
├── causal.yml           # Causal claim triggers
├── comparative.yml      # Comparative claim triggers  
├── descriptive.yml      # Descriptive claim triggers
├── prescriptive.yml     # Prescriptive claim triggers
└── risk_by_section.yml  # Risk modifier per section
```

**Example rule file** (`rules/claims/causal.yml`):

```yaml
# rules/claims/causal.yml
# Causal/definitive claim language triggers.

rule_group: claims.causal
description: "Detect causal claim language in scientific prose."
severity_default: P1

rules:
  - id: claims.causal.definitive_verb
    patterns:
      - "\\bproves?\\b"
      - "\\bdemonstrates?\\b"
      - "\\bestablishes?\\b"
      - "\\bconfirms?\\b"
    message: "Definitive causal verb detected."
    severity: P0
    recommendation: "Replace with proportionate language (e.g., 'suggests', 'indicates') unless study design supports causal inference."
    scope: sentence
    evidence_required: ["study_design", "effect_size", "confidence_interval"]

  - id: claims.causal.effect_verb
    patterns:
      - "\\b(reduced?|increased?|improved?|decreased?)\\b"
    message: "Effect verb detected — possible causal claim."
    severity: P1
    recommendation: "Verify that the study design supports causal attribution."
    scope: sentence
    evidence_required: ["comparator", "effect_size", "design_compatible"]

  - id: claims.causal.result_prep
    patterns:
      - "\\bled? to\\b"
      - "\\bresulted? in\\b"
      - "\\bassociated with\\b"
    message: "Causal/associative language detected."
    severity: P1
    recommendation: "Specify whether the design supports causal or only associative interpretation."
    scope: sentence
    evidence_required: ["study_design"]
```

### 5.5 Section-Aware Risk Modifier

Claims in different sections carry different risk:

| Section | Default Risk Modifier | Rationale |
|---|---|---|
| Abstract | +1 level | Claims here are most visible, often overcondensed |
| Introduction | 0 | Contextual claims, generally lower risk |
| Methods | -1 level | Procedural descriptions, rarely claims |
| Results | +1 level | Results sections contain the strongest evidentiary claims |
| Discussion | +1 level | Interpretation claims, highest overclaim risk |
| Conclusions | +2 levels | Summary claims, often overstated |

### 5.6 Validator Interface

```python
# validators/claims.py — initial design

class ClaimsValidator:
    """Detect claim candidates in manuscript text.

    Phase 0: trigger-lexicon based, section-aware.
    Post-MVP: atomic decomposition + evidence mapping.
    """

    def validate(self, manuscript: Manuscript) -> list[Finding]:
        """Run all claim rules against the parsed manuscript.
        
        Steps:
        1. Sentence segmentation
        2. Section detection
        3. Per-category rule application (causal, comparative, etc.)
        4. Section-aware risk adjustment
        5. Evidence required mapping
        6. Deduplication of overlapping matches
        """
```

---

## 6. Design: `paper audit prose`

### 6.1 Purpose

Analyze scientific prose for overclaiming, hedging, weasel words, and nominalization — the specific linguistic patterns that make academic writing unclear or overstated.

### 6.2 What It Detects

| Category | Description | Example Trigger |
|---|---|---|
| **Overclaim** | Language that exceeds what evidence supports | "proves", "unequivocally shows", "definitively establishes" |
| **Weasel words** | Vague terms that hedge without accountability | "clearly", "obviously", "it is well known", "many" |
| **Hedging conflict** | Mixed hedging within same claim | "might prove" (hedge + definitive) |
| **Causal language** | Verbs implying causation | "causes", "leads to", "results in" (shared with claims) |
| **Vague quantifiers** | Imprecise quantity expressions | "several", "a number of", "various" |
| **Nominalization** | Verbs turned into nouns, obscuring agency | "implementation was performed" → "we implemented" |
| **Unsupported certainty** | Certainty markers without evidence | "undoubtedly", "without question", "certainly" |

### 6.3 What It Does NOT Detect

- Writing quality or readability (Vale handles this)
- Grammatical errors (LanguageTool territory)
- Journal-specific style (not a journal compliance tool)
- Plagiarism

### 6.4 Rule Files

```
rules/prose/
├── overclaim.yml           # Definitive/overstated language
├── hedging.yml             # Hedging language patterns
├── weasel.yml              # Weasel words and vague terms
├── causal_language.yml     # Causal verb detection
├── vague_quantifiers.yml   # Imprecise quantity expressions
├── nominalization.yml      # Noun-heavy constructions
└── unsupported_certainty.yml  # Certainty without evidence
```

**Example rule file** (`rules/prose/overclaim.yml`):

```yaml
# rules/prose/overclaim.yml
# Overclaiming language — statements that exceed available evidence.

rule_group: prose.overclaim
description: "Detect language that overstates what the evidence supports."
severity_default: P1

rules:
  - id: prose.overclaim.definitive_causal
    patterns:
      - "\\bproves?\\b"
      - "\\b(unequivocally|conclusively|definitively)\\s+(shows?|demonstrates?|establishes?)\\b"
    message: "Definitive causal claim — verify against evidence."
    severity: P0
    recommendation: "Use proportional language unless the study design supports definitive causal inference."
    scope: sentence

  - id: prose.overclaim.absolute
    patterns:
      - "\\ball\\b.*\\b(patients|subjects|participants)\\b"
      - "\\bnever\\b"
      - "\\balways\\b"
    message: "Absolute language detected — consider if exceptions exist."
    severity: P1
    recommendation: "Qualify with appropriate limits (e.g., 'most', 'the majority of')."
    scope: sentence
```

### 6.5 Validator Interface

```python
# validators/prose.py — initial design

class ProseValidator:
    """Analyze scientific prose for overclaim, hedging, weasel words.

    Phase 0: check-registry based, pattern-matching, section-aware.
    Post-MVP: discourse-level analysis, hedging consistency scoring.
    """

    def validate(self, manuscript: Manuscript) -> list[Finding]:
        """Run all prose rules against the parsed manuscript.
        
        1. Load rules from rules/prose/*.yml
        2. For each rule, check scope-appropriate segments
        3. Deduplicate overlapping matches (longest match wins)
        4. Apply whitelist (technical terms that should be excluded)
        """
```

---

## 7. Design: `paper gate method`

### 7.1 Purpose

Apply a **fail-closed methodological gate** that checks whether a manuscript includes required reporting items for its study type. This is the most deterministic of the three commands.

### 7.2 What It Checks

| Category | Example Items | Source |
|---|---|---|
| **Basic structure** | Title, Abstract, Introduction, Methods, Results, Discussion, Conclusions | Generic |
| **Ethics & compliance** | Ethics approval, COI, funding, data availability, author contributions | Penelope.ai, Ripeta |
| **Study-specific (CONSORT)** | Randomization, allocation concealment, blinding, sample size, trial registration | EQUATOR/CONSORT |
| **Study-specific (STROBE)** | Eligibility criteria, matching, follow-up, missing data handling | EQUATOR/STROBE |
| **Study-specific (PRISMA)** | Search strategy, selection criteria, risk of bias, synthesis methods | EQUATOR/PRISMA |

### 7.3 Checklist Format (YAML)

```yaml
# rules/method_gate/consort.yml
# CONSORT 2025 checklist for randomized controlled trials.

guideline: CONSORT
version: "2025"
study_types: ["rct", "randomized_controlled_trial"]
source: "https://www.equator-network.org/reporting-guidelines/consort/"

critical_items:
  - id: "1a"
    section: "Title and abstract"
    topic: "Title"
    description: "Identification as a randomised trial in the title"
    expected_location: "Title"
    check_type: keyword_presence
    keywords: ["randomised", "randomized", "RCT", "trial"]
    severity_if_missing: P0
    message: "Title does not identify this as a randomized trial."

  - id: "2"
    section: "Introduction"
    topic: "Trial registration"
    description: "Trial registration number and registry name"
    expected_location: "Abstract"
    check_type: keyword_presence
    keywords: ["NCT", "trial registration", "registered at", "registry"]
    severity_if_missing: P0
    message: "Trial registration number not found."

  - id: "16a"
    section: "Methods"
    topic: "Sample size"
    description: "How sample size was determined"
    expected_location: "Methods"
    check_type: keyword_presence
    keywords: ["power", "sample size", "calculation", "a priori"]
    severity_if_missing: P1
    message: "Sample size determination not described."
```

### 7.4  Core Check Types

| Check Type | What It Does | Implementation |
|---|---|---|
| `keyword_presence` | Check if section contains required keywords | Regex pattern matching on section text |
| `section_presence` | Check if required section heading exists | Heading detection in parsed sections |
| `section_content` | Check if section has minimum content (not empty/placeholder) | Character count or placeholder detection |
| `subsection_presence` | Check if a sub-heading exists within a section | Sub-heading detection |
| `pattern_match` | Check if text matches a required pattern | Regex on combined section text |

### 7.5 Validator Interface

```python
# validators/method_gate.py — initial design

class MethodGateValidator:
    """Apply methodological gate based on EQUATOR-derived checklists.

    Phase 0: deterministic, heading-based IMRAD parsing, keyword checks.
    Post-MVP: LLM-assisted item verification for ambiguous items.
    """

    def validate(
        self,
        manuscript: Manuscript,
        study_type: str,
        checklist_name: str | None = None,
    ) -> GateResult:
        """Run checklist items against the parsed manuscript.
        
        1. Load checklist YAML for the study type
        2. For each item, determine manuscript section by headings
        3. Apply check_type (keyword_presence, section_presence, etc.)
        4. Collect blockers (P0 items missing) and warnings (P1/P2 items missing)
        5. Return GateResult: pass/fail + blockers + warnings
        """
```

### 7.6 Gate Result Schema

```json
{
  "$schema": "https://json-schema.org/draft/07/schema#",
  "title": "GateResult",
  "description": "Result from paper gate method.",
  "type": "object",
  "properties": {
    "study_type": { "type": "string" },
    "guideline": { "type": "string" },
    "gate_passed": { "type": "boolean" },
    "blockers": {
      "type": "array",
      "items": { "$ref": "#/definitions/ChecklistItemResult" },
      "description": "P0 items that are missing — gate fails."
    },
    "warnings": {
      "type": "array",
      "items": { "$ref": "#/definitions/ChecklistItemResult" },
      "description": "P1/P2 items that are missing — warnings only."
    },
    "not_applicable": {
      "type": "array",
      "items": { "$ref": "#/definitions/ChecklistItemResult" },
      "description": "Items explicitly marked N/A (recorded for audit)."
    },
    "summary": {
      "type": "object",
      "properties": {
        "total_items": { "type": "integer" },
        "passed": { "type": "integer" },
        "blockers": { "type": "integer" },
        "warnings": { "type": "integer" },
        "not_applicable": { "type": "integer" }
      },
      "required": ["total_items", "passed", "blockers", "warnings", "not_applicable"]
    }
  },
  "required": ["study_type", "gate_passed", "blockers", "warnings", "summary"]
}
```

---

## 8. Common Infrastructure

### 8.1 ManuscriptParser

Shared parser that all three validators depend on:

```
parsers/
├── manuscript.py     # Manuscript dataclass, parsing pipeline
└── source_map.py     # Position mapping (original ↔ clean text)
```

**`Manuscript` dataclass:**
- `sections: dict[str, Section]` — heading-name → content
- `sentences: list[Sentence]` — all sentences with positions
- `source_map: SourceMap` — original positions ↔ clean text positions
- `metadata: dict` — detected study type, journal, etc.

**Parsing pipeline:**
1. Read file (markdown or LaTeX)
2. Strip markup (preserving offset map)
3. Detect section headings (IMRAD pattern)
4. Segment sentences
5. Build source map

### 8.2 Rule Engine

```
engine/
├── loader.py          # Load YAML rules from rules/<command>/*.yml
├── registry.py        # Check Registry — register, enable/disable
├── matcher.py         # Pattern matching (regex) with scope awareness
├── deduplicator.py    # Overlapping match resolution
└── formatter.py       # Output formatting (JSON, terminal)
```

### 8.3 No Global Score

There is deliberately NO score/lint/grade from any Phase 0 command. Only:
- **Findings** (individual issues with severity)
- **Gate pass/fail** (binary for `gate method`)

This prevents:
- False authority ("my paper scored 8.5/10")
- Gaming the system (optimizing for score instead of quality)
- Scope creep into evaluation territory

---

## 9. Prioritization & Roadmap

### 9.1 Build Order

```
Phase 0-a: Infrastructure (foundation)
├── parsers/manuscript.py      — Markdown + LaTeX parsing
├── parsers/source_map.py      — Position mapping
├── engine/loader.py           — YAML rule loading
├── engine/registry.py         — Check Registry
├── engine/matcher.py          — Pattern matching
├── engine/deduplicator.py     — Overlap resolution
├── engine/formatter.py        — JSON + terminal output
└── schemas/finding.schema.json  — Common schema

Phase 0-b: paper audit prose (proves the engine)
├── validators/prose.py
├── rules/prose/overclaim.yml
├── rules/prose/hedging.yml
├── rules/prose/weasel.yml
├── rules/prose/causal_language.yml
├── rules/prose/vague_quantifiers.yml
├── rules/prose/nominalization.yml
├── rules/prose/unsupported_certainty.yml
└── schemas/prose_audit.schema.json

Phase 0-c: paper gate method (most deterministic)
├── validators/method_gate.py
├── rules/method_gate/consort.yml
├── rules/method_gate/strobe.yml
├── rules/method_gate/prisma.yml
├── rules/method_gate/generic.yml
└── schemas/method_gate.schema.json

Phase 0-d: paper audit claims (most valuable, highest risk)
├── validators/claims.py
├── rules/claims/causal.yml
├── rules/claims/comparative.yml
├── rules/claims/descriptive.yml
├── rules/claims/prescriptive.yml
├── rules/claims/risk_by_section.yml
└── schemas/claim_audit.schema.json
```

### 9.2 Rationale for Build Order

1. **Infrastructure first** — ManuscriptParser and RuleEngine are shared by all three commands. Building them first validates the architecture.

2. **`audit prose` second** — Most straightforward scientifically. Proves the rule engine works. Immediate value for authors.

3. **`gate method` third** — Most deterministic. The YAML checklist approach is well-understood. Fail-closed gate is the most CI-valuable feature.

4. **`audit claims` last** — Most novel and most risky. Benefits from having the engine and prose experience first. Also the command where scope creep is most dangerous.

### 9.3 Post-MVP (Not Phase 0)

- `paper audit stats` — statcheck integration
- `paper audit claims` — semantic decomposition with LLM
- `paper gate method` — LLM-assisted ambiguous item resolution
- `paper evidence-map` — SciFact-inspired evidence mapping
- Additional EQUATOR checklist transcriptions
- `paper gate journal` — journal-specific compliance (Penelope.ai pattern)

---

## 10. Anti-Patterns & Risk Register

### 10.1 Anti-Patterns to Avoid

| Anti-Pattern | Why | Projects That Do It |
|---|---|---|
| Score/lint/grade | False authority, gaming, scope creep | sciwrite-lint, SciScore, Ripeta |
| LLM dependency for core path | Non-deterministic, API-dependent, fail-open | ReClaim, CLLM, RIGOURATE |
| Trained ML models | Maintenance burden, dataset bias, opaque | SciFact, detecting-scientific-claim |
| Full pipeline from PDF to verdict | Overengineered, fragile | sciwrite-lint, ExecutableClaims |
| Journal-specific formatting | Scope creep, journal-rule maintenance | Penelope.ai |
| Semantic claim verification | Requires evidence retrieval (not local) | SciFact, RIGOURATE |
| Claim boundary detection without clear triggers | Fuzzy, non-deterministic | ReClaim, CLLM |
| Package hub dependency | Network dependency for core function | Vale (optional) |
| Multi-format parsing (10+ formats) | Maintenance burden, diminishing returns | Vale, TeXtidote |

### 10.2 Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Scope creep into verification** | Medium | High | Strict "candidate only" rule for claims |
| **False positives from simple patterns** | High | Medium | Whitelist mechanism, severity tiering, section-awareness |
| **Overengineering the rule engine** | Medium | Medium | Keep MVP engine <500 lines, add features only when needed |
| **Checklist maintenance burden** | Medium | Low | YAML files are reviewable; community contributions possible |
| **Section detection failing for non-IMRAD papers** | Medium | Medium | Fallback to flat text; support custom headings per journal preset |
| **Markdown vs LaTeX parsing differences** | Medium | Low | Common parser handles both; edge cases are surface-level |
| **User expects semantic claim verification** | High | High | Clear documentation: "Phase 0 detects risk, not truth" |

---

## Appendix A: Quick Reference — Project Recommendations

> **ℹ Historical terminology.** This table uses the original nomenclature (Adapt / Copy / Only inspiration / Discard). The current authority for all project classifications is the [Classification by Use in Phase 0](#classification-by-use-in-phase-0) table with states: **adoptado / inspiración / futuro / descartado**.

| Project | Recommendation | Use Case |
|---|---|---|
| Vale | Adapt (architecture) | Rule engine, check types, scoping |
| proselint | Adapt (pattern) | Check Registry, namespacing, modularity |
| write-good | Copy (pattern) | Output format, plugin system, whitelist |
| TeXtidote | Adapt (pattern) | Offset mapping, Rule interface |
| statcheck | Copy (deferred) | Statistical verification (post-MVP) |
| EQUATOR | Copy (content) | Checklist-as-YAML, gate methodology |
| SciScore | Adapt (taxonomy) | Rigor criteria items |
| Penelope.ai | Adapt (taxonomy) | Editorial check items |
| detecting-scientific-claim | Adapt (pattern) | Section-aware claim risk |
| RIGOURATE | Only inspiration | Evidential proportionality concept |
| SciFact | Only inspiration | Claim/evidence/status schema (post-MVP) |
| ReClaim/CLLM | Only inspiration | Atomic claim decomposition (post-MVP) |
| sciwrite-lint | Discard | Too alpha, GPU-dependent |
| Ripeta | Discard | Closed code, overengineered |

---

## Appendix B: File Tree — Phase 0 Delivery (Original Design)

> **⚠ Historical — superseded by [Implementation Alignment](#implementation-alignment).**  
> The original design included `engine/registry.py` and `engine/matcher.py`, which were eliminated during Phase 0 cleanup. The SSOT for the current file tree is the Implementation Alignment table at the top of this document.

```
paper-writer/                          # Original design tree — NOT current
├── parsers/
│   ├── __init__.py
│   ├── manuscript.py
│   └── source_map.py
├── engine/
│   ├── __init__.py
│   ├── loader.py
│   ├── registry.py           ← REMOVED (dead code, Phase 0 cleanup)
│   ├── matcher.py            ← REMOVED (dedup centralized in deduplicator.py)
│   ├── deduplicator.py
│   └── formatter.py
├── validators/
│   ├── __init__.py
│   ├── claims.py
│   ├── prose.py
│   └── method_gate.py
├── rules/
│   ├── claims/
│   ├── prose/
│   └── method_gate/
├── schemas/
└── docs/
    └── research/
        └── phase-0-prior-art.md
```
