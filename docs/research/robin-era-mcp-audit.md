# Robin + ERA MCP audit for paper-writer

## 1. Resumen ejecutivo

Se auditó estáticamente **Robin** (FutureHouse) y **ERA** (Google Research) en un workspace temporal local el **28 de mayo de 2026**.

Conclusión sobria:

- **Robin NO conviene como base técnica** para `paper-writer`.
  - Su valor está en **patrones de orquestación**, **separación por etapas**, **ranking pairwise**, y **persistencia de salidas por carpeta**.
  - Su dependencia fuerte de **Edison / Crow / Falcon / Finch** lo vuelve poco reproducible y poco acoplable para nuestro caso.
- **ERA SÍ aporta una base técnica parcial**, pero **muy acotada**.
  - Lo más útil es el núcleo **FUTS / Flat UCB Tree Search** como patrón genérico de búsqueda sobre candidatos **cuando exista una función de score local y auditable**.
  - NO conviene trasladar ERA al dominio de redacción científica general, porque su fortaleza depende de tareas con **ejecución automática + scoring objetivo**.
- Para `paper-writer`, la recomendación es:
  1. **tomar inspiración metodológica de Robin**;
  2. **reutilizar conceptualmente y quizás parcialmente FUTS de ERA** solo para tareas escorables;
  3. **arrancar con un MCP wrapper liviano sobre el CLI**;
  4. **posponer cualquier loop agéntico profundo** hasta tener claim ledger, evidence map y method gates maduros.

Veredicto final:

| Repo | Fuente conceptual | Base técnica parcial | Inspiración arquitectónica | Acoplamiento recomendado |
|---|---|---:|---:|---|
| Robin | Sí | Bajo | Sí | No directo; solo patrones |
| ERA | Sí | Sí, pero pequeña | Sí | Parcial y condicionado |

---

## 2. Repos clonados y commit hash

Workspace temporal usado: `/_scratch/external_repos/`

| Repositorio | URL | Fecha de clonación | Commit revisado | Licencia |
|---|---|---|---|---|
| Robin | https://github.com/Future-House/robin | 2026-05-28 | `4a5cce310f3bc7663a67117db88af43b84733ffe` | Apache-2.0 |
| ERA | https://github.com/google-research/era | 2026-05-28 | `37637a49fd78139c01a2162f8dc5136087165f93` | Apache-2.0 |

---

## 3. Licencias

Ambos repos están bajo **Apache License 2.0**.

Impacto práctico:

- **Permiten reutilización y adaptación**, con preservación de notices y términos de licencia.
- **No habilitan copiar sin criterio** prompts, assets o salidas completas dentro del repo principal.
- Si en el futuro se reutiliza código, conviene hacerlo como:
  - referencia puntual;
  - módulo aislado;
  - o reimplementación limpia basada en ideas, según el caso.

Riesgo legal actual: **bajo**, siempre que se mantenga separación y trazabilidad.

---

## 4. Estructura técnica de Robin

### 4.1 Objetivo y arquitectura general

Robin es un sistema multiagente para descubrimiento biomédico orientado a:

1. generar assays experimentales;
2. proponer candidatos terapéuticos;
3. opcionalmente incorporar análisis experimental;
4. rankear hipótesis por comparaciones pairwise.

Estructura principal observada:

- `robin/assays.py` — pipeline de generación de assay
- `robin/candidates.py` — pipeline de candidatos terapéuticos
- `robin/analyses.py` — análisis experimental adicional
- `robin/utils.py` — polling, guardado, ranking, parseo
- `robin/configuration.py` — config, prompts, clientes Edison/LLM
- `robin/prompts.py` — prompts y formatos
- `robin_demo.ipynb`, `robin_full.ipynb` — entrada operativa principal
- `examples/` y `examples/example_outputs/` — notebooks y salidas ejemplo

### 4.2 Agentes definidos y dependencias externas

Robin no implementa agentes locales propios. Orquesta **agentes remotos de Edison**.

Dependencias observadas:

- `edison-client>=0.11`
- `fhaviary`
- `fhlmi`
- `openai>=1`
- `anthropic`
- `python-dotenv`
- `pandas`, `pydantic`, `choix`, `aiofiles`, `tqdm`

Agentes visibles en código/config:

- **Crow** — búsqueda/literatura e hipótesis
- **Falcon** — reportes de candidatos
- **Finch / data-analysis path** — mencionado en README como acceso restringido / beta

### 4.3 Flujo de hipótesis

Flujo real detectado en `assays.py` y `candidates.py`:

