# Critical Appraisal Resource

> **Source:** K-Dense `scientific-critical-thinking` + Aperivue `medsci-skills` (adaptado)
> **Version:** 1.0.0 | **Created:** 2026-05-22
> **Purpose:** Framework de evaluación crítica para papers incluidos en literature-search

---

## 1. Study Design Assessment

| Design Type | Causal Claims | Internal Validity | Use For |
|-------------|:-------------:|:------------------:|---------|
| RCT | ✅ Strong | High | Treatment efficacy |
| Quasi-experimental | ⚠️ Limited | Moderate | Interventions without randomization |
| Cohort (prospective) | ⚠️ Limited | Moderate-Strong | Prognosis, risk factors |
| Cohort (retrospective) | ⚠️ Weak | Moderate | Association studies |
| Case-control | ❌ Weak | Low-Moderate | Rare outcomes, etiology |
| Cross-sectional | ❌ None | Low | Prevalence, association |
| Case series/reports | ❌ None | Very Low | Novel presentations |
| Systematic review | ✅ Strong | High (if well done) | Evidence synthesis |
| Meta-analysis | ✅ Strong | High (if well done) | Effect size estimation |

## 2. Bias Taxonomy (K-Dense)

### Researcher Biases
- **Confirmation bias:** Only supporting findings highlighted?
- **HARKing:** Hypotheses stated a priori or formed after seeing results?
- **Publication bias:** Negative results missing from literature?
- **Cherry-picking:** Evidence selectively reported?

### Selection Biases
- **Sampling bias:** Sample representative of target population?
- **Volunteer bias:** Participants self-select systematically?
- **Attrition bias:** Differential dropout between groups?
- **Survivorship bias:** Only "survivors" visible in sample?

### Measurement Biases
- **Observer bias:** Expectations influence observations?
- **Recall bias:** Retrospective reports systematically inaccurate?
- **Social desirability:** Responses biased toward acceptability?
- **Instrument bias:** Measurement tools systematically err?

### Analysis Biases
- **P-hacking:** Multiple analyses until significance emerged?
- **Outcome switching:** Non-significant outcomes replaced?
- **Selective reporting:** All planned analyses reported?
- **Subgroup fishing:** Subgroup analyses without correction?

### Detection Checklist
- [ ] Preregistration exists (ClinicalTrials.gov, PROSPERO, OSF)
- [ ] Analysis plan stated a priori
- [ ] All outcomes reported (compare to registration)
- [ ] Participant flow diagram (CONSORT for RCTs)
- [ ] Baseline characteristics table (check group balance)
- [ ] Sensitivity analyses reported

## 3. Statistical Review Checklist

### Sample Size & Power
- [ ] A priori power analysis conducted
- [ ] Sample adequate for detecting meaningful effects
- [ ] Significant results from small samples → flag for inflated effect sizes

### Statistical Tests
- [ ] Tests appropriate for data type and distribution
- [ ] Test assumptions checked and met
- [ ] Parametric tests justified (or non-parametric used)
- [ ] Analysis matched to study design

### Multiple Comparisons
- [ ] Correction applied (Bonferroni, FDR, Tukey)
- [ ] Primary vs secondary outcomes clearly distinguished
- [ ] Pre-specified vs post-hoc analyses labeled

### Effect Sizes
- [ ] Reported with confidence intervals
- [ ] Clinically meaningful (not just statistically significant)
- [ ] Absolute and relative measures both reported

## 4. Risk of Bias Assessment

### RoB 2 (Cochrane) — For RCTs

| Domain | Questions | Signal |
|--------|-----------|--------|
| **Randomization** | Sequence generated? Allocation concealed? Baseline balanced? | Low/Some concerns/High |
| **Deviations** | Participants blinded? Personnel blinded? Deviations from protocol? | Low/Some concerns/High |
| **Missing data** | Outcome data available? Likely to bias results? Appropriate analysis? | Low/Some concerns/High |
| **Measurement** | Outcome assessors blinded? Measurement appropriate? | Low/Some concerns/High |
| **Selected reporting** | Pre-registered? All planned outcomes reported? | Low/Some concerns/High |

**Overall:** Low (all domains Low) / Some concerns / High (any domain High)

### ROBINS-I (Cochrane) — For Non-randomized Studies

| Domain | Questions |
|--------|-----------|
| **Confounding** | Is confounding adequately controlled? |
| **Selection** | Is selection into the study adequately addressed? |
| **Classification** | Are interventions classified correctly? |
| **Deviation** | Are deviations from intended interventions addressed? |
| **Missing data** | Is missing data adequately addressed? |
| **Measurement** | Are outcomes measured appropriately? |
| **Selected reporting** | Are results selectively reported? |

