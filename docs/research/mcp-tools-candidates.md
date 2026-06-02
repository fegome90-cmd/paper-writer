# MCP tools candidates for paper-writer

> ⚠ **Architecture correction (2026-06-01)**: This document was originally
> framed as "MCP tools that paper-writer exposes via CLI". The corrected
> direction is: **paper-writer does NOT expose MCP tools in v1**. The `paper`
> CLI **consumes** MCPs externos (Robin, ERA, otros) through adapters. This
> file is preserved as a reference of WHICH external tools the CLI may consume.
> The canonical architecture will be documented separately once written.

## Scope

Candidatas son **MCPs externos** que el CLI orquestador consume (Robin, ERA,
otros). paper-writer no expone tools propias en v1. No implican implementar
Robin ni ERA ni depender de ellos en runtime.

| Nombre | Descripción | Input schema preliminar | Output schema preliminar | Prioridad | Dependencia | Riesgo | Fuente de inspiración |
|---|---|---|---|---|---|---|---|
| `paper_claim_audit` | Extrae claims y marca soporte requerido y riesgo | `{ markdown: string, manuscript_type: string, reporting_guide?: string }` | `{ claims: [{ id, text, claim_type, evidence_required, risk, recommendation }] }` | P0 | Local CLI / validators | Medio | Propio + Robin |
| `paper_evidence_map` | Mapea papers contra pregunta, diseño, outcomes y claims | `{ papers: [{ id, title, abstract?, fulltext_path? }], research_question: string, framework: "PICO"|"SPIDER"|"custom", supported_claims?: [string] }` | `{ matrix: [{ paper_id, population, design, intervention_or_exposure, comparator, outcome, key_finding, limitation, supported_claims: [string] }], gaps: [string] }` | P0 | Local parser; posible búsqueda futura | Medio | Robin |
| `paper_reviewer2` | Devuelve crítica dura, metodológica y editorial antes de envío | `{ manuscript: string, target_journal?: string, study_type?: string }` | `{ critiques: [{ severity, section, issue, why_it_matters, suggested_fix }], overclaims: [string], blockers: [string] }` | P0 | Local prompts + validators | Alto | Robin + propio |
| `paper_method_gate` | Aplica un gate fail-closed contra checklist metodológica | `{ manuscript_or_protocol: string, study_type: string, checklist: string }` | `{ pass: boolean, blockers: [{ item, reason }], warnings: [string], minimum_actions: [string] }` | P0 | Local checklists | Bajo | Propio |
| `paper_reference_verify` | Verifica consistencia de referencias y relación con claims | `{ references: [{ raw, citation_key? }], claims?: [{ id, text, refs: [string] }] }` | `{ verified_refs: [{ raw, doi?, pmid?, status }], suspicious_refs: [string], unsupported_claims: [string] }` | P1 | Local validators; futura conexión externa opcional | Medio | Propio |
| `paper_wiki_sync` | Propone cambios en wiki y ledger a partir de auditorías | `{ audit_findings: object, wiki_path: string, claim_ledger_path?: string }` | `{ proposed_updates: [{ page, action, summary }], new_claims: [string], modified_claims: [string] }` | P1 | Local files | Medio | Robin + propio |
| `paper_hypothesis_generate` | Genera hipótesis candidatas con constraints y evidencia requerida | `{ topic: string, corpus?: [string], methodological_constraints?: [string], negative_constraints?: [string] }` | `{ hypotheses: [{ id, text, testability, required_evidence, suggested_design, risks: [string] }] }` | P1 | Local corpus; futura búsqueda opcional | Alto | Robin + ERA + propio |
| `paper_experiment_plan` | Convierte hipótesis en plan experimental/analítico escorable | `{ hypothesis: string, study_type: string, data_constraints?: [string], success_metric?: string }` | `{ plan: [{ step, rationale, dependency }], scoreability: { level, metric_needed }, risks: [string] }` | P1 | Local templates | Medio | ERA |
| `paper_repro_audit` | Audita scripts/notebooks/anexos computacionales | `{ artifact_path: string, artifact_type: "notebook"|"script"|"pipeline", data_contract?: string }` | `{ reproducibility_status: string, environment_gaps: [string], unsafe_ops: [string], rerun_requirements: [string] }` | P2 | Sandbox local y parser de notebooks | Medio-Alto | ERA |

## Prioridad recomendada

- **P0**: `paper_claim_audit`, `paper_evidence_map`, `paper_reviewer2`, `paper_method_gate`
- **P1**: `paper_reference_verify`, `paper_wiki_sync`, `paper_hypothesis_generate`, `paper_experiment_plan`
- **P2**: `paper_repro_audit`

## Criterio de resolución: Local vs MCP externo

- **Local primero (Phase 0)**: toda lógica de auditoría, gates y extracción
  estructurada que sea determinística y offline. El CLI resuelve localmente
  cuando el adapter MCP no está disponible.
- **MCP externo cuando disponible**: tools que requieren capacidad externa
  (búsqueda de evidencia, generación de hipótesis con scoring). El CLI detecta
  disponibilidad y delega al adapter.
- **Nunca exponer**: paper-writer no expone tools MCP propias en v1. Si en
  el futuro eso se necesita, será un concern separado, no el corazón del
  sistema.
