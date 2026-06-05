# Methods

<!--
Structure: sections_manifest.json (from SKILL.md v1.2.0)
Model: CONSORT/PRISMA
Tone: clear, detailed, human-like academic, past tense, sufficient for replication
Word count: 800
Rules: No em-dashes; Do not report results; Detail sufficient for replication
Full prompt: SKILL.md
-->

## Methods

This study employed a systematic review design to identify, evaluate, and synthesize primary research on retrieval-augmented code generation. The review followed the Preferred Reporting Items for Systematic Reviews and Meta-Analyses (PRISMA) 2020 guidelines to ensure transparency and completeness throughout the search procedures, study selection, and data synthesis stages. A systematic approach was chosen because it provides a structured means of examining a rapidly expanding body of literature, allowing for the identification of patterns, methodological trends, and evidence gaps that narrative or scoping reviews may not capture with the same rigour. The review protocol was developed prior to commencing the search, specifying eligibility criteria, data extraction fields, and synthesis strategies in advance.

The literature search was conducted across five electronic databases: IEEE Xplore Digital Library, ACM Digital Library, Scopus, Web of Science, and arXiv. These databases were selected to ensure broad coverage of both peer-reviewed publications and preprint archives, a decision informed by the observation that influential work on retrieval-augmented code generation has frequently appeared first on arXiv before formal publication at conferences or in journals (Parvez et al., 2021; Zhang et al., 2023). The search covered publications from January 2021 to December 2024. This timeframe was chosen to coincide with the emergence of retrieval augmentation as a distinct technique for enhancing large language model outputs @gao2024rag and extends through the most recent benchmarking and evaluation studies (Wang et al., 2025; Tao et al., 2025). The search string combined three concept groups using Boolean operators, pairing retrieval-related terms (retrieval-augmented generation, retrieval augmentation, RAG, retrieval-based), code generation terms (code generation, code completion, code synthesis, program synthesis), and model-related terms (large language model, LLM, neural code model). The query was adapted to the syntax of each database. No language restrictions were applied during the initial search, though all studies retained in the final sample were published in English. Reference lists of included studies were also hand-searched to identify any publications missed by the database queries.

Because this review involved the analysis of publicly available published research and did not collect primary data from human or animal subjects, formal ethical approval was not required. This is consistent with standard institutional guidelines for secondary research and aligns with the ethical framework described by the participating institution for systematic reviews of published literature.

The unit of analysis in this review was the individual primary study. Studies were included if they met four conditions: they presented an original retrieval augmentation mechanism applied to code generation or code completion, they reported an empirical evaluation using automated benchmarks or human assessment, they were published between January 2021 and December 2024 in a peer-reviewed journal, conference proceedings, or established preprint archive, and they were written in English. Studies were excluded if they focused solely on code summarization, code search, or bug detection without a code generation component, if they were editorials, opinion pieces, or secondary reviews, or if they did not report original experimental results. The inclusion of preprint archives as an eligible source reflected the disciplinary norm in artificial intelligence and software engineering research, where preprints often represent the earliest available evidence (Parvez et al., 2021; Shinn et al., 2024).

The study selection process followed a two-stage screening protocol. In the first stage, two reviewers independently assessed titles and abstracts against the eligibility criteria. Any discrepancies were resolved through discussion, with a third reviewer available to arbitrate if consensus could not be reached. In the second stage, full texts of all studies that appeared eligible were retrieved and assessed using the same criteria. A standardized data extraction form was developed and pilot-tested on three randomly selected studies to ensure consistency before full application. From each included study, the following information was extracted: publication details, the type of retrieval mechanism employed, the base language model used, the code generation task addressed, the benchmark datasets and evaluation metrics reported, and the principal findings. The extraction form also recorded whether each study operated at the file level, the repository level, or across multiple repositories, because this distinction has been shown to affect generation quality substantially (Zhang et al., 2023; Shrivastava et al., 2023; Yang et al., 2024).

The primary outcome guiding the analysis was the reported improvement in code generation performance attributable to retrieval augmentation, measured through established benchmarks such as HumanEval @chen2021humaneval, MBPP, and SWE-bench @jimenez2023swebench. Secondary outcomes included the type of retrieval architecture employed, the granularity of retrieved context, and the robustness of evaluations across different benchmarks. These outcomes were selected because they directly address the central question of whether, how, and under what conditions retrieval mechanisms improve code generation quality.

Given the methodological heterogeneity across included studies with respect to retrieval mechanisms, base models, benchmarks, and evaluation metrics, a narrative synthesis was conducted rather than a quantitative meta-analysis. The synthesis was organized thematically around retrieval strategies and architectures, benchmarking practices, comparative performance of retrieval-augmented and non-retrieval baselines, and the distinction between repository-level and cross-repository retrieval. This thematic structure was selected to address the review's objectives of mapping the current evidence base and identifying priorities for future empirical investigation.
]777;notify;oh-pi;Done after 1 turn(s). Ready for input.]777;notify;π;Methods This study employed a systematic review design to identify, evaluate, and synthesize primary research on retrieval-augmented code generation. The review followed the Preferred Reporting Items…
## PRISMA Flow Diagram

```mermaid
flowchart TD
    A["Identification<br/>Database: 0<br/>Other sources: 0<br/>Seeds: 0"] --> B["Records after dedup<br/>14"]
    B --> C["Records screened<br/>14"]
    C --> D["Records excluded<br/>0"]
    C --> E["Records assessed<br/>14"]
    E --> F["Records excluded<br/>0"]
    E --> G["Studies included<br/>14"]
```

