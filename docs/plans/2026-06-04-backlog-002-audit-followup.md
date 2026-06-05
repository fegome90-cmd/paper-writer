# BACKLOG-002 Audit Follow-up Plan

> **For Claude:** Execute this plan task-by-task using repo-local commands and evidence capture. Repo-local commands are the default, BUT Task 1 explicitly depends on Engram/OpenSpec retrieval when available; if Engram is unavailable, record SDD traceability as unverifiable and continue fail-closed with filesystem evidence only.

**Goal:** Identificar qué quedó sin atender alrededor de `BACKLOG-002` para separar cierre SDD real, drift documental, deuda técnica adyacente y fixes posteriores.

**Architecture:** Esta pasada NO implementa fixes. Primero reconstruye evidencia SDD, después compara contrato vs runtime vs docs/tests, y recién al final clasifica hallazgos en “bloquea cierre”, “deuda adyacente” y “fuera de alcance”.

**Tech Stack:** Python, pytest, mypy, YAML state repository, harness/orchestrator docs

---

### Task 0: Inicializar el report file antes de cualquier append

**Files:**
- Create/Update: `docs/plans/2026-06-04-backlog-002-audit-followup-report.md`

**Step 1: Crear baseline auditable**

Run:
```bash
cat > docs/plans/2026-06-04-backlog-002-audit-followup-report.md <<'EOF'
# BACKLOG-002 Audit Follow-up Report

Date: 2026-06-04
Source plan: docs/plans/2026-06-04-backlog-002-audit-followup.md

## Task 1 — Slug Candidates

## Task 1 — SDD Traceability / Artifact-Store Verdict

## Task 2 — Semantic Drift

## Task 3 — Legacy Compatibility

## Task 4 — Manifest and Schema Contract

## Task 5 — Runtime vs Adjacent Debt

## Task 6 — Fix Backlog
EOF
```

Rule:
- Si el archivo ya existe, sobreescribirlo SOLO al comienzo de una nueva pasada completa.

### Task 1: Reconstruir el estado real del SDD, sin asumir slug ni backend

**Files:**
- Inspect: `docs/CODE_ISSUES_LOG.md`
- Inspect: `docs/plans/`
- Inspect: Engram topics only AFTER proving the actual change slug/key from repo evidence
- Inspect: `openspec/`

**Reglas de entrada**
- Tomar `BACKLOG-002` como identificador documental primario.
- No asumir que el slug real del cambio es `backlog-002-stage-semantics`.
- Task 1 puede usar Engram/OpenSpec como fuentes REQUERIDAS de evidencia aunque el resto del plan priorice comandos repo-locales.
- Si Engram no está disponible en el runtime, registrar `Engram traceability = unverifiable`, PERO seguir auditando OpenSpec/file-system evidence de forma obligatoria antes de cerrar Task 1.
- Todo claim histórico preciso que no pueda reprobarse queda `unverifiable`.

**Step 1: Verificar artifacts SDD existentes**

Run primero sobre la fuente autoritativa:
```bash
rg -n "BACKLOG-002|backlog-002-stage-semantics" docs/CODE_ISSUES_LOG.md
```

Luego usar `docs/plans/` SOLO como corroboración secundaria:

```bash
rg -n "BACKLOG-002|backlog-002-stage-semantics" docs/plans \
  -g '!docs/plans/2026-06-04-backlog-002-audit-followup.md' \
  -g '!docs/plans/2026-06-04-backlog-002-audit-followup-report.md'
```

Output:
- Append findings to `docs/plans/2026-06-04-backlog-002-audit-followup-report.md` under `## Task 1 — Slug Candidates`.
- Hits en `docs/plans/` NO prueban slug por sí solos; solo cuentan si confirman un identificador ya visto en `docs/CODE_ISSUES_LOG.md` o si luego aparecen como path/topic exacto en Engram/OpenSpec.

**Step 1b: Probar el slug real del cambio**
- Derivar candidatos SOLO desde evidencia encontrada en Step 1.
- Si solo existe `BACKLOG-002`, usar `BACKLOG-002` como identificador documental, no como slug SDD probado.
- No consultar Engram/OpenSpec con un slug inventado.
- Marcar cualquier slug no probado como `unverifiable`.

**Step 2: Verificar trazabilidad del artifact store**

