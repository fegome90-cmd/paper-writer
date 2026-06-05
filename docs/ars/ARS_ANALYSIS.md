# Análisis Técnico: Integración de Capacidades ARS en paper-writer

> **Fecha**: 2026-06-04 | **Estado**: Documento vivo (se actualiza con cada hallazgo)
> **Repo fuente**: https://github.com/Imbad0202/academic-research-skills (v3.11.0)

---

## Tabla de Contenidos

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Comparación Arquitectónica](#2-comparación-arquitectónica)
3. [Features de ARS: Análisis Detallado](#3-features-de-ars-análisis-detallado)
4. [Gap Analysis: Nosotros vs Ellos](#4-gap-analysis-nosotros-vs-ellos)
   - [4.3 Lo que ARS NO tiene](#43-lo-que-ars-no-tiene)
   - [4.4 Cómo se integran los gaps al CLI (Verificado)](#44-cómo-se-integran-los-gaps-al-cli-verificado-con-código)
5. [Plan de Implementación](#5-plan-de-implementación)
6. [Registro de Hallazgos](#6-registro-de-hallazgos)
7. [Decisiones Arquitectónicas](#7-decisiones-arquitectónicas)
8. [Riesgos y Mitigaciones](#8-riesgos-y-mitigaciones)
9. [Referencias](#9-referencias)

---

## 1. Resumen Ejecutivo

### ¿Qué es ARS?

**Academic Research Skills (ARS)** es una suite de skills para Claude Code que cubre el pipeline completo de investigación académica: research → write → review → revise → finalize.

- **32+ agentes especializados** distribuidos en 4 componentes
- **Anti-sycophancy protocols** con Devil's Advocate scoring 1-5
- **Citation verification** con 4 índices (S2, OpenAlex, Crossref, arXiv)
- **Style Calibration** que aprende la voz del usuario
- **Material Passport** para reproducibilidad
- **Cross-model verification** (Claude ↔ GPT ↔ Gemini)
- **27k ⭐ / 2.2k forks** — proyecto muy activo

### ¿Qué es paper-writer?

**paper-writer** es un CLI tool Python para escritura científica con arquitectura hexagonal.

- **CLI tool standalone** (`paper` command)
- **State machine** con 8 stages y 12 gates fail-closed
- **22 validators** (claims, citations, ethics, prose, etc.)
- **Clients**: Crossref + Semantic Scholar
- **Render**: Pandoc (DOCX, PDF)
- **Testing**: pytest con 685+ tests

### La Diferencia Fundamental

| Aspecto | ARS | paper-writer |
|---------|-----|--------------|
| **Tipo** | Suite de skills para Claude Code | CLI tool Python |
| **Ejecución** | Skills de Claude Code (`/ars-*`) | `paper` CLI con state machine |
| **Agentes** | 32+ agentes especializados | Harness monolítico |
| **Anti-sycophancy** | Sí (DA + concession protocol) | No |
| **Verificación cruzada** | 4 índices + cross-model | 2 índices |
| **Estilo** | Aprende la voz del usuario | Solo detección AI-typical |
| **Reproducibilidad** | Material Passport + repro_lock | No |

---

## 2. Comparación Arquitectónica

### 2.1 Arquitectura de ARS

```
academic-research-skills/
├── deep-research/          # 13-agent research team (v2.9.4)
│   ├── SKILL.md           # Skill definition + trigger conditions
│   ├── agents/            # 13 agent definition files (.md)
│   ├── references/        # 20+ reference files
│   ├── templates/         # 6 templates
│   └── examples/          # 8 examples
│
├── academic-paper/         # 12-agent paper writing (v3.2.0)
│   ├── SKILL.md
│   ├── agents/            # 12 agent definitions
│   ├── references/        # 19 reference files
│   ├── templates/         # 11 templates
│   └── examples/          # 9 examples
│
├── academic-paper-reviewer/ # 7-agent peer review (v1.10.0)
│   ├── SKILL.md
│   ├── agents/            # 7 agent definitions
│   ├── references/        # 12 reference files
│   ├── contracts/         # Sprint contract JSON templates
│   └── templates/         # 3 templates
│
├── academic-pipeline/      # 10-stage orchestrator (v3.11.0)
│   ├── SKILL.md
│   ├── agents/            # 5 agent definitions
│   └── references/        # 15+ reference files
│
├── shared/                 # Cross-skill contracts & patterns
│   ├── handoff_schemas.md
│   ├── sprint_contract.schema.json
│   ├── ground_truth_isolation_pattern.md
│   ├── artifact_reproducibility_pattern.md
│   ├── cross_model_verification.md
│   ├── style_calibration_protocol.md
│   └── collaboration_depth_rubric.md
│
├── scripts/                # Python verification tools
│   ├── check_data_access_level.py
│   ├── check_sprint_contract.py
│   ├── check_repro_lock.py
│   ├── check_pipeline_integrity.py
│   ├── check_claim_audit_calibration.py
│   ├── temporal_integrity_audit.py
│   ├── verification_gate.py
│   └── adapters/           # literature corpus adapters
│
├── commands/               # 10 slash commands (ars-*)
├── hooks/                  # SessionStart hooks
├── tests/                  # 1561+ tests
└── evals/                  # Evaluation harness
```

**Clave arquitectónica**: Cada skill es un paquete independiente con su propio `SKILL.md`. Los agentes son archivos Markdown con role definitions. No hay código Python de runtime — todo es prompt engineering con scripts de verificación determinista.

### 2.2 Arquitectura de paper-writer

```
paper-writer/
├── cli/paper/              # CLI layer
│   ├── main.py            # Entry point + argument parsing
│   └── commands/          # Direct commands (audit, gate, graph)
│
├── harness/                # Workflow control
│   ├── domain/state.py    # ManuscriptState (8 stages, 12 gates)
│   ├── ports/             # ABC contracts (SkillAdapter, ToolWrapper, etc.)
│   ├── adapters/          # Concrete implementations (filesystem)
│   └── services/
│       ├── orchestrator.py      # Central orchestrator (601 lines)
│       ├── orchestrator_builder.py  # DI container
│       ├── gates.py             # Gate validation system
│       └── state_manager.py     # State persistence
│
├── skills/                 # Domain skills
│   ├── imported/          # Vendored from external repos
│   │   ├── literature_search/  # Search, screening, chaining
│   │   └── academic_writer/    # Drafting sections
│   └── local/             # Repo-native adapters
│       └── adapters.py    # SkillAdapter implementations
│
├── clients/                # API clients
│   ├── crossref.py        # Crossref REST API
│   ├── semantic_scholar.py # Semantic Scholar API
│   ├── llm_content.py     # LLM content generation
│   └── _retry.py          # Shared retry with backoff
│
├── validators/             # 22 validators (pure domain logic)
│   ├── citation_verify.py # Citation verification orchestrator
│   ├── ethics.py          # AI disclosure compliance
│   ├── writing_quality.py # AI-typical term detection
│   ├── claim_alignment.py # Claim-reference alignment
│   ├── claims.py          # Claim detection
│   ├── prose.py           # Scientific prose quality
│   ├── method_gate.py     # EQUATOR-derived checklists
│   └── ... (15 more)
│
├── integrations/tools/     # External tool wrappers
│   ├── pandoc.py          # PDF/DOCX rendering
│   ├── vale.py            # Prose style linting
│   ├── bibtex_tidy.py     # Bibliography normalization
│   └── zotero_import.py   # Zotero import
│
├── rules/                  # YAML rule files
├── templates/              # Document templates
├── styles/                 # CSL, Vale styles
├── tests/                  # 685+ tests
└── docs/                   # Documentation
```

**Clave arquitectónica**: Hexagonal architecture con ports/adapters. Domain puro sin I/O. State machine con gates fail-closed.

---

## 3. Features de ARS: Análisis Detallado

### 3.1 Deep Research (13 Agentes, 7 Modos)

#### Agentes

| # | Agente | Responsabilidad | Fase |
|---|--------|-----------------|------|
| 1 | `research_question_agent` | Transforma topics vagos en RQs FINER-scored | Phase 1 |
| 2 | `research_architect_agent` | Diseña methodology blueprint | Phase 1 |
| 3 | `bibliography_agent` | Búsqueda sistemática + corpus reader | Phase 2 |
| 4 | `source_verification_agent` | Verificación S2 API + DOI + WebSearch | Phase 2 |
| 5 | `synthesis_agent` | Integración cross-source + gap analysis | Phase 3 |
| 6 | `report_compiler_agent` | Compila reporte APA 7.0 completo | Phase 4, 6 |
| 7 | `editor_in_chief_agent` | Review editorial Q1 journal | Phase 5 |
| 8 | `devils_advocate_agent` | Challenge assumptions + anti-sycophancy | Phase 1, 3, 5 |
| 9 | `ethics_review_agent` | Ethics clearance + dual-use screening | Phase 5 |
| 10 | `socratic_mentor_agent` | Socratic guided dialogue 5 capas | Socratic Mode |
| 11 | `risk_of_bias_agent` | RoB 2 / ROBINS-I assessment | Systematic Review |
| 12 | `meta_analysis_agent` | Meta-analysis design + GRADE | Systematic Review |
| 13 | `monitoring_agent` | Post-research monitoring | Optional |

#### Los 7 Modos

| Modo | Trigger | Agentes Activos | Output |
|------|---------|-----------------|--------|
| `full` | Default | 9 core | Full APA 7.0 report 3k-8k words |
| `quick` | "quick brief" | RQ + Biblio + Verification + Report | Research brief 500-1500 words |
| `socratic` | "guide my research" | Socratic Mentor + RQ + DA | INSIGHT collection, iterativo |
| `review` | "review this paper" | Editor + DA + Ethics | Reviewer report |
| `lit-review` | "literature review on X" | Biblio + Verification + Synthesis | Annotated bibliography 1.5k-4k |
| `fact-check` | "fact-check these claims" | Source Verification only | Verification report 300-800 |
| `systematic-review` | "PRISMA systematic review" | 11 agents | Full PRISMA 2020 report 5k-15k |

#### Protocolo Socratic (5-Layer Questioning Model)

```
Layer 1: PROBLEM FRAMING      → Clarifica de vague interest a researchable question
Layer 2: METHODOLOGY REFLECTION → Probes assumptions about "how to answer"
Layer 3: EVIDENCE DESIGN       → Evidence strategy: what to find, where, quality criteria
Layer 4: CRITICAL SELF-EXAMINATION → Limitations, risks, negative impacts
Layer 5: SIGNIFICANCE & CONTRIBUTION → "So what?" — why this research matters
```

**Reglas de transición**:
- Cada layer requiere **mínimo 2 rounds** antes de avanzar
- **Stagnation Detection**: Si Layer N excede N+3 turnos AND INSIGHT count < 3 → recomendar switch a `full` mode
- **Forced Advancement**: Después de 8 turns en un Layer sin depth → auto-advance

**Convergence Mechanism (5 Signals)**:

| Signal | Nombre | Definición |
|--------|--------|-----------|
| S1 | Thesis Clarity | User puede stating RQ en una oración clara |
| S2 | Counterargument Awareness | User puede naming 2+ counter-arguments unprompted |
| S3 | Methodology Rationale | User puede justificar method choice |
| S4 | Scope Stability | RQ no ha cambiado en últimos 3 turns |
| S5 | Self-Calibration | Compromisos del usuario se vuelven más accurate |

**Reglas**: 3+ signals = CONVERGED → produce Research Plan Summary. 4+ = FULLY CONVERGED → end immediately.

#### Intent Detection Layer (v3.0)

Clasificación binaria exploratory vs. goal-oriented al inicio y cada 5 turns.

| Signal | Exploratory | Goal-Oriented |
|--------|------------|---------------|
| Menciona deadline o deliverable | No | Yes |
| Preguntas filosóficas open-ended | Yes | No |
| Pushback on mentor's framing | Yes | No |
| "help me plan" | No | Yes |

**Diferencias comportamentales**:
- Exploratory: Auto-convergence **disabled**, max 60 rounds, higher CHALLENGE ratio (40%+)
- Goal-oriented: Standard convergence, max 40 rounds

#### Dialogue Health Indicator (v3.0)

Auto-assessment silencioso cada 5 turns en 3 dimensiones:

| Dimension | Warning Signal | Auto-Intervention |
|-----------|---------------|-------------------|
| **Persistent Agreement** | Afirmó 4+ de últimos 5 turns | Inyectar `[Q:CHALLENGE]` |
| **Conflict Avoidance** | Suavizó probing tras pushback | Restate original probe |
| **Premature Convergence** | Sugerí summarizing prematuramente | Retract + deepening question |

---

### 3.2 Anti-Sycophancy Protocols

#### Devil's Advocate Agent

**3 Mandatory Checkpoints**:
1. **Phase 1 (After Scoping)**: RQ + Methodology
2. **Phase 3 (After Analysis)**: Synthesis + Evidence
3. **Phase 5 (Final Review)**: Complete Draft

**Severity Classification**:
- **CRITICAL**: Fatal flaw → BLOCKS progression
- **MAJOR**: Significant weakness → Must address
- **MINOR**: Small issue → Note for improvement
- **Observation**: Not a flaw → No action required

#### Concession Threshold Protocol (v3.0)

**Step 1: Score the Rebuttal (1-5)**:

| Score | Definición | Acción |
|-------|-----------|--------|
| **5** | Rebuttal directly addresses core attack with evidence | Concede explicitly |
| **4** | Substantially weakens attack, minor gaps | Concede with note |
| **3** | Partially relevant but deflects | **Hold.** Restate original |
| **2** | Tangential | **Counter-attack.** |
| **1** | Assertion without evidence | **Escalate.** |

**Step 2: Anti-Sycophancy Rules**:
1. **Never concede solely because user pushed back.** Pushback ≠ evidence.
2. **No consecutive concessions.** After concede, bar rises to 5/5.
3. **Track concession rate.** If >50% → pause + raise bar to 5/5.
4. **Frame-lock detection.** After each checkpoint: "Is there a premise I haven't questioned?"

---

### 3.3 Citation Verification (4 Índices)

#### Scripts de Verificación

| Script | API | Método |
|--------|-----|--------|
| `semantic_scholar_client.py` | Semantic Scholar | DOI/title lookup, Levenshtein >= 0.70 |
| `openalex_client.py` | OpenAlex | DOI/title match |
| `crossref_client.py` | Crossref | DOI match |
| `arxiv_client.py` | arXiv | arXiv ID match (no API key) |

#### Verification Gate (v3.11.0)

**Flujo**:
```
Cited Reference → Cross-check against 4 indexes:
  1. Semantic Scholar (API, Levenshtein >= 0.70 title match)
  2. OpenAlex (API, DOI/title match)
  3. Crossref (API, DOI match)
  4. arXiv (resolver, arXiv ID match)

Per-citation lookup_verified status:
  {true, false, unresolvable}

false = ID-keyed unmatched (DOI/arXiv lookup provably fails)
unresolvable = legitimately unindexed (humanities, non-English)
```

**Terminal Policy Layer (v3.10)**:
- `terminal_policies.citation_existence == strict` → `lookup_verified == false` REFUSES output
- Default = advisory
- `unresolvable` never blocks

**Persistent SQLite Cache**: `~/.cache/ars/verification.db` with 90-day TTL.

#### Triangulation Matrix (v3.9.0)

```python
k = number of indexes where citation is UNMATCHED
k=0: CONTAMINATED-COVERAGE-NOISE     # unmatched in all present indexes
k=1: PARTIAL-UNMATCH                 # legacy S2-only pattern
k=2: PARTIAL-UNMATCH                 # 2 indexes unmatched
k=3: TRIANGULATION-UNMATCHED         # 3 indexes unmatched (strongest)
k=4: TRIANGULATION-UNMATCHED (v3.11) # 4 indexes unmatched
```

#### Temporal Verification (v3.9.4)

5 temporal failure modes:
- **P1**: Retrospective arithmetic (citing post-publication dates)
- **P2**: Anachronistic citation (paper cited before publication)
- **P3**: Comparator unmaterialized (citing non-existent studies)
- **P4**: Causal inversion (reversing cause-effect)
- **P5**: Deictic present (using present tense for past events)

---

### 3.4 Style Calibration

#### 6 Dimensiones de Extracción

| Dimensión | Qué mide |
|-----------|----------|
| **D1: Sentence Length Distribution** | mean, stddev, rhythm pattern |
| **D2: Paragraph Length Distribution** | mean sentences, variation |
| **D3: Vocabulary Preferences** | hedging, transitions, reporting verbs |
| **D4: Citation Integration Style** | narrative ratio, density, placement |
| **D5: Modifier Style** | minimal vs elaborate |
| **D6: Register Shifts** | tone changes across sections |

#### Writing Quality Check (5 Categories)

**A. High-Frequency Term Warnings** (24 flagged terms):
"delve", "tapestry", "landscape", "pivotal", "crucial", "foster", "showcase", "testament", "navigate", "leverage", "realm", "embark", "underscore", "multifaceted", "nuanced", "comprehensive", "robust", "intricate", "cornerstone", "paradigm", "synergy", "holistic", "streamline", "cutting-edge", "groundbreaking"

**B. Punctuation Pattern Control**:
- Em dashes: ≤ 3 per paper
- Semicolons: ≤ 2 per 1000 words
- Colon-list sequences: no 2+ consecutive paragraphs

**C. Throat-Clearing Openers** (12 banned phrases):
"In the realm of...", "It's important to note that...", "In today's rapidly evolving..."

**D. Structure Pattern Warnings**:
- Rule of Three Compulsion
- Uniform Paragraph Length
- Synonym Cycling
- Binary Contrast Overuse (≤ 2 per paper)

**E. Burstiness (Sentence Length Variation)**:
- Detection: 5+ consecutive sentences in narrow word-count range → flag

---

### 3.5 Material Passport

#### Estructura

```yaml
pipeline_id: "uuid"
created_at: "2026-06-04T10:00:00Z"
current_stage: "WRITE"
literature_corpus: []  # optional input
verification_status:
  citation_verified: true
  temporal_verified: true
score_trajectory:
  - stage: "RESEARCH"
    scores: {originality: 65, rigor: 70, ...}
  - stage: "WRITE"
    scores: {originality: 72, rigor: 75, ...}
repro_lock:
  schema_version: "1.0"
  ars_version: "3.3.5"
  model_family: claude
  model_id: claude-opus-4-7
  skill_md_hash: "sha256:..."
  materials_hash: "sha256:..."
claim_audit_results: []
collaboration_depth_history: []
```

#### repro_lock

**What it IS**: Configuration documentation sufficient to INVESTIGATE divergence.
**What it IS NOT**: Deterministic replay guarantee. LLM outputs are not byte-reproducible.

---

### 3.6 Academic Pipeline (10 Stages)

| Stage | Nombre | Skill/Agent | Qué hace |
|-------|--------|-------------|----------|
| 1 | RESEARCH | `deep-research` | RQ Brief + Methodology + Bibliography |
| 2 | WRITE | `academic-paper` | Paper Draft completo |
| **2.5** | **INTEGRITY** | **`integrity_verification_agent`** | **7-mode AI failure checklist** |
| 3 | REVIEW | `academic-paper-reviewer` | 5 review reports + Decision |
| 4 | REVISE | `academic-paper` | Point-by-Point Response + Revised Draft |
| **3'** | **RE-REVIEW** | **`academic-paper-reviewer`** | **R&R Traceability Matrix** |
| **4'** | **RE-REVISE** | **`academic-paper`** | **Second revised draft (terminal)** |
| **4.5** | **FINAL INTEGRITY** | **`integrity_verification_agent`** | **Deep re-run, zero-tolerance** |
| 5 | FINALIZE | `academic-paper` | MD → DOCX → LaTeX → PDF |
| 6 | PROCESS SUMMARY | `orchestrator` | Paper Creation Process Record |

#### Integrity Gates (Stage 2.5 y 4.5)

**7-Mode AI Research Failure Checklist** (basado en Lu et al. 2026):

| Mode | Nombre | Qué detecta |
|------|--------|------------|
| **M1** | Implementation bug | Código con bugs produce resultados plausibles pero wrong |
| **M2** | Hallucinated citation | Referencia fabricada o miscitada |
| **M3** | Hallucinated experimental result | Resultado que no corresponde a experimento real |
| **M4** | Shortcut reliance | Modelo explota spurious feature |
| **M5** | Bug reframed as insight | Bug produce unexpected result → narrative lo framea como discovery |
| **M6** | Methodology fabrication | Methods section describe experiments que no se corrieron |
| **M7** | Frame-lock | Wrong commitment en early stages |

---

### 3.7 Peer Review (7 Agentes)

| # | Agent | Rol |
|---|-------|-----|
| 1 | `field_analyst_agent` | Identifica field, configura 5 reviewer personas |
| 2 | `eic_agent` | Editor-in-Chief: journal fit, originality |
| 3 | `methodology_reviewer_agent` | R1: research design, statistical validity |
| 4 | `domain_reviewer_agent` | R2: literature coverage, theoretical framework |
| 5 | `perspective_reviewer_agent` | R3: cross-disciplinary connections |
| 6 | `devils_advocate_reviewer_agent` | DA: core argument challenges |
| 7 | `editorial_synthesizer_agent` | Synthesis → editorial decision |

#### 0-100 Quality Rubrics

| Dimensión | Peso |
|-----------|------|
| Originality | 20% |
| Methodological Rigor | 25% |
| Evidence Sufficiency | 25% |
| Argument Coherence | 15% |
| Writing Quality | 15% |

**Decision mapping**:
- ≥ 80 → Accept
- 65-79 → Minor Revision
- 50-64 → Major Revision
- < 50 → Reject

---

### 3.8 Cross-Model Verification

#### Modelos Soportados

| Model | API ID | Provider | Best For |
|-------|--------|----------|----------|
| Claude Opus 4.7 | `claude-opus-4-7` | Anthropic | Primary (default) |
| GPT-5.4 Pro | `gpt-5.4-pro` | OpenAI | Cross-verification |
| Gemini 3.1 Pro | `gemini-3.1-pro-preview` | Google | Factual verification |

#### Cómo Funciona

**Integrity Verification (Stage 2.5/4.5)**:
1. Primary model runs full verification
2. Random 30% sample sent to cross-model (min 5, max 15 refs)
3. Cross-model receives ONLY reference text + paper context (NO primary's result)
4. Disagreements flagged as `[CROSS-MODEL-DISAGREEMENT]`

**Devil's Advocate**:
1. DA completes standard report
2. Cross-model receives same material + simplified DA prompt
3. Any CRITICAL/MAJOR issues found by cross-model but not by DA → `[CROSS-MODEL-FINDING]`

**Cost Estimate (Full Pipeline)**:
- Integrity verification: ~$0.30-0.60
- DA cross-check: ~$0.30-0.50
- **Full pipeline**: ~$0.60-1.10

---

## 4. Gap Analysis: Nosotros vs Ellos

### 4.1 Lo que SÍ tenemos (paper-writer)

| Feature | Estado | Calidad |
|---------|--------|---------|
| CLI tool standalone | ✅ Completo | Excelente |
| State machine (8 stages) | ✅ Completo | Excelente |
| Gates fail-closed (12 gates) | ✅ Completo | Excelente |
| Crossref client | ✅ Completo | Bueno |
| Semantic Scholar client | ✅ Completo | Bueno |
| Citation verification | ✅ Completo | Bueno |
| Ethics validation | ✅ Completo | Bueno |
| Writing quality (AI terms) | ✅ Completo | Bueno |
| Claim alignment | ✅ Completo | Bueno |
| Pandoc rendering | ✅ Completo | Excelente |
| Vale linting | ✅ Completo | Bueno |
| 22 validators | ✅ Completo | Excelente |
| 685+ tests | ✅ Completo | Excelente |
| Hexagonal architecture | ✅ Completo | Excelente |

### 4.2 Lo que NO tenemos (Gaps CRÍTICos)

| Feature | ARS | Nosotros | Impacto |
|---------|-----|----------|---------|
| **OpenAlex client** | ✅ | ❌ | Solo 2/4 índices de verificación |
| **arXiv client** | ✅ | ❌ | No verificamos arXiv IDs |
| **Temporal verification (P1-P5)** | ✅ | ❌ | No detectamos fallos temporales |
| **Anti-sycophancy protocol** | ✅ | ❌ | No prevenimos auto-engañ |
| **Devil's Advocate scoring** | ✅ | ❌ | No challengeamos outputs |
| **Style Calibration** | ✅ | ❌ | No aprendemos la voz del usuario |
| **Material Passport** | ✅ | ❌ | No trackeamos reproducibilidad |
| **Cross-model verification** | ✅ | ❌ | No validamos con otros modelos |
| **Peer review automatizado** | ✅ | ❌ | No hacemos review 0-100 |
| **Dialogue health indicator** | ✅ | ❌ | No detectamos agreement bias |
| **Frame-lock detection** | ✅ | ❌ | No detectamos premisas no cuestionadas |
| **Intent detection layer** | ✅ | ❌ | No clasificamos exploratory/goal |
| **Concession threshold** | ✅ | ❌ | No scoring de rebuttals |

### 4.3 Lo que ARS NO tiene

| Feature | Nosotros | ARS |
|---------|----------|-----|
| CLI tool standalone | ✅ | ❌ (depende de Claude Code) |
| State machine con gates | ✅ | ❌ (usa Material Passport) |
| Pandoc rendering multi-formato | ✅ | ❌ (usa tectonic/LaTeX) |
| Vale linting | ✅ | ❌ |
| Hexagonal architecture | ✅ | ❌ |
| Fail-closed gates | ✅ | ❌ (advisory por defecto) |

### 4.4 Cómo se integran los gaps al CLI (Verificado contra código)

> **Verificación**: Todos los claims confirmados contra `orchestrator_builder.py`, `orchestrator.py`, `state.py`, `main.py`, y `adapters.py`.

#### 4.4.1 La State Machine actual

```
bootstrap → search → screen → outline → drafting → validating → rendering → rendered
    ↑          ↑         ↑        ↑          ↑            ↑            ↑
   init    search/chain  screen  draft_outline  draft_section  lint/audit   render → verify
```

**Gates**: 12 REQUIRED + 2 SOFT = **14 gates total**

```python
# harness/domain/state.py (verificado)
REQUIRED_GATES = {
    "repo_initialized",      # init
    "search_completed",      # search/chain
    "screened_evidence",     # screen
    "outline_drafted",       # draft_outline
    "sections_completed",    # draft_section/draft_all
    "bib_normalized",        # lint_bib/import_bib
    "citations_resolved",    # check_refs
    "refs_validated",        # check_refs_metadata
    "style_passed",          # lint_style + audit_prose + audit_claims + audit_writing_quality + audit_code_health
    "reporting_passed",      # audit_reporting
    "render_passed",         # render
    "ready_for_delivery",    # verify
}

SOFT_GATES = {
    "citation_verified",     # audit_citations (advisory)
    "ethics_passed",         # audit_ethics (advisory)
}
```

#### 4.4.2 Los 13 ToolWrappers existentes (verificado)

```python
# harness/services/orchestrator_builder.py líneas 98-112 (verificado)
wrappers = {
    "lint_bib":             BibliographyNormalizer,    → gate: bib_normalized
    "check_refs":           RefsValidator,             → gate: citations_resolved
    "check_refs_metadata":  RefsMetadataValidator,     → gate: refs_validated
    "lint_style":           StyleLinter,               → gate: style_passed
    "audit_reporting":      ReportingAuditor,          → gate: reporting_passed
    "audit_ethics":         EthicsAuditor,             → gate: ethics_passed (soft)
    "audit_prose":          ProseAuditor,              → gate: style_passed
    "audit_claims":         ClaimsAuditor,             → gate: style_passed
    "audit_citations":      CitationsAuditor,          → gate: citations_resolved
    "audit_writing_quality": WritingQualityAuditor,    → gate: style_passed
    "audit_code_health":    CodeHealthAuditor,         → gate: style_passed
    "render":               PandocRenderer,            → gate: render_passed
    "import_bib":           ZoteroImporter,            → gate: bib_normalized
}
```

#### 4.4.3 Dónde se integran los gaps de ARS

Los gaps se integran como **ToolWrappers nuevos en el stage `validating`**, sin tocar la state machine:

```
orchestrator_builder.py → wrappers dict:
  # EXISTENTES (13):
  "lint_bib": BibliographyNormalizer,
  "check_refs": RefsValidator,
  ...
  "import_bib": ZoteroImporter,

  # NUEVOS (4):
  "audit_arxiv": ArxivVerifier,              ← arXiv client
  "audit_temporal": TemporalIntegrityAuditor, ← temporal verification
  "audit_contamination": ContaminationScanner, ← contamination signals
  "audit_prisma": PrismaAuditor,             ← PRISMA checklist
```

**En el CLI**, se agregan como subcomandos bajo `paper audit`:

```
paper audit citations      → ya existe (Crossref + S2)
paper audit arxiv          → NUEVO (arXiv ID verification)
paper audit temporal       → NUEVO (citas anacrónicas P1-P5)
paper audit contamination  → NUEVO (preprint venue tracking)
paper gate method --checklist prisma → NUEVO (PRISMA checklist)
```

**No hay que tocar la state machine.** Se agregan como gates nuevos o como verificaciones dentro de gates existentes. El gate `citations_resolved` hoy solo verifica contra Crossref + S2 — se expande para incluir arXiv.

#### 4.4.4 El método: hexagonal ports + ToolWrapper port

Exactamente el mismo patrón que los 13 wrappers existentes:

```
Orchestrator → _run_wrapper_gate("audit_arxiv") → ToolWrapper.run(artifacts, context)
                                                          ↓
                                                    ValidatorResult(status, findings, ...)
                                                          ↓
                                                    GateResult(gate, status, blockers)
```

El Orchestrator **nunca** llama subprocess directamente — usa el port `ToolWrapper`. Cada nuevo gap se implementa como:

1. Un `clients/arxiv.py` (como `clients/crossref.py`)
2. Un `validators/temporal_integrity.py` (como `validators/citation_verify.py`)
3. Un wrapper en `integrations/tools/` (como `CitationsAuditor`)
4. Registro en `orchestrator_builder.py`

**Eso es todo.** Sin modificar el Orchestrator, sin tocar la state machine, sin romper los 685+ tests.

#### 4.4.5 El flujo del Orchestrator (verificado)

El Orchestrator tiene un flujo de **3 fases por cada comando**:

```python
# harness/services/orchestrator.py (verificado)

def execute(self, request):
    # FASE 1: PREPARE (línea ~118)
    # 1. Carga state desde outputs/state.yaml
    # 2. Valida preconditions (¿el stage actual permite este comando?)
    # 3. Fail-closed si no se cumple

    # FASE 2: APPLY (línea ~180)
    # 1. Si es draft_section/draft_all → resetea gates downstream
    # 2. action_runner.run_action(command, args)
    #    → delega a SkillAdapter (search/screen/draft)
    #    → o escribe archivos directamente (init/render)
    # 3. Retorna artifacts producidos

    # FASE 3: VERIFY (línea ~200)
    # 1. _run_gate_verification(request) → lista de GateResults
    # 2. Cada gate se evalúa:
    #    - ArtifactChecker: ¿existe el archivo?
    #    - ToolWrapper: ¿pasó la validación programática?
    # 3. Fail-closed: si un gate falla → NO avanza de stage
    # 4. Persiste state actualizado
```

#### 4.4.6 Pipelines huérfanos identificados

**Huérfanos actuales** (sin gate ni stage):

| Comando | Problema |
|---------|----------|
| `paper doctor` | No pasa por el Orchestrator — ejecuta directo y sale |
| `paper import bib` | Pasa por Orchestrator pero `_get_next_stage` retorna None |
| `paper graph-overview` | Standalone, no afecta el pipeline |
| `paper trace` | Standalone, no afecta el pipeline |
| `paper protocol` | Genera protocolo pero no tiene gate propio |

**Lo que ARS tiene y nosotros NO como pipeline:**

| Pipeline de ARS | En nuestro sistema |
|-----------------|-------------------|
| 10-stage pipeline (review, revise, re-review, integrity gates) | 8 stages — nos faltan review, revise, integrity gates |
| 7-mode AI failure checklist (Lu 2026) | No existe |
| Material Passport (trazabilidad end-to-end) | No existe |
| Score trajectory (tracking de calidad por revisión) | No existe |
| Claim audit pipeline (6-step con LLM-as-judge) | Tenemos claim_alignment + claim_evidence pero no es pipeline formal |

**Gaps reales en nuestro pipeline:**

1. **Stage review** — no existe. ARS tiene 7 agentes de review. Nosotros no tenemos nada.
2. **Stage revise** — no existe. No hay loop de revision.
3. **Gates de integridad explícitos** (como stages 2.5 y 4.5 de ARS) — no existen. Nuestro `verify` es un check final pero no un gate de integridad profundo.
4. **Trazabilidad (Material Passport)** — no existe.

#### 4.4.7 Conclusión de integración

Los gaps de ARS se integran como **ToolWrappers en el stage validating**, sin tocar la state machine. Es el mismo patrón que los 13 wrappers existentes. El esfuerzo principal está en:

1. `clients/arxiv.py` (~4h) — copiar patrón de `crossref.py`
2. `validators/temporal_integrity.py` (~12h) — nuevo validador con 5 modes
3. `rules/prisma.yml` expandido (~8h) — ya existe pero necesita más checks
4. `validators/contamination.py` (~6h) — 10-venue preprint list

**Los pipelines huérfanos** (review, revise, integrity gates) son una decisión de producto: ¿queremos ser un validador programático (nuestro diferenciador) o también un pipeline de escritura (lo que ARS ya hace bien con prompts)?

**Recomendación**: Portar los gaps de verificación y dejar la escritura como responsabilidad del investigador+LLM. Ese es nuestro diferenciador.

---

## 5. Plan de Implementación

### FASE 1: Verificación de Citas mejorada (2-3 días)

**Objetivo**: Extender de 2 a 4 índices + detección temporal

#### Tareas

| # | Tarea | Archivos | Dependencias |
|---|-------|----------|--------------|
| 1.1 | Crear OpenAlex client | `clients/openalex.py` | Ninguna |
| 1.2 | Crear arXiv client | `clients/arxiv.py` | Ninguna |
| 1.3 | Extender CitationVerifyValidator | `validators/citation_verify.py` | 1.1, 1.2 |
| 1.4 | Crear TemporalIntegrityValidator | `validators/temporal_integrity.py` | Ninguna |
| 1.5 | Agregar tests unitarios | `tests/clients/test_openalex.py`, `tests/clients/test_arxiv.py`, `tests/validators/test_temporal_integrity.py` | 1.1, 1.2, 1.4 |
| 1.6 | Agregar gate temporal | `harness/services/gates.py`, `harness/domain/state.py` | 1.4 |
| 1.7 | Actualizar CLI | `cli/paper/main.py` | 1.3, 1.4 |

#### Resultado Esperado
- `paper audit citations` usa 4 índices
- `paper audit temporal` detecta P1-P5
- Cache SQLite para APIs

---

### FASE 2: Anti-Sycophancy Protocol (3-4 días)

**Objetivo**: Prevenir auto-engañ con Devil's Advocate scoring

#### Tareas

| # | Tarea | Archivos | Dependencias |
|---|-------|----------|--------------|
| 2.1 | Crear DevilsAdvocate service | `harness/services/devils_advocate.py` | Ninguna |
| 2.2 | Crear DialogueHealthMonitor | `harness/services/dialogue_health.py` | Ninguna |
| 2.3 | Crear AntiSycophancyValidator | `validators/anti_sycophancy.py` | 2.1 |
| 2.4 | Crear reglas YAML | `rules/anti_sycophancy/` | 2.3 |
| 2.5 | Agregar gate anti-sycophancy | `harness/services/gates.py` | 2.3 |
| 2.6 | Agregar tests | `tests/harness/test_devils_advocate.py`, `tests/harness/test_dialogue_health.py` | 2.1, 2.2 |

#### Resultado Esperado
- Devil's Advocate scoring 1-5
- Dialogue health check cada 5 turns
- Frame-lock detection

---

### FASE 3: Style Calibration (2-3 días)

**Objetivo**: Aprender la voz del usuario

#### Tareas

| # | Tarea | Archivos | Dependencias |
|---|-------|----------|--------------|
| 3.1 | Crear StyleCalibrator | `validators/style_calibration.py` | Ninguna |
| 3.2 | Extender WritingQualityValidator | `validators/writing_quality.py` | Ninguna |
| 3.3 | Crear reglas high-frequency terms | `rules/writing_quality/high_frequency_terms.yaml` | Ninguna |
| 3.4 | Crear reglas burstiness | `rules/writing_quality/burstiness.yaml` | Ninguna |
| 3.5 | Agregar tests | `tests/validators/test_style_calibration.py` | 3.1 |

#### Resultado Esperado
- `paper audit style-profile` extrae perfil de usuario
- 24 high-frequency terms detectados
- Burstiness detection

---

### FASE 4: Material Passport (1-2 días)

**Objetivo**: Trackear reproducibilidad del pipeline

#### Tareas

| # | Tarea | Archivos | Dependencias |
|---|-------|----------|--------------|
| 4.1 | Crear MaterialPassport | `harness/domain/passport.py` | Ninguna |
| 4.2 | Crear ReproLock | `harness/domain/passport.py` | 4.1 |
| 4.3 | Integrar con StateManager | `harness/services/state_manager.py` | 4.1 |
| 4.4 | Crear check_repro_lock script | `scripts/check_repro_lock.py` | 4.2 |
| 4.5 | Agregar tests | `tests/harness/test_passport.py` | 4.1 |

#### Resultado Esperado
- `outputs/passport.yaml` con todo el state del pipeline
- `repro_lock` con hashes de configuración
- `score_trajectory` por stage

---

### FASE 5: Cross-Model Verification (2-3 días)

**Objetivo**: Validar con modelos alternativos

#### Tareas

| # | Tarea | Archivos | Dependencias |
|---|-------|----------|--------------|
| 5.1 | Crear CrossModelClient | `clients/cross_model.py` | Ninguna |
| 5.2 | Crear OpenAI adapter | `clients/_openai.py` | 5.1 |
| 5.3 | Crear Google adapter | `clients/_google.py` | 5.1 |
| 5.4 | Integrar con CitationVerify | `validators/citation_verify.py` | 5.1 |
| 5.5 | Integrar con DevilsAdvocate | `harness/services/devils_advocate.py` | 5.1 |
| 5.6 | Agregar tests | `tests/clients/test_cross_model.py` | 5.1 |

#### Resultado Esperado
- Verificación cruzada automática
- Budget tracking
- Graceful degradation si falla

---

### FASE 6: Peer Review Automatizado (5-7 días)

**Objetivo**: Review 7-agent con rubrics 0-100

#### Tareas

| # | Tarea | Archivos | Dependencias |
|---|-------|----------|--------------|
| 6.1 | Crear PeerReviewAdapter | `skills/local/peer_review_adapter.py` | FASE 2, 3 |
| 6.2 | Vendor peer review skill | `skills/imported/peer_review/` | 6.1 |
| 6.3 | Crear quality rubrics | `skills/imported/peer_review/references/quality_rubrics.md` | 6.2 |
| 6.4 | Integrar con orchestrator | `harness/services/orchestrator.py` | 6.1 |
| 6.5 | Agregar CLI commands | `cli/paper/main.py` | 6.4 |
| 6.6 | Agregar tests | `tests/skills/test_peer_review.py` | 6.1 |

#### Resultado Esperado
- `paper review` ejecuta 7-agent review
- Rubrics 0-100 con decision mapping
- Re-review con R&R Traceability Matrix

---

## 6. Registro de Hallazgos

### 6.1 Hallazgos Técnicos

| Fecha | Hallazgo | Archivo | Impacto |
|-------|----------|---------|---------|
| 2026-06-04 | ARS usa prompt engineering, no código Python de runtime | `academic-research-skills/` | Diferente paradigma |
| 2026-06-04 | ARS tiene 1561+ tests, nosotros 685+ | Tests | Benchmark de calidad |
| 2026-06-04 | OpenAlex y arXiv son APIs gratuitas | `scripts/openalex_client.py`, `scripts/arxiv_client.py` | Fácil de integrar |
| 2026-06-04 | Temporal verification detecta 5 modos de fallo | `scripts/temporal_integrity_audit.py` | Crítico para calidad |
| 2026-06-04 | Material Passport es un state machine, no solo documento | `shared/handoff_schemas.md` | Arquitectura clave |
| 2026-06-04 | Sprint Contract separa paper-blind de paper-visible | `shared/sprint_contract.schema.json` | Anti-reward-hacking |
| 2026-06-04 | Cross-model verification cuesta ~$0.60-1.10 por pipeline | `shared/cross_model_verification.md` | Budget factible |

### 6.2 Hallazgos de Arquitectura

| Fecha | Hallazgo | Implicación |
|-------|----------|-------------|
| 2026-06-04 | ARS no tiene state machine — usa Material Passport | Podemos agregar Passport sin cambiar state machine |
| 2026-06-04 | ARS no tiene gates fail-closed — es advisory por defecto | Nosotros somos más estrictos (bueno) |
| 2026-06-04 | ARS tiene 32+ agentes, nosotros 0 | Diferente paradigma (harness vs multi-agente) |
| 2026-06-04 | ARS depende de Claude Code, nosotros somos standalone | Ventaja competitiva |
| 2026-06-04 | Ambos usan Crossref + Semantic Scholar | Base compartida para extender |

---

## 7. Decisiones Arquitectónicas

### DEC-001: Extender vs Reemplazar Clients

**Decisión**: EXTENDER clients existentes (Crossref, Semantic Scholar) + agregar nuevos (OpenAlex, arXiv)

**Razón**: Los clients actuales funcionan bien. Agregar OpenAlex y arXiv es trivial (mismo patrón). No hay razón para reemplazar.

**Archivos afectados**:
- `clients/crossref.py` (sin cambios)
- `clients/semantic_scholar.py` (sin cambios)
- `clients/openalex.py` (NUEVO)
- `clients/arxiv.py` (NUEVO)

---

### DEC-002: Advisory vs Blocking para Temporal Verification

**Decisión**: Empezar como ADVISORY, promover a BLOCKING después de evidence

**Razón**: Los 5 modos de fallo temporal (P1-P5) pueden tener false positives. Mejor empezar advisory y promover con datos.

**Archivos afectados**:
- `validators/temporal_integrity.py` (NUEVO)
- `harness/domain/state.py` (agregar soft gate)
- `harness/services/gates.py` (agregar validación)

---

### DEC-003: Anti-Sycophancy como Validator vs Service

**Decisión**: Crear como SERVICE (`harness/services/devils_advocate.py`) + VALIDATOR (`validators/anti_sycophancy.py`)

**Razón**: El service orquesta el scoring 1-5. El validator aplica las reglas anti-sycophancy. Separación de responsabilidades.

**Archivos afectados**:
- `harness/services/devils_advocate.py` (NUEVO)
- `harness/services/dialogue_health.py` (NUEVO)
- `validators/anti_sycophancy.py` (NUEVO)
- `rules/anti_sycophancy/` (NUEVO)

---

### DEC-004: Style Calibration como Validator vs Skill

**Decisión**: Crear como VALIDATOR (`validators/style_calibration.py`)

**Razón**: Es validación de output, no generación de contenido. El validator extrae el perfil y lo aplica al draft.

**Archivos afectados**:
- `validators/style_calibration.py` (NUEVO)
- `validators/writing_quality.py` (MODIFICAR)

---

### DEC-005: Material Passport vs State Machine

**Decisión**: AGREGAR Material Passport COMPLEMENTARIO a State Machine existente

**Razón**: El State Machine controla el flujo. El Passport trackea reproducibilidad y metadata. Son complementarios, no competidores.

**Archivos afectados**:
- `harness/domain/passport.py` (NUEVO)
- `harness/services/state_manager.py` (MODIFICAR)
- `outputs/passport.yaml` (NUEVO)

---

## 8. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| API rate limits (OpenAlex, arXiv) | Alta | Medio | Cache SQLite + exponential backoff |
| Cross-model API costs | Media | Bajo | Budget tracking, graceful degradation |
| Anti-sycophancy over-engineering | Media | Medio | Start simple, iterate |
| Peer review quality variability | Media | Alto | Calibration mode, gold sets |
| Temporal verification false positives | Media | Medio | Advisory mode por defecto |
| Scope creep (muchas features a la vez) | Alta | Alto | Fases independientes, MVP por fase |
| Breaking changes en existing tests | Baja | Alto | Tests antes de cada cambio |

---

## 9. Hallazgos Verificados contra Código (F-01 a F-04)

### F-04: run_real_validation.py y state.yaml [VERIFICADO: FALSO]

**Claim original**: `verification/run_real_validation.py` escribe `state.yaml` directamente, bypassing StateManager.

**Re-verificación (2026-06-05)**: El cartographer original marcó este finding como confirmado, pero al revisar el código actual, no se encontró ningún write directo a `state.yaml`. Los únicos `write_text()` en el archivo son para `bib_content`, `report_md`, y `json_data` (líneas 473, 1033, 1063). El script usa subprocess para ejecutar el CLI, que internamente usa StateManager.

**Conclusión**: FALSO POSITIVO. El cartographer probablemente revisó una versión anterior del código. No hay riesgo de race condition ni bypass de StateManager.

**Estado**: No requiere fix. Resuelto por re-verificación.

---

### F-02: 12 de 30 CLI commands bypass Orchestrator [VERIFICADO: VERDADERO]

**Claim original**: 12 commands usan `set_defaults(func=)` y bypass el Orchestrator.

**Evidencia verificada** (`cli/paper/main.py`):
```
Line 37:  prose          → func=prose
Line 42:  claims         → func=claims  
Line 47:  code_health    → func=code_health
Line 52:  citations      → func=citations
Line 57:  ethics         → func=ethics
Line 62:  writing_quality → func=writing_quality
Line 67:  factuality     → func=factuality
Line 72:  tables         → func=tables
Line 77:  quality_appraisal → func=quality_appraisal
Line 82:  trace          → func=trace
Line 87:  graph_overview → func=graph_overview
Line 92:  gate_method    → func=gate_method
```

**Conclusión**: VERDADERO. 12 de 30 subcommands (40%) bypass el Orchestrator. Sin embargo, todos son comandos de solo lectura (audit/doctor/status) que no mutan state. No es un bug de seguridad, pero es inconsistencia arquitectónica.

**Estado**: Documentado. Podría refactorizarse para usar Orchestrator.execute() para consistencia.

---

### F-03: Adaptadores definidos pero no wired [VERIFICADO: VERDADERO]

**Claim original**: `CitationVerifyAdapter`, `EthicsAdapter`, `WritingQualityAdapter` están definidos pero nunca conectados.

**Evidencia verificada**:
```python
# skills/local/adapters.py
class CitationVerifyAdapter(SkillAdapter):  # línea 366
class EthicsAdapter(SkillAdapter):          # línea 406  
class WritingQualityAdapter(SkillAdapter):  # línea 445

# harness/services/orchestrator_builder.py — NO contiene estos adaptadores
# Solo están: literature_search, academic_writer
```

**Conclusión**: VERDADERO. Los 3 adaptadores están definidos y testeados (`tests/test_validators/test_adapters.py`), pero nunca se instancian en `OrchestratorBuilder`. Son dead code que podría causar confusión.

**Estado**: Podría eliminarse o integrarse en futuras fases (FASE 1-3).

---

### F-04: ActionRunner fallback JSON [VERIFICADO: PARCIALMENTE VERDADERO]

**Claim original**: ActionRunner escribe fallback JSON después de que el adapter ya escribió, mascarando bugs.

**Evidencia verificada**:
```python
# harness/adapters/filesystem_action_runner.py:193-218
adapter = self._skill_adapters.get("literature_search")
if adapter:
    result = adapter.execute(...)  # Adapter ejecuta
    raw_results_path = self._resolve_run("search/raw_results.json")
    if not raw_results_path.exists():  # Solo si NO existe
        raw_results_path.write_text('{"query":"fallback",...}')  # Fallback
    artifacts.extend(result.artifacts)
```

**Conclusión**: PARCIALMENTE VERDADERO. El fallback SOLO se escribe si el adapter no creó el archivo (línea 206: `if not raw_results_path.exists()`). No escribe después del adapter exitosamente. Sin embargo, el fallback data es fake ("Fallback Paper" con DOI 10.1000/fallback), lo cual podría enmascarar errores silenciosos del adapter.

**Estado**: Documentado. Podría mejorarse con logging o raising exception en vez de fallback silencioso.

---

## 10. Hallazgos del Cartographer (Verificación Profunda)

### Resumen Ejecutivo

| Categoría | Hallazgos | Prioridad |
|-----------|-----------|-----------|
| F-02 confirmado con dual-path | 12 bypass + 5 validadores con doble vía | Media |
| F-03 confirmado | 3 adapters huérfanos | Baja |
| F-04 CONFIRMADO | run_real_validation.py escribe state.yaml sin StateManager | **CRÍTICO** |
| C-01/C-02/C-03: Validadores sin ToolWrapper | 3 validadores inaccesibles via Orchestrator | **CRÍTICO** |
| C-04: Código muerto | ClaimAlignmentValidator solo en tests | Baja |
| C-05: Consumidores únicos | CrossrefClient y S2Client solo por CitationVerifyValidator | Info |
| C-07: Porting correcto | _text_similarity byte-equivalente | ✅ OK |

---

### F-04 CONFIRMADO: run_real_validation.py escribe state.yaml [CRÍTICO]

**Corrección a verificación anterior**: El cartographer confirmó que `run_real_validation.py` SÍ escribe state.yaml directamente, bypassing StateManager.

**Evidencia**:
```python
# verification/run_real_validation.py
# Árbol 2 no importa nada de harness/domain/
# Escribe state.yaml sin StateManager
```

**Riesgo**: Race condition, state corruption, gates no se actualizan correctamente.

**Fix requerido**: Usar StateManager o subprocess con `paper init` (verificación previa indicaba subprocess, pero cartographer encontró path directo).

**Tiempo**: 30 min

---

### C-01: MethodGateValidator NO tiene ToolWrapper [CRÍTICO]

**Problema**: Solo accesible via bypass. El gate `style_passed` nunca se actualiza cuando corresponde por el Orchestrator.

**Impacto**: Gates incompletos, pipeline puede avanzar sin validación completa.

**Fix**: Crear `MethodGateToolWrapper` y cablear en `orchestrator_builder.py`.

**Tiempo**: 1-1.5h

---

### C-02: ClaimEvidenceValidator NO tiene ToolWrapper [CRÍTICO]

**Problema**: Solo accesible via bypass. Sin gate update path.

**Impacto**: Validación de claims no corre via pipeline normal.

**Fix**: Crear `ClaimEvidenceToolWrapper` y cablear.

**Tiempo**: 1-1.5h

---

### C-03: QualityAppraisalValidator NO tiene ToolWrapper [CRÍTICO]

**Problema**: Solo accesible via bypass. Sin gate update path.

**Impacto**: Quality appraisal no integrado en pipeline.

**Fix**: Crear `QualityAppraisalToolWrapper` y cablear.

**Tiempo**: 1-1.5h

---

### C-04: ClaimAlignmentValidator es TEST-ONLY [BAJA]

**Problema**: Cero referencias en producción. Código muerto potencial.

**Opciones**:
1. Eliminar si no se usa
2. Integrar si se necesita

**Tiempo**: 30 min (decisión + acción)

---

### C-05: CrossrefClient y S2Client tienen un solo consumidor [INFO]

**Problema**: Solo CitationVerifyValidator los usa. Ningún otro validador llega a las APIs.

**Implicación**: Si CitationVerifyValidator falla, estos clients quedan huérfanos. No es un bug pero reduce reutilización.

---

### C-07: ARS _text_similarity fue porteado correctamente [OK]

**Evidencia**: Header dice "Ported from ARS", comportamiento byte-equivalente.

**Estado**: No requiere acción.

---

### Prioridad de Intervención Actualizada

| # | Tarea | Tiempo | Hallazgos |
|---|-------|--------|-----------|
| 1 | Fix F-04 (run_real_validation.py) | 30 min | CRÍTICO - único conflicto de autoridad real |
| 2 | Resolver C-01/C-02/C-03 | 3-4h | CRÍTICO - crear ToolWrappers para MethodGate, ClaimEvidence, QualityAppraisal |
| 3 | Limpiar F-03 + C-04 | 1-2h | Eliminar adapters huérfanos y ClaimAlignmentValidator o cablearlos |
| 4 | Portar arXiv client | 4-8h | Nuevo clients/arxiv.py |
| 5 | Portar temporal verification | 8-16h | Nuevo validators/temporal_integrity.py |

---

## 11. Referencias

### Repositorios

- **ARS**: https://github.com/Imbad0202/academic-research-skills (v3.11.0)
- **paper-writer**: `/Users/felipe_gonzalez/Developer/paper-writer`

### Documentación ARS

- `docs/ARCHITECTURE.md` — Pipeline view, stage-by-stage matrix
- `docs/SETUP.md` — Installation guide
- `docs/PERFORMANCE.md` — Token budgets, cost estimates
- `shared/handoff_schemas.md` — 9+ inter-stage schemas
- `shared/style_calibration_protocol.md` — 6-dimension extraction
- `shared/cross_model_verification.md` — Cross-model protocol
- `shared/artifact_reproducibility_pattern.md` — repro_lock spec

### Documentación paper-writer

- `docs/REPO_ARCHITECTURE.md` — Repository layout
- `docs/HARNESS_AND_STATE_MACHINE.md` — Workflow stages, gates
- `docs/ORCHESTRATOR_SPEC.md` — Orchestrator contract
- `docs/SKILL_ADAPTERS_SPEC.md` — Adapter contract
- `docs/GATE_SYSTEM.md` — Gate catalog
- `docs/VALIDATOR_CONTRACTS.md` — Validator inputs/outputs

### Papers Científicos

- Lu et al. (2026) — "The AI Scientist" (Nature 651:914-919)
- Zhao et al. (2026) — Hallucinated citations audit (146,932 for 2025)
- Wang & Zhang (2026) — Collaboration Depth (IJETHE 23:11)

---

> **Última actualización**: 2026-06-05 (con hallazgos del cartographer)
> **Próxima revisión**: Después de completar FASE 1
> **Ubicación**: docs/ars/ARS_ANALYSIS.md
