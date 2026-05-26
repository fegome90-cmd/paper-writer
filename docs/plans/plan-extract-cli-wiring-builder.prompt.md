## Plan: Extract CLI Wiring Builder

Move dependency wiring out of the CLI entrypoint into a dedicated builder so [cli/paper/main.py](cli/paper/main.py) becomes orchestration-only, easier to test, and less coupled to concrete adapter construction.

**Steps**
1. Define target boundary and contract for wiring extraction.
Dependency: none.
Action: introduce an explicit constructor API with typed return container and explicit input boundary:
- Signature target: build_orchestrator_dependencies(project_root: Path | None = None)
- Rule: if project_root is None, resolve Path.cwd(); tests pass tmp_path explicitly.
- Return contract: a frozen dataclass container **without** the Orchestrator itself. The CLI constructs the Orchestrator from the returned dependencies.
<!-- Fix: C-001 — explicit return container type definition -->
- Explicit return type:
  ```python
  @dataclass(frozen=True)
  class OrchestratorDependencies:
      repo_path: Path
      state_manager: StateManager
      checker: ArtifactChecker
      action_runner: ActionRunner
      wrappers: dict[str, ToolWrapper]
      skill_adapters: dict[str, SkillAdapter]
  ```
  <!-- Fix: C-1 — wrappers type corrected to dict[str, ToolWrapper] (not SkillAdapter); verified from Orchestrator.__init__ signature (harness/services/orchestrator.py:61) -->
  <!-- Fix: C-2 — removed phantom `repository: PaperRepository` field; YamlFileStateRepository is an internal construction detail inside the builder, not a dependency the CLI needs -->
  <!-- Fix: C-3 — added repo_path: Path; constructor call is Orchestrator(deps.repo_path, deps.state_manager, deps.checker, deps.action_runner, deps.wrappers) matching the 5-arg signature -->
  <!-- Fix: C-4 — checker type corrected to ArtifactChecker (the actual port ABC in harness/ports/artifact_checker.py); PaperChecker does not exist -->
  <!-- Fix: W-7 — added skill_adapters: dict[str, SkillAdapter]; FilesystemActionRunner needs skill_adapters separately from wrappers, both must be in the container -->
  NOTE: `skill_adapters` is consumed internally by the builder when constructing `FilesystemActionRunner`. It is NOT passed to `Orchestrator.__init__`. The field is exposed for test injection only.
<!-- Fix: H-001 — builder returns dependencies only, not the Orchestrator -->
- Concept rename: this is a "dependency assembler," not a "wiring builder that returns everything." The builder assembles dependencies; the CLI constructs `Orchestrator(deps.repo_path, deps.state_manager, deps.checker, deps.action_runner, deps.wrappers)` from the returned container.

2. Create a new builder module in harness services.
Dependency: step 1.
<!-- Fix: M-002 — lock the filename explicitly -->
Action: create `harness/services/orchestrator_builder.py` with construction functions for repository, state manager, checker, action runner, wrappers, and skill adapters. The module exports `OrchestratorDependencies` and `build_orchestrator_dependencies()`.
<!-- Fix: W-8 — removed "pure"; these constructors have side effects (tool availability checks, path resolution). Use "construction functions" or "factory functions" instead. -->
<!-- Fix: M-003 — error propagation strategy -->
Constraint: builder lets construction errors propagate naturally (e.g., missing config, invalid paths). Callers (CLI, tests) handle exceptions — the builder does not catch or wrap.
<!-- Fix: M-004 — optional skill_adapters parameter -->
API detail: `build_orchestrator_dependencies(project_root: Path | None = None, skill_adapters: dict[str, SkillAdapter] | None = None) -> OrchestratorDependencies`. When `skill_adapters` is None, create defaults (LiteratureSearchAdapter, AcademicWriterAdapter). Tests can pass their own.
<!-- Fix: L-003 — __init__.py note -->
Note: update `harness/services/__init__.py` if re-exports are desired, otherwise import directly from `orchestrator_builder` module.
Parallel note: implementation can proceed in parallel with drafting tests in step 4 once the API signature is fixed.

3. Refactor CLI main to consume the builder.
Dependency: step 2.
Action: replace inline wiring block in [cli/paper/main.py](cli/paper/main.py) with one call to the new builder, then construct `Orchestrator` from the returned `OrchestratorDependencies`.
<!-- Fix: S-11 — explicit import migration checklist -->
Import removals from main.py:
- `YamlFileStateRepository` (from harness.adapters.yaml_repository)
- `StateManager` (from harness.services.state_manager)
- `FilesystemArtifactChecker` (from harness.adapters.filesystem_artifact_checker)
- `FilesystemActionRunner` (from harness.adapters.filesystem_action_runner)
- All tool wrapper imports: `BibliographyNormalizer`, `PandocRenderer`, `RefsMetadataValidator`, `RefsValidator`, `ReportingAuditor`, `StyleLinter`, `ZoteroImporter` (from integrations.tools)
- All skill adapter imports: `AcademicWriterAdapter`, `LiteratureSearchAdapter` (from skills.local.adapters)
Import additions to main.py:
- `build_orchestrator_dependencies`, `OrchestratorDependencies` (from harness.services.orchestrator_builder)
Imports that REMAIN in main.py (do NOT remove):
- `Orchestrator` from `harness.services.orchestrator` — still needed to construct from deps
- `OrchestratorRequest` from `harness.services.orchestrator` — used for request construction
- `OrchestratorResult` from `harness.services.orchestrator` — used in `_print_summary` signature
<!-- Fix: H-004 — resolve cwd dual-resolution -->
Constraint: resolve `repo_path = project_root or Path.cwd()` **once** in main.py, then pass to both `build_orchestrator_dependencies(repo_path)` and the request context `{"cwd": str(repo_path)}`. This prevents dual-resolution under test monkeypatching.
<!-- Fix: W-6 — the single cwd resolution guarantee applies only to the orchestrator flow. The doctor branch retains its own `Path.cwd()` call (main.py line 158) because it exits before the builder is invoked. This is intentional and out of scope. -->
Constraint: keep current behavior unchanged for all commands including doctor branch.