Procedure:
- First prove one or more candidate slugs from Step 1 evidence.
- If no slug can be proven, set `candidate slug = unverifiable` and audit by `BACKLOG-002` references only.
- If Engram is unavailable, skip only the Engram branch; OpenSpec/file-system inspection remains REQUIRED.
- Engram invocation contract:
  - For each proved slug, query exact artifact candidates only:
    - `sdd/<slug>/explore`
    - `sdd/<slug>/proposal`
    - `sdd/<slug>/spec`
    - `sdd/<slug>/design`
    - `sdd/<slug>/tasks`
    - `sdd/<slug>/apply-progress`
    - `sdd/<slug>/verify-report`
    - `sdd/<slug>/state`
    - `sdd/<slug>/archive-report`
  - `mem_search(query: "<exact_topic_key>", project: "paper-writer")`
  - if a match appears, `mem_get_observation(id: <match-id>)`
  - count `present` ONLY when topic/title/content clearly identify the exact artifact; incidental mentions count as `missing`
  - if no exact-topic match is possible, record `status = unverifiable`
  - record `lookup query | returned id | exact match? | final status`
- OpenSpec invocation contract:
  ```bash
  find openspec -type d \\( -iname '*backlog-002*' -o -iname '*stage-semantics*' \\)
  find openspec/changes/archive -type d 2>/dev/null | rg 'backlog-002|stage-semantics'
  rg -n "BACKLOG-002|backlog-002|stage-semantics|explore|exploration|proposal|spec|design|tasks|apply-progress|verify-report|gate-report|archive-report" openspec
  ```
- OpenSpec paths to inspect before declaring absence:
  - `openspec/changes/<slug>/`
  - `openspec/<slug>/`
  - `openspec/changes/archive/<date>-<slug>/`
  - filename variants: `explore.md`, `exploration.md`, `proposal.md`, `spec.md`, `design.md`, `tasks.md`, `apply-progress.md`, `state.yaml`, `verify-report.md`, `gate-report.md`, `archive-report.md`
- If `candidate slug = unverifiable`, use fuzzy search ONLY to discover a concrete path/slug candidate:
  - `rg -n "BACKLOG-002|stage-semantics" openspec`
  - If this yields a concrete directory or filename candidate, re-run the exact path inspection above against that candidate.
  - If it does NOT yield a concrete candidate, keep `store verdict = unverifiable`; do NOT mark any artifact `present` from fuzzy hits alone.
- If backend/storage mode remains ambiguous, audit BOTH Engram and OpenSpec and record `storage mode = unverifiable`.
- Record `artifact | candidate slug | store | status | evidence path/id | date | impact`

Expected checks:
- `explore` existe
- `proposal` existe
- `spec` existe
- `design` existe
- `state` existe o falta explícitamente
- `archive-report` existe o falta explícitamente
- `verify-report` existe
- `tasks` / `apply-progress` faltan o existen

Closure rule:
- Only mark `SDD closure evidence incomplete` after checking every relevant backend for the chosen storage mode.
- If `tasks`, `apply-progress`, `state`, or `archive-report` are missing across all applicable backends, mark the gap explicitly.
- If a historical completion claim cannot be reproved from exact evidence, rewrite it in the report as `unverifiable`.

**Step 3: Anotar gap de trazabilidad**

Deliverable:
- una tabla corta con `artifact | store | present | missing | evidence path/id | date | impact`
- Write it into `docs/plans/2026-06-04-backlog-002-audit-followup-report.md` under `## Task 1 — SDD Traceability / Artifact-Store Verdict`.

### Task 2: Barrer drift semántico `verified` vs `rendered`

**Files:**
- Inspect: `docs/PRODUCTION_READINESS.md`
- Inspect: `docs/TESTING_STRATEGY.md`
- Inspect: `docs/STATE_MANAGER_SPEC.md`
- Inspect: `docs/GATE_SYSTEM.md`
- Inspect: `docs/HARNESS_AND_STATE_MACHINE.md`
- Inspect: `docs/PHASE_LEDGER.md`
- Inspect: `docs/plans/2026-06-04-backlog-002-audit-followup-report.md`
- Inspect: `tests/harness/test_domain_consistency.py`
- Inspect: `tests/harness/test_orchestrator.py`

**Step 1: Buscar referencias stale**

