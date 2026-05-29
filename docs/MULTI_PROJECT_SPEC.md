# paper-writer - Multi-Project Mode Specification

Defines how paper-writer can be installed once and used to produce multiple independent papers.

## Quick path

1. Install `paper-writer` as a package (pip/uv).
2. Create a project directory per paper.
3. Run `paper init` (or `paper -C /path/to/project init`) from anywhere.
4. The CLI resolves assets from the installed package, state from the project directory.

## Problem Statement

Currently the CLI uses `Path.cwd()` as `project_root` in 3 places and has no `--project` flag. This means:

1. The user must always run `paper` from inside their paper project directory.
2. `validate_repo_initialized` checks for **source code directories** (`cli/`, `harness/`, `validators/`) that only exist in the source tree.
3. `paper init` creates empty stubs of source directories to pass the gate — a workaround, not a design.
4. There is no separation between "engine" (installed package) and "project" (user's paper directory).

## Goal

Enable this workflow:

```bash
# Install once
uv tool install paper-writer  # or: pip install paper-writer

# Paper A
mkdir ~/papers/voice-disorders && cd ~/papers/voice-disorders
paper init --preset nature
paper import bib ~/Downloads/references.bib
paper search --raw-papers candidates.json
# ... full pipeline ...

# Paper B (concurrent, independent)
mkdir ~/papers/sleep-apnea && cd ~/papers/sleep-apnea
paper init
paper import bib ~/Downloads/sleep-refs.bib
# ...
```

Or with explicit project flag:

```bash
paper -C ~/papers/voice-disorders init --preset nature
paper -C ~/papers/voice-disorders search
```

## Design Decisions

### Decision 1: Dual project root resolution

The CLI resolves `project_root` using this priority:

1. `--project / -C` flag (explicit path)
2. Ascending search for `outputs/state.yaml` from CWD (like `git` finds `.git`)
3. `Path.cwd()` as fallback (backward compatible)

This means:
- Existing users who `cd` into their project directory continue to work unchanged.
- New users can specify the project explicitly from anywhere.
- If the user runs `paper init` in an empty directory, it uses CWD (no state.yaml to find yet).

### Decision 2: Separate engine from project

A "project" directory contains **only**:

```text
my-paper/
  outputs/
    state.yaml
    search/
    drafts/
    render/
    logs/
  templates/
    manuscript.qmd      # copy or generated
    references.bib      # user-provided or imported
```

It does NOT contain: `cli/`, `harness/`, `validators/`, `skills/`, `styles/`, `tests/`, source code of any kind.

Assets (presets, CSL styles, Vale rules, skill resources) resolve from the **installed package** via `harness/ports/assets.py`.

### Decision 3: Updated gate for repo_initialized

The `validate_repo_initialized` gate must check for **project directories**, not source directories.

Current (broken for projects):
```python
required_dirs = ["cli", "harness", "validators", "templates", "outputs"]
```

Proposed:
```python
required_entries = ["templates", "outputs"]
required_files = ["outputs/state.yaml"]
```

A project is "initialized" when it has `templates/`, `outputs/`, and `outputs/state.yaml`. Period.

### Decision 4: Asset resolution waterfall

All asset reads follow a single pattern:

```text
project_dir / "templates" / ...    → if exists, use project-local version
package_assets / "templates" / ... → fallback to installed package
```

The `harness/ports/assets.py` module already implements `importlib.resources` correctly.
The gap is that most code bypasses it and constructs paths directly via `repo_path / "templates/..."`.

Fix: route all asset reads through `assets.py` or through the action runner (which already does dual resolution for presets).

## Affected Components

### BLOCKER changes (must fix)

| ID | File | Change | Impact |
|----|------|--------|--------|
| B1 | `cli/paper/main.py` | Add `--project/-C` flag; resolve project root via ascending search | CLI entry point |
| B2 | `harness/services/gates.py` | `validate_repo_initialized`: check `templates/`, `outputs/`, `outputs/state.yaml` only | Gate logic |
| B3 | `harness/adapters/filesystem_action_runner.py` | `init`: stop creating `cli/`, `harness/`, `validators/` stubs | Init behavior |
| B4 | `harness/ports/assets.py` | Verify package install resolves correctly for all asset types | Asset resolution |
| B5 | `integrations/tools/bibtex_tidy.py` | Use `repo_path` from context, not `Path.cwd()` fallback | Tool wrapper |
| B6 | `harness/adapters/filesystem_action_runner.py` | `emit_manifest`: use relative paths (already correct) but document | Manifest |
| B7 | `harness/services/orchestrator.py` | Route render template lookup through asset resolver | Render logic |

### WARNING changes (should fix)

| ID | File | Change |
|----|------|--------|
| W1 | `cli/paper/main.py` | `--target` default should be relative to project root, not CWD |
| W2 | `harness/services/orchestrator.py` | Default `target_bib` relative to project root |
| W3 | `integrations/tools/zotero_import.py` | Same pattern as W2 |

## Project Root Resolution Algorithm

```python
def resolve_project_root(explicit_path: Path | None, cwd: Path) -> Path:
    """Resolve project root with git-like ascending search.

    Priority:
    1. Explicit --project flag
    2. Ascending search for outputs/state.yaml
    3. CWD fallback
    """
    if explicit_path is not None:
        path = explicit_path.resolve()
        if not path.is_dir():
            raise ValueError(f"Project path does not exist: {path}")
        return path

    # Ascending search for outputs/state.yaml
    current = cwd.resolve()
    for _ in range(20):  # safety limit
        candidate = current / "outputs" / "state.yaml"
        if candidate.is_file():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    # Fallback: use CWD (backward compatible for `paper init` in new dirs)
    return cwd.resolve()
```

## CLI Changes

### New global flag

```
paper [--project PATH/-C PATH] <command> [args...]
```

### Updated `paper init`

```bash
# In empty directory (creates project structure)
mkdir my-paper && cd my-paper
paper init

# From anywhere, with explicit path
paper -C ~/papers/my-paper init --preset nature
```

`paper init` creates:

```text
my-paper/
  templates/
    manuscript.qmd      # copied from package or preset
    references.bib      # copied from preset or empty
  outputs/
    state.yaml          # bootstrap state
    search/
    drafts/
    render/
    logs/
```

Does NOT create: `cli/`, `harness/`, `validators/`, `tests/`.

### Updated `paper doctor`

`paper doctor` should report:
- Project root path (resolved via algorithm)
- Package install path (where assets come from)
- Which mode: "source tree" vs "installed package"
- Whether assets are available from the package

## Migration Path

### For existing users (source tree mode)

No breaking change. If CWD contains the source tree, `Path.cwd()` is used (priority 3).
The ascending search won't find a different `state.yaml` because the source tree's `outputs/state.yaml` is in CWD.

Existing tests continue to pass because they use `tmp_path` and pass explicit `project_root`.

### For new users (installed package mode)

```bash
uv tool install paper-writer
mkdir ~/papers/my-paper && cd ~/papers/my-paper
paper init --preset nature
```

### For CI

```bash
pip install paper-writer
paper -C /workspace/paper init
paper -C /workspace/paper search --raw-papers candidates.json
```

## Testing Requirements

1. **Project resolution tests**: ascending search, explicit flag, CWD fallback
2. **Init from empty dir**: creates only project dirs, not source stubs
3. **Init from outside project**: `paper -C /tmp/my-paper init` works
4. **Asset resolution from installed package**: presets, CSL, Vale rules resolve
5. **Full pipeline in project mode**: init → search → render → verify from a lean project dir
6. **Backward compatibility**: existing tests pass without modification
7. **Package install contract**: `pyproject.toml` package-data covers all runtime assets

## File Structure After Implementation

### Source tree (development)

```text
paper-writer/                    # source repo
  cli/paper/main.py              # + --project flag
  harness/
    ports/assets.py              # asset resolver (unchanged)
    services/gates.py            # updated gate checks
    services/orchestrator.py     # route through asset resolver
    adapters/filesystem_action_runner.py  # stop creating source stubs
  integrations/tools/
    bibtex_tidy.py               # use project root from context
  templates/                     # packaged assets
  styles/                        # packaged assets
  skills/                        # packaged assets
  tests/                         # + new multi-project tests
```

### User project (installed mode)

```text
my-paper/                        # user directory
  outputs/
    state.yaml
    search/
    drafts/
    render/
    logs/
  templates/
    manuscript.qmd
    references.bib
```

## Estimated Effort

| Task | Hours | Priority |
|------|-------|----------|
| Add `--project` flag + ascending resolution | 1.5h | P0 |
| Update `validate_repo_initialized` gate | 0.5h | P0 |
| Remove source stubs from `paper init` | 0.5h | P0 |
| Route orchestrator render through asset resolver | 1h | P1 |
| Fix bibtex_tidy CWD fallback | 0.5h | P1 |
| Fix default path assumptions (W1-W3) | 0.5h | P1 |
| Update `paper doctor` for dual mode | 0.5h | P2 |
| Multi-project tests | 1.5h | P0 |
| Update docs (README, REPO_ARCHITECTURE, Makefile) | 0.5h | P2 |
| **Total** | **~7h** | |

## Audit Checklist

- [ ] `paper -C /path init` works from any directory
- [ ] Ascending search finds `outputs/state.yaml`
- [ ] `validate_repo_initialized` checks project dirs, not source dirs
- [ ] `paper init` does not create `cli/`, `harness/`, `validators/`
- [ ] Assets resolve from installed package when not in project dir
- [ ] Existing tests pass without modification
- [ ] New project-mode tests cover resolution, init, full pipeline
- [ ] `paper doctor` reports project root and package mode
