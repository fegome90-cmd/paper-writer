# Ranking Criteria — Literature Search Skill

## Scoring Formula

```
Final Score = (A × wA) + (B × wB) + (C × wC) + (D × wD) + (E × wE)
Range: 0.0 — 10.0
```

Weights are set per study phase (see §Weight Adjustments below).

## Criterion A: Population Relevance (default 25%)

How directly does the study population match the target population?

| Score | Definition |
|:-----:|-----------|
| 10 | Exact match: same disease, same stage, same treatment |
| 8-9 | Same disease, different stage or treatment |
| 6-7 | Related disease, similar functional impact |
| 4-5 | Similar functional impact, different disease |
| 2-3 | General population or tangentially related |
| 0-1 | Unrelated population |

**Examples:**
- HNC app study → studying HNC patients = 10
- HNC app study → studying ALS patients = 4-5
- HNC app study → studying stroke patients = 3-4

## Criterion B: Intervention Relevance (default 25%)

How directly does the study intervention match what we're evaluating?

| Score | Definition |
|:-----:|-----------|
| 10 | Exact same intervention (same technology, same delivery) |
| 8-9 | Very similar (same type of technology, different brand/app) |
| 6-7 | Related intervention (technology-assisted communication) |
| 4-5 | Adjacent (rehabilitation, prosthetics) |
| 2-3 | Describes the problem but no intervention |
| 0-1 | No intervention relevance |

## Criterion C: Outcome Relevance (default 20%)

How well do the study's outcome measures align with ours?

| Score | Definition |
|:-----:|-----------|
| 10 | Uses the exact same validated instruments |
| 8-9 | Uses similar validated instruments (same construct) |
| 6-7 | Measures same constructs with different instruments |
| 4-5 | Measures some relevant outcomes |
| 2-3 | Tangentially related outcomes |
| 0-1 | Unrelated outcomes |

**Key outcome instruments for communication studies:**

| Instrument | Construct | Abbreviation |
|------------|-----------|:------------:|
| Voice-Related Quality of Life | Voice-specific QoL | V-RQoL |
| Voice Handicap Index | Voice handicap | VHI / VHI-10 |
| Self-Evaluation Communication Experiences after Laryngectomy | Communication post-TL | SECEL |
| Speech Handicap Index | Speech handicap | SHI |
| EORTC QLQ-H&N35 | HNC-specific QoL | H&N35 |
| M.D. Anderson Dysphagia Inventory | Swallowing | MDADI |
| Patient Health Questionnaire | Depression | PHQ-9 |
| Generalized Anxiety Disorder | Anxiety | GAD-7 |

## Criterion D: Methodological Quality (default 20%)

Composite of evidence level, sample size, journal quality, citation impact, and COI penalty.

### Formula

```
D = Evidence + Sample + Journal + Citations + COI_penalty
    ─────────   ───────   ────────   ─────────   ────────────
    máximo 5    máximo 2  máximo 2   máximo 1    0 o -0.5
```

When weight == max for every component, the normalization cancels out completely:
`value/max × weight` = `value` when `weight == max`.

| Sub-score | Weight | Range | Calculation |
|-----------|:------:|:-----:|-------------|
| Evidence | 5 | 0-5 | `value` (passthrough) |
| Sample | 2 | 0-2 | `value` (passthrough) |
| Journal | 2 | 0-2 | `value` (passthrough) |
| Citations | 1 | 0-1 | `value` (passthrough) |
| COI penalty | — | 0 / -0.5 | direct subtraction |
| **Maximum** | **10** | | |

**Simplified formula:** `D = evidence + sample + journal + citations + coi_penalty`

### Evidence Level (0-5)

| Level | Type | Score |
|:-----:|------|:-----:|
| 1a | Systematic review of RCTs / Meta-analysis | 5 |
| 1b | Individual RCT | 4.5 |
| 2a | Systematic review of cohort studies | 4 |
| 2b | Individual cohort / prospective | 3 |
| 3 | Case-control | 2 |
| 4 | Case series / cross-sectional | 1.5 |
| 5 | Expert opinion | 0.5 |

### Sample Size (0-2)