1. LLM genera queries de literatura.
2. Edison/Crow ejecuta búsquedas por query.
3. LLM sintetiza ideas de assay.
4. Edison/Crow genera reportes detallados por assay.
5. LLM rankea assays por comparaciones pairwise.
6. LLM sintetiza un goal para generación de candidatos.
7. LLM genera queries de literatura para candidatos.
8. Edison/Crow produce revisiones de literatura.
9. LLM propone candidatos terapéuticos.
10. Edison/Falcon genera reportes por candidato.
11. LLM rankea candidatos pairwise.
12. Opcionalmente se incorpora análisis experimental y se reitera.

Esto es una **pipeline secuencial con ranking interno**, NO un sistema tipo wiki/ledger auditable por defecto.

### 4.4 Flujo de búsqueda de literatura

Patrón:

- queries generadas por LLM;
- ejecución remota vía `call_platform(...)`;
- polling por task id;
- recuperación de `answer` y `references`;
- serialización a `.txt` por query.

Fortaleza:

- separa búsqueda, síntesis y ranking.

Debilidad:

- la calidad de evidencia depende de una caja negra externa;
- no hay un **claim ledger** ni un esquema fuerte de evidencia estructurada.

### 4.5 Flujo de análisis de datos

`robin/analyses.py` implementa un pipeline multi-step con `MultiTrajectoryRunner`:

- step 1: análisis R sobre datos experimentales;
- step 2: consenso / análisis agregado;
- luego LLM interpreta HTML derivado de CSV;
- finalmente propone follow-ups.

Esto depende de runtime remoto Edison y de jobs específicos (`job-futurehouse-data-analysis-crow-high`).

### 4.6 Notebooks disponibles

- `robin_demo.ipynb` — 11 celdas, 4 de código, 7 markdown
- `robin_full.ipynb` — 16 celdas, 7 de código, 9 markdown
- `examples/*.ipynb` — notebooks por enfermedad, 9 celdas típicamente

Patrón útil:

- notebooks como interfaz de operador;
- pipeline explícita por etapas;
- ejemplos de salidas ya persistidas.

### 4.7 Prompts / configs

Puntos relevantes:

- `Prompts` en `configuration.py` valida placeholders esperados con Pydantic.
- `prompts.py` define contratos de salida relativamente explícitos:
  - queries separadas por `<>`;
  - propuestas de assay en JSON array;
  - candidatos con marcadores `<CANDIDATE START>` / `<CANDIDATE END>`;
  - ranking en JSON con `Winner` y `Loser`.

Esto es BUENO como patrón: **prompt con schema textual explícito + validación previa de placeholders**.

### 4.8 Entrada / salida

Entrada principal:

- `disease_name`
- parámetros numéricos (`num_queries`, `num_assays`, `num_candidates`)
- opcionalmente datos experimentales
- API keys externas

Salida principal:

- carpeta `robin_output/<disease>_<timestamp>/`
- `.txt` de revisiones y reportes
- `.csv` de ranking
- `.txt` de resúmenes
- links a trayectorias Edison

### 4.9 Persistencia, logging y trazabilidad

Persistencia:

- bastante simple y útil para auditoría humana;
- basada en carpetas y archivos texto/csv;
- naming legible.

Logging:

- abundante `logger.info/warning/error`;
- NO hay logging estructurado ni event schema consistente.

Trazabilidad:

- parcial;
- guarda query, answer, references y link remoto de trayectoria;
- NO guarda una representación fuerte de claim -> evidence -> decision.

### 4.10 Qué requiere credenciales y qué no

**Requiere credenciales / servicios externos**

- Edison platform para Crow/Falcon/Finch
- `EDISON_API_KEY`
- proveedor LLM vía LiteLLM, por defecto `OPENAI_API_KEY`

**Ejecutable sin credenciales, de forma parcial**

- inspección de notebooks
- lectura de prompts/configs
- revisión de ejemplos/salidas ya comiteadas
- análisis de utilidades de ranking y persistencia

**No viable localmente sin terceros**

- pipeline completa de assay/candidate generation
- data analysis remota
- validación de calidad real del loop multiagente

### 4.11 Límites de reproducibilidad

Principales límites:

1. dependencia dura de agentes remotos;
2. costo variable por API/credits;
3. versiones de modelos externas no fijadas de manera reproducible;
4. salida dependiente de prompts largos y respuestas no deterministas;
5. evidencia no estructurada para reauditoría automática;
6. parte del análisis experimental restringida/beta.

### 4.12 Hallazgos de Robin clasificados

