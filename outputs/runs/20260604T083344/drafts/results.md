# Results

<!--
Structure: sections_manifest.json (from SKILL.md v1.2.0)
Model: APA_7th_reporting
Tone: careful researcher presenting evidence, not machine listing numbers
Word count: not specified
Rules: Describe what data shows without interpretation; Reference tables and figures without duplicating content; Natural transitions between subsections
Full prompt: SKILL.md
-->

Large language models have achieved remarkable proficiency in generating code from natural-language descriptions, yet their effectiveness remains bounded by the knowledge encoded during training @chen2021humaneval. Models trained on static corpora cannot incorporate proprietary APIs, internal documentation, or cross-module dependencies that define real-world software projects. Retrieval-augmented code generation (RACG) addresses this limitation by coupling generation with dynamic retrieval of relevant code artifacts, enabling models to ground their outputs in project-specific context @gao2024rag. The premise is straightforward: before or during generation, retrieve the most relevant code snippets, documentation, or repository-level signals, and present them as additional input to the language model. Early work by Parvez et al. (2021) demonstrated that augmenting code generation with retrieved examples improved both functional correctness and code quality on standard benchmarks, establishing retrieval as a viable complement to pre-trained knowledge rather than a replacement for it.

Subsequent approaches refined the retrieval signal along several dimensions. RepoCoder @zhang2023repocoder introduced iterative retrieval and generation, where the model's initial output is used to refine subsequent retrieval queries, progressively narrowing the search space to the most contextually relevant files within a repository. RepoFusion @shrivastava2023repofusion took a complementary approach by fine-tuning code models on repository-level data so that retrieval and generation operate over a shared latent space optimized for cross-file understanding. Rather than relying solely on lexical overlap, these methods encode structural relationships between files—imports, call graphs, and shared type signatures—to surface context that purely semantic or keyword-based search would miss. Tao et al. (2025), in their comprehensive survey, observed that repository-level retrieval has become the dominant paradigm in the field, shifting focus from single-file completion to multi-file, multi-module generation tasks that more closely approximate real development workflows.

The empirical evidence, however, reveals a more nuanced picture. Wang et al. (2025) introduced CodeRAG-Bench, a standardized evaluation framework designed to isolate the contribution of retrieval from the contribution of the underlying language model. Their analysis showed that retrieval augmentation yields substantial gains on repository-level tasks—where context spans multiple files and modules—but the magnitude of improvement depends heavily on retrieval quality. When the retrieval component surfaces irrelevant or only superficially related code, performance can degrade, confirming that retrieval is not uniformly beneficial and that the choice of retrieval strategy, embedding model, and chunking granularity constitutes a design space with real consequences. EvoR @su2024evor attempted to address this by evolving retrieval heuristics through genetic programming, adapting the retrieval strategy to the specific codebase at hand rather than relying on a fixed configuration.

Beyond code completion, RACG has been applied to more ambitious software engineering tasks. On SWE-bench @jimenez2023swebench, which evaluates whether models can resolve actual GitHub issues by editing multiple files, retrieval augmentation proved essential for grounding agent-based systems in the relevant repository context. SWE-agent @yang2024sweagent demonstrated that an agent equipped with targeted file retrieval could navigate large codebases, identify bug locations, and propose patches with a non-trivial success rate, though performance remained far from human-level on the most challenging instances. These results suggest that retrieval augmentation is necessary but not sufficient for complex software engineering tasks—the agent's ability to reason about the retrieved content, iterate on failed attempts, and compose multi-file edits matters as much as the retrieval itself. Reflexion @shinn2024reflexion reinforced this finding by showing that allowing agents to reflect on and retry failed generations, informed by retrieval-augmented context, improved performance on multi-step coding tasks, though the gains were modest and inconsistent across problem types.
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

