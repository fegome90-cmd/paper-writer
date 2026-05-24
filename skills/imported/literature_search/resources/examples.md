---
version: 1.1.1
updated: 2026-05-22
purpose: Worked examples with scoring formulas and output templates
---

# Examples — Literature Search Skill

## Example 1: Communication App for HNC Patients

**Scenario:** Building a TTS communication app for post-laryngectomy patients in Chile.

### Search Plan

```markdown
## Search Plan
- Question: Does a TTS mobile app improve communication and QoL in HNC patients post-laryngectomy?
- Period: 2020-2025 (5 years)
- Languages: English, Spanish
- Population: Adult HNC patients (post-surgery or post-RT) with speech impairment
- Intervention: Mobile app / TTS / AAC / ASR technology
- Outcomes: Communication ability, QoL, depression, social participation
- Phase: Intervention design (weights: A=15% B=35% C=25% D=15% E=10%)
```

### Search Queries Used

```
1. "head neck cancer speech voice outcomes patient-reported quality of life 2020 2021 2022"
2. "total laryngectomy communication quality of life voice rehabilitation 2023 2024 2025"
3. "TTS app communication disability RCT 2023 2024 2025"
4. "Richard Cave" speech recognition motor neurone disease publications
5. "AAC app spanish medical 2020"
```

### Results Summary

- 30+ papers found
- 20 extracted in detail
- 6 PDFs downloaded (open access)
- Top 5 score range: 7.0-8.2

### Final Ranking (Top 5)

| Rank | Paper | Score | Tier |
|:----:|-------|:-----:|:----:|
| 1 | Bakia 2025 — RCT TTS app | 8.15 | 🏆 |
| 2 | Jimenez-Labaig 2024 — Meta mental health HNC | 7.80 | 🏆 |
| 3 | "Less I type" — CHI 2023 (Cave) | 7.10 | 🥈 |
| 4 | V-RQoL Scoping Review 2025 | 7.00 | 🥈 |
| 5 | SECEL Spanish 2022 | 6.40 | 🥉 |

> **Note:** Scores are illustrative and depend on the search phase weights. Calculated with default (balanced) weights: A=25%, B=25%, C=20%, D=20%, E=10%. D sub-scores use direct passthrough formula (v1.1.0+).

## Example 2: Quick Single-Topic Search

**Scenario:** "Busca papers sobre disfagia post-radioterapia en HNC"

### Simplified Flow

1. **1 search:** `web_search "pubmed dysphagia post radiotherapy head neck cancer prevalence 2020 2025"`
2. **Fetch top 3:** `web_fetch` each PMC article
3. **Quick rank:** Apply criteria, pick top 3
4. **Export:** Save to `apps/pae-wizard/outputs/research/` with basic template

### Output Format (simplified)

```markdown
## Dysphagia Post-RT in HNC — Quick Review

| # | Paper | Journal | n | Key Finding | Score |
|---|-------|---------|---|-------------|:-----:|
| 1 | ... | *Oral Oncol* | 200 | 80% prevalence | 8.2 |
| 2 | ... | *Head & Neck* | 150 | Worsens at 2yr | 7.5 |
| 3 | ... | *Eur Arch Oto* | 85 | Rehab helps | 6.8 |
```

## Example 3: Author Profile

**Scenario:** "Busca publicaciones de Richard Cave"

### Flow

1. `web_search "Richard Cave" + area keyword`
2. `web_fetch` Google Scholar profile
3. `web_fetch` institutional page (GDI Hub, UCL)
4. Extract all publications with citation counts
5. Rank by relevance to current project

### Output Format

```markdown
## Dr. Richard Cave — Publication Profile

**Affiliation:** GDI Hub / CDLI at UCL
**h-index:** X | **Total citations:** Y
**Focus:** ASR for non-standard speech (ALS, MND, HNC)

| # | Paper | Journal | Year | Citations | Relevance |
|---|-------|---------|:----:|:---------:|:---------:|
| 1 | ... | *CHI* | 2023 | 144 | ★★★★★ |
```