4. Add/adjust tests for wiring extraction contract.
Dependency: steps 2 and 3.
Action: add focused unit tests for builder outputs and update existing CLI mapping tests only if import paths/monkeypatch targets change.
Parallel note: split into three sub-phases for consistency:
- 4a (after step 2): draft builder contract tests and wrappers/adapters mapping tests.
<!-- Fix: H-003 — monkeypatch migration path -->
- 4b (after step 3): align tests to final CLI integration paths. Existing CLI mapping tests continue patching `cli_main.Orchestrator` as they do today — the class is still imported in main.py after refactor. New builder-specific tests in `test_orchestrator_builder.py` can patch `build_orchestrator_dependencies` in their own namespace.
<!-- Fix: M-001 — create doctor branch test file -->
- 4c (after step 3): create `tests/cli/test_cli_doctor_branch.py` with test cases for: doctor exits 0, doctor outputs tool status, doctor works without state file.

5. Regression check for command behavior.
Dependency: steps 3 and 4.
Action: verify unchanged command-to-request mapping and exit code behavior via existing CLI tests and the new exit-code matrix tests.
<!-- Fix: W-10 — review exit code matrix test monkeypatch targets post-refactor for stability, even if no changes required. The monkeypatch targets may shift if imports move from main.py to the builder. -->

6. Documentation touch-up (minimal).
Dependency: step 3.
Action: add a short note in [docs/REPO_ARCHITECTURE.md](docs/REPO_ARCHITECTURE.md) stating that CLI delegates dependency assembly to harness service builder.
<!-- Fix: W-9 — docs/REPO_ARCHITECTURE.md exists as of plan date; create file if it does not exist, or append to existing content. -->

**Relevant files**
- /Users/felipe_gonzalez/Developer/paper-writer/cli/paper/main.py — remove inline wiring and call builder.
- /Users/felipe_gonzalez/Developer/paper-writer/harness/services/assembler.py — currently unrelated manuscript assembler; avoid overloading this file with dependency wiring.
- /Users/felipe_gonzalez/Developer/paper-writer/harness/services/ (new module) — host the new wiring builder API.
<!-- Fix: M-002 — locked filename -->
- /Users/felipe_gonzalez/Developer/paper-writer/harness/services/orchestrator_builder.py — the new dependency assembler module (created in step 2).
<!-- Fix: M-001 — doctor branch test file to be created -->
- /Users/felipe_gonzalez/Developer/paper-writer/tests/cli/test_cli_doctor_branch.py — create with test cases for doctor exits 0, doctor outputs tool status, doctor works without state file (created in step 4c).
- /Users/felipe_gonzalez/Developer/paper-writer/tests/cli/test_cli_request_mapping.py — ensure request mapping remains unchanged after refactor.
- /Users/felipe_gonzalez/Developer/paper-writer/tests/cli/test_cli_exit_code_matrix.py — confirm failure category exit codes stay stable.
- /Users/felipe_gonzalez/Developer/paper-writer/tests/harness/test_assembler.py — keep isolated from new wiring builder unless intentionally split into dedicated builder tests.
<!-- Fix: S-12 — integration test file as primary verification gate -->
- /Users/felipe_gonzalez/Developer/paper-writer/tests/harness/test_orchestrator_builder.py — integration test: builder -> orchestrator -> result with minimal tmp_path repo.

**Verification**
1. Static diagnostics clean for changed files (no new Problems).
2. CLI contract tests pass: [tests/cli/test_cli_request_mapping.py](tests/cli/test_cli_request_mapping.py).
3. Exit code matrix tests pass: [tests/cli/test_cli_exit_code_matrix.py](tests/cli/test_cli_exit_code_matrix.py).
4. Doctor branch regression test passes: [tests/cli/test_cli_doctor_branch.py](tests/cli/test_cli_doctor_branch.py).
5. Harness tests covering orchestrator behavior still pass: [tests/harness/test_orchestrator.py](tests/harness/test_orchestrator.py).
6. Manual sanity run of one happy-path command to confirm no runtime wiring regression.
<!-- Fix: M-005 / S-12 — integration test elevated to primary verification gate -->
7. Integration test (primary gate): create `tests/harness/test_orchestrator_builder.py` exercising builder -> orchestrator -> result with a minimal tmp_path repo. Minimal assertions: `result.success` is correct, `result.exit_code` matches expected value, state file is created on disk. This is the primary automated verification gate — step 6 (manual sanity run) is supplementary.

**Decisions**
- Included scope: extraction of dependency construction only.
- Excluded scope: parser redesign, command mapping changes, or orchestrator logic refactor.
<!-- Fix: H-002 — doctor branch out of scope -->
- Doctor command wiring is intentionally excluded from this extraction because it bypasses the orchestrator. A future task may extract doctor wiring into a separate builder function.
- Guardrail: preserve current observable behavior (request mapping, warnings, exit codes).
- Guardrail: doctor branch behavior is protected by automated test, not only manual checks.

**Further Considerations**
1. Naming choice recommendation: use a new file name like orchestrator_builder.py instead of reusing [harness/services/assembler.py](harness/services/assembler.py) to avoid mixing manuscript assembly with dependency assembly concerns.
2. Future follow-up (separate task): reduce cognitive complexity in [harness/services/orchestrator.py](harness/services/orchestrator.py#L69) once wiring extraction is complete.