Run:
```bash
rg -n 'verified|rendered|transitions_to_verified|transitions_to_rendered' \
  docs/PRODUCTION_READINESS.md \
  docs/TESTING_STRATEGY.md \
  docs/STATE_MANAGER_SPEC.md \
  docs/GATE_SYSTEM.md \
  docs/HARNESS_AND_STATE_MACHINE.md \
  docs/PHASE_LEDGER.md \
  docs/plans/2026-06-04-backlog-002-audit-followup-report.md \
  tests/harness/test_domain_consistency.py \
  tests/harness/test_orchestrator.py
```

**Step 1b: Buscar nombres stale en tests**

Run:
```bash
rg -n 'def test_.*(verified|rendered)|class Test.*(Verified|Rendered)' \
  tests/harness/test_domain_consistency.py \
  tests/harness/test_orchestrator.py
```

**Step 2: Clasificar cada match**

Buckets:
- `real bug`
- `stale docs`
- `stale comment/docstring`
- `stale test name/identifier`
- `not related to BACKLOG-002`

**Step 3: Crear lista de fixes mínimos**

Deliverable:
- append `path | line | issue | suggested fix | bucket` into `docs/plans/2026-06-04-backlog-002-audit-followup-report.md` under `## Task 2 — Semantic Drift`.

### Task 3: Auditar compatibilidad legacy implementada vs demostrada

**Files:**
- Inspect: `harness/domain/state.py`
- Inspect: `harness/adapters/yaml_repository.py`
- Inspect: `harness/services/state_manager.py`
- Inspect: `harness/services/orchestrator.py`
- Inspect: `harness/adapters/filesystem_action_runner.py`
- Inspect: `docs/MANIFEST_SPEC.md`
- Inspect: `docs/HARNESS_AND_STATE_MACHINE.md`
- Inspect: `docs/STATE_MANAGER_SPEC.md`
- Inspect: `tests/adapters/test_yaml_repository.py`
- Inspect: `tests/harness/test_state_manager.py`
- Inspect: `tests/adapters/test_filesystem_adapters.py`
- Inspect: `tests/harness/test_orchestrator.py`
- Inspect: `tests/harness/test_domain_consistency.py`

**Step 1: Confirmar dónde existe la normalización**

Run:
```bash
rg -n "LEGACY_STAGE_MAP|verified|rendered" \
  harness/domain/state.py \
  harness/adapters/yaml_repository.py \
  harness/services/state_manager.py \
  harness/services/orchestrator.py \
  harness/adapters/filesystem_action_runner.py \
  tests/adapters/test_yaml_repository.py \
  tests/harness/test_state_manager.py \
  tests/adapters/test_filesystem_adapters.py \
  tests/harness/test_orchestrator.py \
  tests/harness/test_domain_consistency.py
```

**Step 2: Confirmar qué está cubierto por tests**

Run:
```bash
.venv/bin/pytest -v \
  tests/adapters/test_yaml_repository.py \
  tests/harness/test_state_manager.py \
  tests/adapters/test_filesystem_adapters.py \
  tests/harness/test_orchestrator.py \
  tests/harness/test_domain_consistency.py
```

Check:
- state legacy load
- state legacy round-trip
- emitted manifest schema/backward-compat evidence on write
- canonical manifest emission

Evidence rule:
- No marcar `passing test exists` hasta tener test name + resultado PASS + mapping al archivo runtime que implementa el comportamiento.

**Step 3: Marcar huecos**

Deliverable:
- matriz `behavior | implementation exists | passing test exists | missing evidence`
- Write it into `docs/plans/2026-06-04-backlog-002-audit-followup-report.md` under `## Task 3 — Legacy Compatibility`.

### Task 4: Auditar coherencia de schema y contratos YAML/manifest

**Files:**
- Inspect: `harness/adapters/yaml_repository.py`
- Inspect: `harness/adapters/filesystem_action_runner.py`
- Inspect: `harness/ports/action_runner.py`
- Inspect: `harness/services/orchestrator.py`
- Inspect: `harness/services/orchestrator_builder.py`
- Inspect: `harness/services/gates.py`
- Inspect: `cli/paper/main.py`
- Inspect: `docs/MANIFEST_SPEC.md`
- Inspect: `docs/ORCHESTRATOR_SPEC.md`
- Inspect: `docs/STATE_MANAGER_SPEC.md`
- Inspect: `docs/HARNESS_AND_STATE_MACHINE.md`
- Inspect: `tests/adapters/test_filesystem_adapters.py`
- Inspect: `tests/harness/test_orchestrator.py`
- Inspect: `tests/harness/test_gates.py`
- Inspect: `tests/cli/test_paper_cli.py`
- Inspect: `tests/harness/mocks.py`