| Hallazgo | Clasificación | Por qué |
|---|---|---|
| Validación de placeholders de prompts (`Prompts`) | **Adaptable con trabajo moderado** | Útil para contratos de prompts MCP/CLI; el patrón es bueno y pequeño |
| Persistencia por carpeta con artefactos legibles (`txt/csv`) | **Adaptable con trabajo moderado** | Compatible con auditoría humana, pero falta esquema fuerte |
| Ranking pairwise + agregación de scores (`choix`) | **Adaptable con trabajo moderado** | Sirve para rankear hipótesis/críticas, no para copiar el dominio biomédico |
| Secuencia literature -> proposal -> detailed review -> ranking | **Solo inspiracional** | Patrón valioso, pero demasiado acoplado a terapéutica y Edison |
| Generación de hipótesis terapéuticas | **No recomendable** | Desalineado con paper-writer; alto riesgo de sobrealcance biomédico |
| Análisis experimental remoto con Edison/Finch | **Requiere dependencia externa no viable** | No reproducible localmente; beta/cerrado |
| Uso de Crow/Falcon como fuentes de evidencia | **No recomendable** | Caja negra externa; poca auditabilidad para nuestro objetivo |
| Ejemplos de output comiteado | **Solo inspiracional** | Útiles para formato de artefactos, no como datos base |
| Reutilización de código Robin dentro del repo principal | **Requiere revisión legal/licencia** | Apache permite, pero conviene mínima extracción y notices si hubiera copia |

### 4.13 Recomendación sobre Robin

**NO usar Robin como base del producto.**

Sí conviene rescatar:

- contratos de salida bien definidos;
- ranking pairwise;
- carpetas de artefactos por corrida;
- separación por etapas.

No conviene acoplar:

- Edison;
- sus agentes remotos;
- su loop biomédico de descubrimiento.

---

## 5. Estructura técnica de ERA

### 5.1 Objetivo del sistema

ERA busca ayudar a científicos a producir **software empírico experto**. Su centro no es la escritura académica sino la **búsqueda de programas que maximizan una métrica objetiva**.

### 5.2 Arquitectura general

Núcleo observado:

- `implementation/futs.py` — algoritmo Flat UCB Tree Search
- `implementation/llm.py` — wrapper LLM (Gemini)
- `implementation/playground_s3e1.py` — ejemplo end-to-end sobre regresión
- `implementation/sandbox.py` — contrato abstracto para ejecutar código no confiable
- `implementation/futs_test.py` — tests del núcleo FUTS
- `implementation/notebooks/*.ipynb` — tareas benchmark con celdas mutables y scoring
- `docs/` — páginas HTML de estudios y miles de diffs
- `era_applications/` — papers/casos de uso

### 5.3 Uso de LLM

ERA usa LLM para **generar código candidato**. El scoring no lo hace el LLM: lo hace una función ejecutable local/sandbox.

Patrón central:

- LLM propone código nuevo;
- sandbox lo ejecuta;
- una métrica devuelve score;
- FUTS decide qué nodo expandir después.

Eso es importante: **ERA funciona cuando hay un evaluador objetivo**.

### 5.4 Tree search / planificación

`futs.py` implementa un árbol plano con PUCT:

- nodos con `solution`, `score`, `num_visits`, `rank_score`, `puct`;
- selección del mejor nodo por `puct`;
- expansión con `generate_fn`;
- ejecución con `execute_fn`;
- backpropagation de visitas.

Valor real para nosotros:

- el núcleo es **pequeño, comprensible y auditable**;
- separa muy bien generación de evaluación.

Limitación:

- si no existe `execute_fn` confiable, el algoritmo pierde sentido.

### 5.5 Asistencia empírica y generación/evaluación de código científico

ERA está mucho más cerca de:

- generar scripts de análisis;
- optimizar pipelines reproducibles;
- iterar sobre modelos o métodos;
- comparar salidas por score.

Esto lo vuelve más alineado con:

- `paper_hypothesis_generate` solo si hay scoring fuerte;
- `paper_method_gate` cuando el output sea estructurado;
- `paper_repro_audit` sobre scripts o notebooks;
- asistencia para anexos computacionales, no para narrativa libre.

### 5.6 Manejo de experimentos

Se observaron dos capas:

1. **reference implementation** pequeña (`implementation/`)
2. **artifact layer** grande (`docs/`) con páginas de estudio y diffs

Dato relevante:

- `docs/` contiene **6 study pages** y **6541 diff pages**.

Eso es interesante como patrón de trazabilidad visual de evolución de soluciones.

### 5.7 Prompts / configs

ERA es mucho más minimalista que Robin:

- prompt hardcodeado en `llm.py` para “expert Data Scientist and Python programmer”;
- prompt específico en `playground_s3e1.py` con restricciones de librerías y tiempo;
- notebooks benchmark con delimitadores `# Begin mutable cells` / `# End mutable cells`.

Patrón útil:

- **task notebook con región mutable + celdas de validación**.

### 5.8 Tests y ejemplos

Tests locales observados:

- `implementation/futs_test.py`

Resultado de verificación mínima:

- el test **no corrió** por dependencia faltante `absl` (`ModuleNotFoundError: No module named 'absl'`).

