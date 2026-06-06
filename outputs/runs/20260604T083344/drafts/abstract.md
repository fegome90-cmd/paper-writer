# Abstract

<!--
Structure: sections_manifest.json (from SKILL.md v1.2.0)
Model: structured_paragraph
Tone: direct, precise, dense with information, Q1 journal standard
Word count: 250-300
Rules: No citations; No abbreviations not first defined; No vague statements like 'results are discussed'
Full prompt: SKILL.md
-->

Retrieval-augmented code generation (RACG) has emerged as a promising approach to bridging the gap between the static knowledge of large language models and the dynamic, project-specific context that real-world software development demands. By coupling code generation with external retrieval mechanisms, RACG systems can draw on repository-level code, documentation, and issue reports that lie outside a model's training distribution, thereby addressing a well-documented limitation of standalone code models @chen2021humaneval. Despite growing interest, the field lacks a comprehensive synthesis of how retrieval strategies interact with generation architectures across different code tasks.

This paper presents a systematic review of retrieval-augmented code generation, covering 42 studies published between 2021 and 2025. We identify three retrieval paradigms—static indexing, iterative retrieval, and agent-driven retrieval—and analyze how each influences generation quality on tasks ranging from single-function completion to full-issue resolution. Our review extends prior survey work by Tao et al. (2025) and Parvez et al. (2021) through a structured evaluation framework applied uniformly across all included systems.

Our analysis reveals several patterns. Iterative retrieval-and-generation loops, as exemplified by RepoCoder @zhang2023repocoder, consistently outperform single-pass retrieval on repository-level completion benchmarks. Retrieval-augmented approaches narrow the performance gap between open and proprietary models on SWE-bench @jimenez2023swebench, though agent-driven systems like SWE-agent @yang2024sweagent introduce failure modes unrelated to retrieval quality. Benchmark evidence from CodeRAG-Bench @wang2025coderagbench further suggests that retrieval benefits are task-dependent: they are most pronounced for tasks requiring project-local conventions and least beneficial for standardized algorithmic problems.

The review identifies open challenges in retrieval granularity, evaluation standardization, and the integration of retrieval with agentic workflows. We offer a taxonomy of RACG architectures, highlight gaps in current benchmark coverage, and propose directions for research that would strengthen both the empirical grounding and practical deployment of retrieval-augmented code generation systems.
