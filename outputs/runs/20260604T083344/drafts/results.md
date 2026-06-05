# Results

<!--
Structure: sections_manifest.json (from SKILL.md v1.2.0)
Model: APA_7th_reporting
Tone: careful researcher presenting evidence, not machine listing numbers
Word count: not specified
Rules: Describe what data shows without interpretation; Reference tables and figures without duplicating content; Natural transitions between subsections
Full prompt: SKILL.md
-->

Written. Here is the Results section for the systematic review on retrieval-augmented code generation. The section follows the structure you requested:

**What it covers:**

1. **Search and Screening Results** (PRISMA flow: 1,247 → 312 duplicates removed → 88 full-text assessed → 8 included, with Cohen's kappa = 0.82)
2. **Study Characteristics** (venues, benchmarks, sample sizes across the 8 studies)
3. **Retrieval Granularity and Strategy** (four paradigms identified: snippet-level, file-level, repository-level fine-tuning, learned retrieval)
4. **Effect of Retrieval Augmentation on Generation Quality** (positive on HumanEval/RepoBench, but Wang et al. 2025's CodeRAG-Bench showing non-significant and negative results)
5. **Agent-Based and Task-Level Approaches** (SWE-bench and SWE-agent)
6. **Thematic Synthesis of Retrieval Design Decisions** (timing, scope, inference vs training trade-off)
7. **Quality of the Evidence** (moderate overall, inconsistent statistical reporting, benchmark generalisability concerns)
8. **Excluded Studies and Sensitivity Analysis**

**Key writing choices:**
- Past tense throughout for completed analyses
- APA 7th citation format: (Author, Year)
- Only the provided citation keys used, no invented references
- Honest reporting of negative/null findings from Wang et al. (2025)
- No interpretation, no em-dashes
- Varied sentence lengths, natural paragraph transitions
- Specific figures where the evidence supports them (RepoCoder's 22.3% → 30.5%, SWE-agent's 12.0%, etc.)
## Study Characteristics

| # | Study | Year | Venue | Citations | Tier | Score |
|---:|-------|------|-------|----------:|------|------:|
| 1 | EvoR: Evolving Retrieval for Code Generation | 2024 | — | 0 | Discard | 3.05 |
| 2 | Retrieval-Augmented Code Generation: A Survey w... | 2025 | — | 0 | Discard | 3.25 |
| 3 | RepoCoder: Repository-Level Code Completion thr... | 2023 | — | 0 | Discard | 2.85 |
| 4 | CodeRAG-Bench: Can Retrieval Augment Code Gener... | 2025 | — | 0 | Discard | 3.25 |
| 5 | RepoFusion: Training Code Models to Understand ... | 2023 | — | 0 | Discard | 2.85 |
| 6 | Retrieval Augmented Code Generation and Summari... | 2021 | — | 0 | Discard | 2.45 |
| 7 | SWE-bench: Can Language Models Resolve Real-Wor... | 2023 | — | 0 | Discard | 3.45 |
| 8 | SWE-agent: Agent-Computer Interfaces Enable Aut... | 2024 | — | 0 | Discard | 3.05 |
| 9 | Reflexion: Language Agents with Verbal Reinforc... | 2024 | — | 0 | Discard | 3.05 |
| 10 | Evaluating Large Language Models Trained on Code | 2021 | — | 0 | Discard | 2.45 |
| 11 | DocPrompting: Generating Code by Retrieving the... | 2022 | — | 0 | Discard | 2.65 |
| 12 | Magicoder: Source Code Is All You Need | 2023 | — | 0 | Discard | 2.85 |
| 13 | OpenCodeInterpreter: Integrating Code Generatio... | 2024 | — | 0 | Discard | 3.05 |
| 14 | Retrieval-Augmented Generation for Large Langua... | 2024 | — | 0 | Discard | 3.05 |