Eso muestra una debilidad de reproducibilidad: el README declara instalación mínima con `pandas numpy scikit-learn google-generativeai`, pero el test requiere algo más.

### 5.9 Problemas concretos detectados

Hallazgos técnicos importantes:

1. **Inconsistencia de API key**
   - README dice `GOOGLE_API_KEY`
   - `playground_s3e1.py` y `experiment_pipeline.ipynb` usan `GEMINI_API_KEY`

2. **Sandbox incompleto en el ejemplo de implementación**
   - `implementation/sandbox.py` solo define una interfaz abstracta.
   - `playground_s3e1.py` intenta usar `Sandbox(timeout_seconds=60)` como si hubiera implementación concreta.
   - No se encontró `ExecSandbox` en código Python del repo; el notebook la importa pero no está implementada en el árbol inspeccionado.

3. **Modelo default llamativo**
   - `llm.py` usa por defecto `gemini-2.5-flash-image`, raro para generación de código.
   - Esto requiere revisión antes de tomarlo como referencia técnica.

### 5.10 Qué requiere credenciales y qué no

**Requiere credenciales / recursos externos**

- Gemini API key
- datasets Kaggle / datasets externos
- runtime capaz de ejecutar código generado

**Ejecutable sin credenciales, de forma parcial**

- `futs.py`
- `futs_test.py` si se satisfacen dependencias locales
- lectura de notebooks benchmark
- inspección de `docs/` y aplicaciones

### 5.11 Límites de reproducibilidad

1. ejemplo end-to-end incompleto por sandbox faltante;
2. mismatch de variable de entorno para API key;
3. datasets externos no incluidos plenamente para reejecución universal;
4. tests no documentan todas las dependencias;
5. utilidad muy condicionada a tasks con scoring objetivo.

### 5.12 Hallazgos de ERA clasificados

| Hallazgo | Clasificación | Por qué |
|---|---|---|
| `implementation/futs.py` | **Reutilizable directamente** | Núcleo pequeño, genérico, Apache, auditable |
| Contrato `generate_fn` / `execute_fn` | **Reutilizable directamente** | Excelente separación para tareas escorables |
| Notebooks con `Begin mutable cells` y scoring | **Adaptable con trabajo moderado** | Muy útil para tareas metodológicas o anexos computacionales |
| HTML studies + diff pages | **Adaptable con trabajo moderado** | Buen patrón de trazabilidad de iteraciones |
| `llm.py` wrapper Gemini | **Solo inspiracional** | Muy específico y con defaults dudosos |
| Ejemplo `playground_s3e1.py` | **No recomendable** | Inconsistencia de API key + sandbox no implementado |
| Benchmark notebooks científicos | **Solo inspiracional** | Útiles como formato de task, no como base directa del CLI |
| Aplicaciones en `era_applications/` | **Solo inspiracional** | Muestran alcance, no una superficie integrable |
| Reutilización de ERA dentro del repo principal | **Requiere revisión legal/licencia** | Apache permite, pero conviene extracción mínima y notices |
| Ejecución full local del ejemplo | **Requiere dependencia externa no viable** | API key + datasets + sandbox concreto |

### 5.13 Recomendación sobre ERA

**Sí conviene usar ERA como referencia técnica parcial**, pero SOLO en esta forma:

- tomar **FUTS** como patrón o base pequeña;
- usar el modelo `generate/evaluate/search` donde exista un score fuerte;
- usar notebooks benchmark como inspiración para evaluaciones controladas.

No conviene:

- copiar el ejemplo de playground tal cual;
- convertir `paper-writer` en un generador general de código científico sin gates;
- usar tree search para prosa libre.

---

## 6. Comparación Robin vs ERA

