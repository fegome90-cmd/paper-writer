# Tasks: ToolResolver Port Centralization

> **Status**: 📝 Planned  
> **Topic Key**: `sdd/tool-resolver-port/tasks`

## Phase 1: Infrastructure & Ports
- [ ] 1.1 Create `harness/ports/tool_resolver.py` with `ToolResolver` ABC and `ToolResolutionError`.
- [ ] 1.2 Implement `harness/adapters/local_tool_resolver.py` with waterfall logic (Env -> Local -> Global).
- [ ] 1.3 Add unit tests for `LocalToolResolver` in `tests/adapters/test_local_tool_resolver.py`.

## Phase 2: Core Refactoring
- [ ] 2.1 Update `ToolWrapper` in `harness/ports/tool_wrapper.py` to accept `ToolResolver` in `__init__`.
- [ ] 2.2 Refactor `BibliographyNormalizer` in `integrations/tools/bibtex_tidy.py` to use injected resolver (delete redundant code).
- [ ] 2.3 Refactor `PandocRenderer` in `integrations/tools/pandoc.py` to use injected resolver.
- [ ] 2.4 Refactor `StyleLinter` in `integrations/tools/vale.py` to use injected resolver.
- [ ] 2.5 Refactor `ZoteroImporter` in `integrations/tools/zotero_import.py` to use injected resolver.

## Phase 3: Integration & Wiring
- [ ] 3.1 Update `build_orchestrator_dependencies` in `harness/services/orchestrator_builder.py` to instantiate and inject `LocalToolResolver`.
- [ ] 3.2 Update `Orchestrator` constructor and tests in `tests/harness/test_orchestrator.py` if signature changed.

## Phase 4: Verification
- [ ] 4.1 Run `paper doctor` and verify all tools are correctly resolved in different scenarios (env var set vs not set).
- [ ] 4.2 Run integration tests: `pytest tests/integrations/test_tool_wrappers.py`.
- [ ] 4.3 Run full smoke test: `uv run paper init --preset nature && uv run paper doctor`.

## Phase 5: Cleanup
- [ ] 5.1 Remove any unused imports or temporary comments in adaptors.
- [ ] 5.2 Update `docs/CODE_ISSUES_LOG.md` marking the refactoring as complete.

---
*Plan generado por Gemini CLI Agent mediante SDD (Spec-Driven Development).*