### NOS (Newcastle-Ottawa Scale) — For Cohort/Case-Control

**Maximum 9 stars:**

| Category | Cohort | Case-Control |
|----------|--------|--------------|
| Selection (max 4) | Representativeness, Selection, Ascertainment, Outcome not present at start | Case definition, Representativeness, Selection of controls, Definition of controls |
| Comparability (max 2) | Study controls for most important factor + additional factor | Same |
| Outcome/Exposure (max 3) | Assessment method, Follow-up length, Adequacy of follow-up | Assessment method, Same method for cases/controls, Non-response rate |

**Interpretation:** ≥7 = high quality, 4-6 = moderate, ≤3 = low quality

## 5. GRADE Assessment (For Evidence Synthesis)

### Certainty of Evidence

| Factor | Upgrade | Downgrade |
|--------|:-------:|:---------:|
| Study design | RCTs start HIGH, Observational start LOW | — |
| Risk of bias | — | -1 serious, -2 very serious |
| Inconsistency | — | -1 serious, -2 very serious |
| Indirectness | — | -1 serious, -2 very serious |
| Imprecision | — | -1 serious, -2 very serious |
| Publication bias | — | -1 likely, -2 very likely |
| Large effect | +1 large, +2 very large | — |
| Dose-response | +1 evidence of gradient | — |
| Confounding | +1 all plausible confounding reduces effect | — |

### Final GRADE Rating
- **High:** Very confident estimate is close to true value
- **Moderate:** Moderately confident; estimate may be substantially different
- **Low:** Limited confidence; estimate may be substantially different
- **Very Low:** Very little confidence; estimate is likely substantially different

## 6. Reporting Guidelines Checklist

| Guideline | Study Type | Key Items |
|-----------|------------|-----------|
| **CONSORT** | RCT | 25-item checklist + flow diagram |
| **STROBE** | Observational | 22-item checklist |
| **PRISMA** | Systematic review | 27-item checklist + flow diagram |
| **CARE** | Case report | 13-item checklist |
| **STARD** | Diagnostic accuracy | 30-item checklist |
| **COREQ** | Qualitative | 32-item checklist |
| **SRQR** | Qualitative | 21-item checklist |
| **MOOSE** | Meta-analysis observational | 21-item checklist |

## 7. Appraisal by Study Type (AIPOCH pattern)

### Therapy Questions
1. Was assignment randomized?
2. Was allocation concealed?
3. Were groups similar at baseline?
4. Were participants blinded?
5. Were outcome assessors blinded?
6. Was follow-up adequate?
7. Was intention-to-treat analysis used?

### Prognosis Questions
1. Was cohort representative?
2. Was exposure measured validly?
3. Were outcomes measured blind to exposure?
4. Was follow-up adequate (>80%)?
5. Were confounders controlled?
6. Were confidence intervals provided?

### Diagnostic Accuracy Questions
1. Was there an independent blind comparison?
2. Was the test evaluated in an appropriate spectrum?
3. Was the reference standard applied regardless of index test?
4. Were sensitivity/specificity reported with CIs?

### Harm/Etiology Questions
1. Were there clearly defined groups?
2. Were exposures and outcomes measured similarly?
3. Was follow-up adequate?
4. Were temporal relationships clear?
5. Was there a dose-response relationship?

---

## Usage in literature-search Workflow

This resource is used in **Phase 3 (Rank)** after initial scoring A-E:

```
Phase 3: Rank
├── A: Population match (0-4)
├── B: Clinical relevance (0-4)
├── C: Recency (0-4)
├── D: Evidence quality (0-5)  ← this resource feeds into D
│   ├── Study design (0-2)
│   ├── Sample size (0-2)
│   ├── Journal quality (0-2)  
│   ├── Citations (0-1)
│   └── COI penalty (-0.5)
├── E: Validation (0-4)
└── RoB assessment ← this resource provides the framework
    ├── RoB 2 (for RCTs)
    ├── ROBINS-I (for observational)
    ├── NOS (for cohort/case-control)
    └── GRADE (for synthesis)
```

---

**Sources:**
- K-Dense `scientific-critical-thinking` SKILL.md — bias taxonomy, statistical review, validity analysis
- Aperivue `medsci-skills` — 33 reporting guidelines, RoB frameworks
- AIPOCH `medical-research-literature-reader-pro` — appraisal by study type
- Cochrane Handbook — RoB 2, ROBINS-I
- GRADE Working Group — certainty of evidence