| Dimensión | Robin | ERA | Utilidad para paper-writer CLI | Utilidad para wiki metodológica | Riesgo | Recomendación |
|---|---|---|---|---|---|---|
| Propósito | Descubrimiento terapéutico multiagente | Optimización de software empírico | ERA gana en tareas escorables; Robin gana en pipeline editorial | Robin aporta mejor secuencia de artefactos | Medio | Tomar ideas de ambos, no producto completo |
| Madurez técnica | Pipeline real, pero muy dependiente de servicios remotos | Núcleo pequeño y claro; ejemplo E2E incompleto | ERA es más auditable | Ambos sirven como referencia | Medio | Preferir piezas pequeñas |
| Reproducibilidad local | Baja | Media-baja | ERA parcialmente mejor | Robin baja por Edison | Alto | No depender de ejecución plena |
| Dependencia de API keys | Alta (`EDISON_API_KEY`, LLM key) | Alta (Gemini key) | Ambas limitan CI/local | Ambas limitan wiki reproducible | Alto | Diseñar modo local-first |
| Arquitectura agéntica | Fuerte, remota, por etapas | No realmente multiagente; search sobre soluciones | Robin inspira orquestación | Robin inspira ledger por etapas | Medio | No replicar profundidad agéntica inicial |
| Análisis de literatura | Sí, pero vía Edison | No es el foco | Robin inspira interfaces | Robin puede informar evidence map | Alto | Inspiración, no acoplamiento directo |
| Análisis de datos | Sí, con runners remotos y R | Sí, vía código generado y scoring | ERA es mejor para anexos computacionales | Robin aporta follow-up framing | Alto | Acotar dominio antes de integrar |
| Generación de hipótesis | Sí, biomédica | Indirecta, como búsqueda de programas | Robin inspira `hypothesis_generate` | Robin útil como referencia conceptual | Alto | No automatizar sin gates |
| Validación / crítica | Ranking pairwise con LLM | Scoring objetivo por executor | ERA es mejor cuando hay métrica | Robin mejor para crítica textual inspiracional | Medio | Combinar score + crítica estructurada |
| Trazabilidad | Archivos txt/csv + links Edison | diffs HTML + study pages + JSON de progreso | ERA aporta mejor historial de iteración | Robin aporta mejor artefacto por etapa | Medio | Adoptar trazabilidad propia |
| Facilidad de acoplamiento MCP | Baja | Media | ERA mejor para tools puntuales | Robin mejor como inspiración de prompts | Medio | MCP wrapper propio |
| Licencia | Apache-2.0 | Apache-2.0 | Ambas compatibles | Ambas compatibles | Bajo | Sin bloqueo legal aparente |
| Riesgo de sobreingeniería | Muy alto si se replica el loop completo | Alto si se usa tree search donde no aplica | Alto | Alto | Alto | Empezar simple |

---

## 7. Componentes reutilizables / adaptables / inspiracionales

### 7.1 Reutilizable directamente

1. **ERA / `implementation/futs.py`**
   - Uso posible: ranking/búsqueda de scripts metodológicos o planes escorables.
   - Condición: debe existir `execute_fn` local y auditable.

2. **ERA / contrato `generate_fn` + `execute_fn`**
   - Uso posible: separar claramente generación de evaluación en futuras herramientas.

### 7.2 Adaptable con trabajo moderado

1. **Robin / validación de placeholders de prompts**
2. **Robin / ranking pairwise + score aggregation**
3. **Robin / carpeta de artefactos por corrida**
4. **ERA / notebooks con región mutable y evaluación explícita**
5. **ERA / páginas de diff como trazabilidad de iteración**

### 7.3 Solo inspiracional

1. Robin / pipeline literature -> proposal -> review -> ranking
2. Robin / idea de consenso entre agentes y follow-up experimental
3. ERA / framing de “expert empirical software” y benchmark notebooks
4. ERA / showcase de estudios y diffs navegables

### 7.4 No recomendable

1. Robin / dependencia directa de Edison como backend del sistema
2. Robin / generación biomédica de candidatos terapéuticos dentro de paper-writer
3. ERA / ejemplo `playground_s3e1.py` como base operativa
4. ERA / aplicar tree search a prosa libre sin scoring fuerte

---

## 8. Oportunidades MCP

La recomendación es que las primeras tools MCP NO hablen con Robin ni ERA directamente. Deben hablar con **nuestro CLI y nuestros artefactos locales**.

### 8.1 MCP tools candidatas

| Tool | Propósito | Entrada | Salida | Inspiración | Dependencia externa | Riesgo | Complejidad | Prioridad | Primero |
|---|---|---|---|---|---|---|---|---|---|
| `paper_claim_audit` | extraer claims y clasificarlos | markdown, manuscript_type, reporting_guide | claims, tipo, evidencia requerida, riesgo | Propio + Robin | No obligatoria | Medio | Baja | P0 | CLI |
| `paper_evidence_map` | mapear papers a claims y outcomes | papers, research_question, PICO/SPIDER | matriz estructurada | Robin | No obligatoria | Medio | Media | P0 | CLI |
| `paper_reviewer2` | crítica dura pre-envío | manuscript, journal, study_type | debilidades, overclaims, bloqueadores | Robin | No obligatoria | Alto si no se acota | Baja | P0 | CLI |
| `paper_method_gate` | gate metodológico fail-closed | protocol/manuscript, checklist | pass/fail, razones, blockers | Propio | No obligatoria | Bajo | Baja | P0 | CLI |
| `paper_reference_verify` | verificar referencias/claims | refs, claims | DOI/PMID hallados, refs sospechosas | Propio | Puede requerir APIs/bases en futuro | Medio | Media | P1 | CLI |
| `paper_wiki_sync` | proponer sync con wiki/ledger | audit findings, wiki path, claim ledger | diff propuesto | Robin + propio | No obligatoria | Medio | Media | P1 | MCP |
| `paper_hypothesis_generate` | generar hipótesis con restricciones | domain, corpus, constraints | hipótesis, testabilidad, evidencia requerida | Robin + ERA + propio | No obligatoria al inicio | Alto | Media | P1 | CLI |
| `paper_experiment_plan` | bosquejar experimento/analysis plan escorable | hypothesis, data constraints, outcome metric | plan, scoreability, risks | ERA | No obligatoria | Medio | Media | P1 | CLI |
| `paper_repro_audit` | auditar anexos computacionales | notebook/script, dataset contract | reproducibility report | ERA | Puede requerir sandbox local | Medio | Alta | P2 | CLI |