| n | Score |
|:-:|:-----:|
| > 1,000 | 2 |
| 500-999 | 1.5 |
| 100-499 | 1 |
| 50-99 | 0.5 |
| < 50 | 0.25 |

### Journal Quality (0-2)

| Tier | Score |
|------|:-----:|
| Q1 (SJR top 25%) | 2 |
| Q2 | 1.5 |
| Q3 | 1 |
| Q4 | 0.5 |
| Unknown | 0.5 |

Verify at: https://www.scimagojr.com/journalsearch.php?q=JOURNAL_NAME

### Citation Impact (0-1)

| Citations | Score |
|:---------:|:-----:|
| > 100 | 1 |
| 50-99 | 0.75 |
| 20-49 | 0.5 |
| 10-19 | 0.25 |
| < 10 | 0.1 |

### COI Penalty (0 or negative)

| COI Type | Penalty |
|----------|:-------:|
| No COI / Academic funded | 0 |
| Industry-funded RCT studying their own product | -0.5 |
| Author employed by company whose product is studied | -0.5 |
| COI not reported / unclear | -0.25 |

**Detection:** Scan abstract/metadata for keywords: "supported by", "funded by", "conflict of interest", "industry". If explicit "No conflict of interest" → 0.

### D Calculation Examples

| Paper | Ev | n | J | Cit | COI | **D** |
|-------|:--:|:-:|:-:|:---:|:---:|:-----:|
| Meta n=654k, Q1, 50+ citas | 5.0 | 2 | 2 | 0.75 | 0 | **9.75** |
| Meta n=50, Q1, 0 citas | 5.0 | 0.25 | 2 | 0.1 | 0 | **7.35** |
| RCT n=62, Q1, 5 citas | 4.5 | 0.5 | 2 | 0.1 | 0 | **7.10** |
| RCT n=62, Q1, 5 citas, industria | 4.5 | 0.5 | 2 | 0.1 | -0.5 | **6.60** |
| Cohorte n=200, Q2, 20 citas | 3.0 | 1 | 1.5 | 0.5 | 0 | **6.00** |
| Transversal n=30, Q3, 0 citas | 1.5 | 0.25 | 1 | 0.1 | 0 | **2.85** |

## Criterion E: Context Applicability (default 10%)

Parameter: `E_CONTEXT` (defined per project, configurable)

| Score | Definition |
|:-----:|-----------|
| 10 | Study done in E_CONTEXT with same language/culture |
| 8-9 | Instruments validated in local language |
| 6-7 | Applicable with cultural adaptation |
| 4-5 | Applicable with significant adaptation |
| 2-3 | Limited applicability |
| 0-1 | Not applicable |

**E_CONTEXT defaults by project:**

| Project | Default E_CONTEXT |
|---------|-------------------|
| `examen_grado` | "Chile/Latin America, Spanish" |
| `tqt_app` | "Chile/FALP, oncología, Spanish" |
| (other) | "Global (no specific context)" |

Override via search plan parameter in Phase 1.

## Tier Classification

| Range | Tier | Action |
|:-----:|:----:|--------|
| 8.0-10 | 🏆 **Tier 1** | **Primary citation** — direct evidence for the study |
| 6.5-7.9 | 🥈 **Tier 2** | **Supporting citation** — complement, backup |
| 5.0-6.4 | 🥉 **Tier 3** | **Background** — context, theory, framework |
| < 5.0 | ⬜ **Discard** | Not cited in formal output |

## Weight Adjustments by Study Phase

| Phase | A (Pop) | B (Interv) | C (Outcome) | D (Quality) | E (Local) |
|-------|:-------:|:----------:|:-----------:|:-----------:|:---------:|
| **Problem definition** | 30% | 5% | 15% | 35% | 15% |
| **Intervention design** | 15% | 35% | 25% | 15% | 10% |
| **Outcome selection** | 20% | 10% | 40% | 20% | 10% |
| **Default (balanced)** | 25% | 25% | 20% | 20% | 10% |

Specify which phase when starting the search. If unspecified, use "Default".

---

**Version:** 1.2.0 | **Updated:** 2026-05-22 | **Fix:** Normalized D formula, parametric E, COI penalty