**Step 1: Comparar versiones de schema**

Check:
- `state.yaml` schema comment
- `manifest.yaml` schema version
- runtime-emitted manifest fields from `FilesystemActionRunner.emit_manifest()`
- `ActionRunner.emit_manifest()` port contract
- `paper verify` caller path and gate snapshot passed into manifest emission
- gate snapshot semantics from `harness/services/gates.py`
- whether orchestrator evidence depends on mocks versus real emitter behavior
- docs que hablan de `1.0` / `1.1`

**Step 1b: Capturar artifact real o fixture verificable**

Locator command:
```bash
rg -n "schema_version|stage: rendered|gate_snapshot" tests docs outputs
```

Evidence rule:
- El `rg` anterior sirve SOLO para localizar candidatos; NO cuenta como evidencia por sí solo.
- Antes de usar un fixture/test artifact como evidencia, probar el vínculo con runtime:
  - identificar el test exacto que lo produce o valida
  - identificar el call-site runtime (`FilesystemActionRunner.emit_manifest()` o su caller real) al que ese test está mapeado
  - registrar `artifact path | producing/validating test | runtime path`
- Si no existe artifact runtime-emitted o fixture atado explícitamente al emitter real, marcar `runtime artifact evidence = missing`.

**Step 2: Determinar si es blocker o cleanup**

Rule:
- si rompe lectura/escritura o interpretación = blocker
- si solo miente la doc/comentario = cleanup

**Step 3: Registrar decisión**

Deliverable:
- nota con `contract | current value | expected value | severity`
- Write it into `docs/plans/2026-06-04-backlog-002-audit-followup-report.md` under `## Task 4 — Manifest and Schema Contract`.

### Task 5: Separar bugs de runtime de deuda adyacente

**Files:**
- Inspect: `harness/services/orchestrator.py`
- Inspect: `harness/services/gates.py`
- Inspect: `harness/adapters/filesystem_action_runner.py`
- Inspect: `validators/protocol_generator.py`

**Step 1: Re-ejecutar surface relevante**

Run:
```bash
.venv/bin/pytest tests/harness/test_domain_consistency.py tests/harness/test_state_manager.py tests/adapters/test_yaml_repository.py tests/harness/test_gates.py tests/harness/test_orchestrator.py tests/adapters/test_filesystem_adapters.py tests/cli/test_paper_cli.py tests/e2e/test_smoke_e2e.py -q
.venv/bin/python -m mypy harness/domain/state.py harness/adapters/yaml_repository.py harness/services/state_manager.py harness/services/orchestrator.py harness/services/gates.py harness/adapters/filesystem_action_runner.py validators/protocol_generator.py
```

**Step 2: Triage de resultados**

Buckets:
- `BACKLOG-002 blocker`
- `adjacent debt`
- `pre-existing unrelated`

**Step 3: Probar si el full suite sigue verde (opcional, señal adyacente)**

Run:
```bash
.venv/bin/pytest -q
```

Rule:
- Ejecutar este paso SOLO si el surface focalizado ya quedó clasificado.
- Si el full suite falla, registrar el hallazgo como `adjacent signal` hasta demostrar vínculo con BACKLOG-002.

### Task 6: Cerrar con backlog accionable

**Files:**
- Create/Update: `docs/plans/2026-06-04-backlog-002-audit-followup-report.md`

**Step 1: Consolidar hallazgos**

Sections:
- SDD traceability / artifact-store verdict
- blockers para decir “SDD cerrado”
- fixes chicos de doc/comentarios
- deuda técnica no bloqueante
- fuera de alcance / pre-existing unrelated
- adjacent signal

**Step 2: Priorizar**

Priority rules:
- `P0`: rompe contrato o test principal
- `P1`: evidencia SDD faltante / compat legacy no demostrada
- `P2`: doc drift / comments stale / schema label drift

**Step 3: Definir siguiente movimiento**

Deliverable:
- lista corta de fixes con `owner area | priority | evidence | expected verification`
- Write it into `docs/plans/2026-06-04-backlog-002-audit-followup-report.md` under `## Task 6 — Fix Backlog`.