> El detalle preliminar de schemas quedó en `docs/research/mcp-tools-candidates.md`.

### 8.2 MCP resources candidatos

| Resource | Contenido | Prioridad |
|---|---|---|
| `paper://claim-ledger/current` | ledger estructurado de claims y estado de soporte | P0 |
| `paper://evidence-maps/{topic}` | matrices claim-evidence por tema | P0 |
| `paper://reporting-checklists/{study_type}` | CONSORT/STROBE/PRISMA/etc. normalizados | P0 |
| `paper://journals/{journal}` | scope, article types, constraints editoriales | P1 |
| `paper://model-corpus/{domain}` | corpus de papers modelo/anotados | P1 |
| `paper://audit-runs/{run_id}` | logs y resultados de auditorías previas | P1 |
| `paper://method-wiki/{page}` | páginas de wiki metodológica | P1 |

### 8.3 Prompt contracts candidatos

| Prompt contract | Propósito | Notas |
|---|---|---|
| `claim-audit/strict` | extraer claims sin expandir contenido | Debe ser fail-closed y marcar incertidumbre |
| `reviewer2/hostile` | crítica severa pero justificada | Inspiración Robin en evaluación comparativa |
| `method-gate/checklist-bound` | evaluar contra checklist concreta | Sin creatividad gratuita |
| `hypothesis-generate/constrained` | generar hipótesis con límites explícitos | Separar hipótesis de evidencia |
| `reference-verify/no-fabrication` | verificar citas sin inventar metadata | Regla crítica |

---

## 9. Arquitecturas de acoplamiento

| Alternativa | Descripción | Complejidad | Mantenibilidad | Riesgo de drift | Dependencia de terceros | Seguridad | Reproducibilidad | Valor inmediato | Compatibilidad wiki | Compatibilidad CLI | Recomendación |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **A. MCP wrapper liviano sobre `paper` CLI** | MCP traduce tools a comandos/subcomandos propios | Baja | Alta | Baja | Baja | Alta | Alta | Alta | Alta | Alta | **RECOMENDADA** |
| **B. Sidecar MCP independiente** | servidor MCP separado lee wiki, corpus y ledger | Media | Media | Media | Media | Media | Media | Media | Alta | Media | Recomendable en segunda etapa |
| **C. Integración profunda tipo Robin/ERA** | loops agénticos, búsqueda, evaluación y herramientas múltiples | Alta | Baja | Alta | Alta | Baja-media | Baja | Baja al inicio | Media | Media | **NO recomendada para v1** |

### Recomendación de arquitectura

Elegir **A** ahora.

Razón:

- preserva el CLI como fuente de verdad;
- mantiene logs y gates donde ya existen;
- evita meter estados paralelos desde el día uno;
- permite exponer solo herramientas estables.

---

## 10. Roadmap para paper-writer CLI

### Fase 0 — Solo auditoría local

**Objetivo**

Agregar auditoría local de claims, prosa y método sin depender de búsquedas externas.

**Comandos CLI propuestos**

- `paper audit claims`
- `paper audit prose`
- `paper gate method`

**Tools MCP**

- `paper_claim_audit`
- `paper_reviewer2`
- `paper_method_gate`

**Archivos afectados**

- `cli/paper/main.py`
- `harness/services/orchestrator.py`
- `validators/`
- `integrations/tools/`
- `docs/`

**Riesgos**

- scope creep de NLP;
- confundir lint con auditoría metodológica.

**Criterios de aceptación**

- outputs determinísticos o casi determinísticos;
- reporte legible por claim;
- gate metodológico fail-closed.

### Fase 1 — Evidence mapping

**Objetivo**

Ingestar papers y generar matriz estructurada de evidencia conectada a claims.

**Comandos CLI propuestos**

- `paper ingest papers`
- `paper extract evidence`
- `paper map evidence`
- `paper sync claim-ledger`

**Tools MCP**

- `paper_evidence_map`
- `paper_reference_verify`
- `paper_wiki_sync`

**Archivos afectados**

- `integrations/tools/`
- `harness/domain/` o equivalente para ledger
- `outputs/`
- `docs/research/`

**Riesgos**

- extracción inconsistente;
- referencias parcialmente alucinadas si no hay verificación.

**Criterios de aceptación**

- cada claim puede apuntar a evidencia concreta;
- existe matriz reproducible paper -> diseño -> outcome -> hallazgo -> limitación.

### Fase 2 — MCP wrapper

**Objetivo**

Exponer las herramientas estables del CLI vía MCP.

**Comandos CLI propuestos**

- `paper mcp serve`
- `paper audit claims --json`
- `paper map evidence --json`

**Tools MCP**

- P0 y P1 estables

**Archivos afectados**

- nuevo módulo `integrations/mcp/` o `mcp_server/`
- adapters CLI/JSON
- docs operativas

**Riesgos**

- drift entre CLI y MCP si ambos resuelven lógica.

**Criterios de aceptación**

- MCP delega al CLI o a servicios internos comunes;
- logs y schemas estables;
- cero duplicación innecesaria de reglas.

### Fase 3 — Hipótesis asistida

**Objetivo**

Generar hipótesis y criticarlas con constraints metodológicos.

**Comandos CLI propuestos**

- `paper hypothesis generate`
- `paper hypothesis critique`
- `paper hypothesis rank`

**Tools MCP**

- `paper_hypothesis_generate`
- `paper_reviewer2`
- `paper_experiment_plan`

**Archivos afectados**

- prompts/contracts
- validators metodológicos
- claim ledger / evidence map

**Riesgos**

- confundir ideación con evidencia;
- sobreclaim automático.

**Criterios de aceptación**

- toda hipótesis sale con evidencia requerida, testabilidad y riesgos;
- no hay “paper magic”.

### Fase 4 — Loop avanzado

**Objetivo**

Explorar un loop inspirado en Robin/ERA SOLO sobre tareas con datos estructurados y scoring claro.

**Comandos CLI propuestos**

- `paper loop run`
- `paper loop score`
- `paper repro audit`

**Tools MCP**

- `paper_repro_audit`
- `paper_experiment_plan`

**Archivos afectados**

- sandbox local
- módulo de scoring
- trazabilidad de iteraciones

**Riesgos**

- sobreingeniería;
- inseguridad al ejecutar código;
- uso indebido en dominios biomédicos.

**Criterios de aceptación**

- solo corre sobre outputs scorable;
- logs completos de generación/evaluación;
- sin decisiones clínicas automáticas.

---

## 11. Riesgos y límites

### Seguridad y gobernanza obligatoria

- **Riesgos de ejecutar código externo**
  - ERA empuja naturalmente a ejecutar código generado. Eso exige sandbox serio, límites de tiempo, FS/network policy y revisión humana.
- **Licencias**
  - Apache-2.0 permite reutilización, pero cualquier copia debe preservar notices.
- **API keys**
  - no deben vivir en repo, outputs ni notebooks versionados.
- **Datos sensibles**
  - no mezclar manuscritos no publicados ni datos clínicos con servicios externos sin política explícita.
- **Alucinación de referencias**
  - cualquier tool de referencias debe operar fail-closed.
- **Uso de IA en investigación**
  - la IA puede asistir; no debe constituir autoridad epistemológica.
- **Trazabilidad**
  - cada claim, crítica y recomendación debe quedar ligada a evidencia o quedar marcada como hipótesis.
- **Humano en el loop**
  - obligatorio para aprobar claims, evidencias, journal fit y method gates.
- **Límites biomédicos**
  - no automatizar recomendaciones terapéuticas, diagnósticas ni clínicas.
- **Separación entre hipótesis y evidencia**
  - regla dura: una hipótesis generada jamás debe mostrarse como evidencia existente.

### Qué NO conviene acoplar

- Robin como backend remoto del sistema.
- Crow/Falcon/Finch como fuente primaria de evidencia.
- El loop completo de Robin para candidates terapéuticos.
- El ejemplo `playground_s3e1.py` de ERA como si fuera “reference implementation” confiable.
- Tree search sobre prosa libre, reviewer comments o journal selection sin score objetivo.

---

## 12. Recomendación final

Recomendación accionable:

1. **No acoplar Robin directamente.**
2. **Extraer de Robin solo patrones pequeños:**
   - staged artifacts;
   - pairwise ranking;
   - prompt contracts con outputs delimitados.
3. **Tomar de ERA solo la pieza pequeña y fuerte:**
   - FUTS / `generate_fn` + `execute_fn` para futuras tareas escorables.
4. **Construir primero un MCP wrapper del CLI propio.**
5. **Crear antes claim ledger + evidence map + method gate**; recién después evaluar loops avanzados.

En términos del criterio de éxito pedido:

- **Robin** sirve como **fuente conceptual** e **inspiración arquitectónica**, pero **NO** como base técnica parcial recomendable.
- **ERA** sirve como **fuente conceptual**, **inspiración arquitectónica** y **base técnica parcial pequeña**.

---

## 13. Próximos pasos

1. Diseñar el **schema del claim ledger** y del **evidence map**.
2. Implementar en el CLI la **Fase 0**: `claim-audit`, `prose-audit`, `method-gate`.
3. Diseñar el **MCP wrapper liviano** sobre esos comandos, sin agentes profundos todavía.

---

## 14. Apéndice — comandos ejecutados

Comandos seguros usados durante la auditoría (resumen):

```bash
# Localización del repo objetivo
pwd
ls -1
find . -maxdepth 2 -type d \( -name '*paper*' -o -name 'developer*' -o -name 'wiki' -o -name 'docs' \)

git -C /Users/felipe_gonzalez/Developer/paper-writer rev-parse --show-toplevel
find /Users/felipe_gonzalez/Developer/paper-writer -maxdepth 2 -type d \( -name docs -o -name wiki -o -name _scratch \)

# Preparación y clonación superficial
mkdir -p /Users/felipe_gonzalez/Developer/paper-writer/_scratch/external_repos
cd /Users/felipe_gonzalez/Developer/paper-writer/_scratch/external_repos
git clone --depth 1 https://github.com/Future-House/robin.git
git clone --depth 1 https://github.com/google-research/era.git

# Verificación de commits
cd .../robin && git rev-parse HEAD
cd .../era && git rev-parse HEAD

# Lectura estática Robin
find .../robin -maxdepth 2
sed -n '1,260p' README.md
sed -n '1,160p' LICENSE
sed -n '1,240p' pyproject.toml
sed -n '1,240p' robin/configuration.py
sed -n '1,260p' robin/prompts.py
sed -n '1,260p' robin/analyses.py
sed -n '1,280p' robin/assays.py
sed -n '1,340p' robin/candidates.py
sed -n '1,980p' robin/utils.py
rg -n 'API_KEY|EDISON|OPENAI|litellm|dotenv|os.getenv|environ' ...
python3 (lectura JSON de notebooks para contar celdas)

# Lectura estática ERA
find .../era -maxdepth 2
sed -n '1,260p' README.md
sed -n '1,260p' implementation/README.md
sed -n '1,260p' era_applications/README.md
sed -n '1,260p' implementation/futs.py
sed -n '1,260p' implementation/llm.py
sed -n '1,260p' implementation/playground_s3e1.py
sed -n '1,260p' implementation/sandbox.py
sed -n '1,260p' implementation/futs_test.py
sed -n '1,260p' implementation/notebooks/README.md
rg -n 'GOOGLE_API_KEY|GEMINI_API_KEY|genai|sandbox|score|PUCT|tree|diff|study|html|results|json|Kaggle|notebook|test' ...
python3 (conteo de notebooks y diff pages)

# Verificación mínima de tests locales ERA
pytest /Users/felipe_gonzalez/Developer/paper-writer/_scratch/external_repos/era/implementation/futs_test.py -q
# Resultado: error por dependencia faltante 'absl'

# Verificación de wiki local
test -d /Users/felipe_gonzalez/Developer/paper-writer/wiki
```

### Archivos principales inspeccionados

- `/_scratch/external_repos/robin/README.md`
- `/_scratch/external_repos/robin/pyproject.toml`
- `/_scratch/external_repos/robin/robin/configuration.py`
- `/_scratch/external_repos/robin/robin/prompts.py`
- `/_scratch/external_repos/robin/robin/assays.py`
- `/_scratch/external_repos/robin/robin/candidates.py`
- `/_scratch/external_repos/robin/robin/analyses.py`
- `/_scratch/external_repos/robin/robin/utils.py`
- `/_scratch/external_repos/era/README.md`
- `/_scratch/external_repos/era/implementation/README.md`
- `/_scratch/external_repos/era/implementation/futs.py`
- `/_scratch/external_repos/era/implementation/llm.py`
- `/_scratch/external_repos/era/implementation/playground_s3e1.py`
- `/_scratch/external_repos/era/implementation/sandbox.py`
- `/_scratch/external_repos/era/implementation/futs_test.py`
- `/_scratch/external_repos/era/implementation/notebooks/README.md`
- `/_scratch/external_repos/era/docs/index.html`

### Nota sobre la wiki

No se actualizó `wiki/24_IA_AGENTICA_EN_INVESTIGACION_CIENTIFICA.md` porque **no existe un directorio `wiki/` en el repo actual**.
La recomendación quedó documentada en este reporte.
