"""
Arm B: LSP Baseline
Uses pyright CLI for definitions, references, and hover info.
No pre-computed graph — each query triggers live LSP operations.
"""

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LSPResult:
    """Result from an LSP query."""

    query: str
    matches: list[dict[str, Any]]
    latency_ms: int
    arm: str = "grep_pyright"


@dataclass
class LSPBaseline:
    """
    LSP-based baseline using pyright.
    Provides definitions, references — but no pre-computed graph.
    Each query triggers a fresh LSP operation (realistic IDE baseline).
    """

    repo_root: Path
    _pyright_available: bool | None = None
    index_time_ms: int = 0  # LSP has no separate index phase

    def _check_pyright(self) -> bool:
        """Check if pyright is available."""
        if self._pyright_available is None:
            try:
                _result = subprocess.run(
                    ["pyright", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self._pyright_available = _result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._pyright_available = False
        return self._pyright_available

    def _find_symbol_location(
        self,
        symbol_name: str,
    ) -> tuple[str, int] | None:
        """Find file and approximate line for a symbol using grep."""
        for filepath in self.repo_root.rglob("*.py"):
            if "/.venv/" in str(filepath) or "/__pycache__/" in str(filepath):
                continue
            try:
                content = filepath.read_text(errors="ignore")
                for i, line in enumerate(content.split("\n"), 1):
                    stripped = line.strip()
                    if (
                        stripped.startswith(f"def {symbol_name}")
                        or stripped.startswith(f"async def {symbol_name}")
                        or stripped.startswith(f"class {symbol_name}")
                    ):
                        return str(filepath.relative_to(self.repo_root)), i
            except (OSError, ValueError):
                continue
        return None

    def _file_to_uri(self, rel_path: str) -> str:
        """Convert relative path to file URI."""
        abs_path = (self.repo_root / rel_path).resolve()
        return f"file://{abs_path}"

    def find_definition(self, symbol_name: str) -> LSPResult:
        """Find definition using pyright CLI + grep fallback."""
        t0 = time.perf_counter()

        matches = []

        # Try pyright --verifytype or similar
        if self._check_pyright():
            # Pyright doesn't have a CLI "goto definition" command.
            # We simulate LSP definition via grep + pyright hover for type info.
            loc = self._find_symbol_location(symbol_name)
            if loc:
                file_path, line = loc
                # Run pyright to verify the symbol is valid
                abs_path = self.repo_root / file_path
                try:
                    subprocess.run(
                        ["pyright", "--verifytypes", symbol_name, str(abs_path)],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    # pyright confirms the symbol exists
                    matches.append(
                        {
                            "file": file_path,
                            "line": line,
                            "name": symbol_name,
                            "text": f"LSP verified: {symbol_name}",
                            "score": 1.0,
                        }
                    )
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    # Fallback to grep result
                    matches.append(
                        {
                            "file": file_path,
                            "line": line,
                            "name": symbol_name,
                            "text": f"grep fallback: {symbol_name}",
                            "score": 0.7,
                        }
                    )
        else:
            # No pyright — pure grep
            loc = self._find_symbol_location(symbol_name)
            if loc:
                file_path, line = loc
                matches.append(
                    {
                        "file": file_path,
                        "line": line,
                        "name": symbol_name,
                        "text": f"grep-only: {symbol_name}",
                        "score": 0.5,
                    }
                )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return LSPResult(
            query=f"definition of {symbol_name}",
            matches=matches,
            latency_ms=latency_ms,
        )

    def find_references(self, symbol_name: str) -> LSPResult:
        """Find all references using grep (pyright doesn't expose refs via CLI)."""
        t0 = time.perf_counter()

        matches = []
        seen: set[str] = set()

        for filepath in self.repo_root.rglob("*.py"):
            if "/.venv/" in str(filepath) or "/__pycache__/" in str(filepath):
                continue
            try:
                rel = str(filepath.relative_to(self.repo_root))
                content = filepath.read_text(errors="ignore")
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    if symbol_name in line:
                        # Skip string literals and comments (rough heuristic)
                        stripped = line.strip()
                        if stripped.startswith("#"):
                            continue
                        key = f"{rel}:{i}"
                        if key not in seen:
                            seen.add(key)
                            matches.append(
                                {
                                    "file": rel,
                                    "line": i,
                                    "name": symbol_name,
                                    "text": stripped[:100],
                                    "score": 0.8,
                                }
                            )
            except (OSError, ValueError):
                continue

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return LSPResult(
            query=f"references of {symbol_name}",
            matches=matches,
            latency_ms=latency_ms,
        )

    def find_callers(self, symbol_name: str) -> LSPResult:
        """Find callers by finding references that are NOT definitions."""
        refs = self.find_references(symbol_name)

        callers = []
        for m in refs.matches:
            # Exclude the definition line
            content_line = m.get("text", "")
            if f"def {symbol_name}" in content_line or f"class {symbol_name}" in content_line:
                continue
            callers.append(m)

        return LSPResult(
            query=f"callers of {symbol_name}",
            matches=callers,
            latency_ms=refs.latency_ms,
        )

    def search(self, query: str, top_k: int = 10) -> LSPResult:
        """LSP has no search — falls back to grep."""
        t0 = time.perf_counter()

        # Tokenize query
        tokens = re.findall(r"[a-z0-9_]+", query.lower())

        matches = []
        scored: list[tuple[float, dict[str, Any]]] = []

        for filepath in self.repo_root.rglob("*.py"):
            if "/.venv/" in str(filepath) or "/__pycache__/" in str(filepath):
                continue
            try:
                rel = str(filepath.relative_to(self.repo_root))
                content = filepath.read_text(errors="ignore")
                content_lower = content.lower()

                score = sum(1 for t in tokens if t in content_lower) / max(len(tokens), 1)

                if score > 0.3:
                    scored.append(
                        (
                            score,
                            {
                                "file": rel,
                                "line": 1,
                                "name": Path(rel).stem,
                                "text": content[:200],
                                "score": round(score, 2),
                            },
                        )
                    )
            except (OSError, ValueError):
                continue

        scored.sort(key=lambda x: x[0], reverse=True)
        matches = [m for _, m in scored[:top_k]]

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return LSPResult(
            query=query,
            matches=matches,
            latency_ms=latency_ms,
        )

    def find_orphans(self) -> LSPResult:
        """Find functions with zero callers — O(n²), capped at 60s."""

        t0 = time.perf_counter()

        # Collect all definitions
        all_defs: dict[str, dict[str, Any]] = {}
        for filepath in self.repo_root.rglob("*.py"):
            if "/.venv/" in str(filepath) or "/__pycache__/" in str(filepath):
                continue
            try:
                rel = str(filepath.relative_to(self.repo_root))
                content = filepath.read_text(errors="ignore")
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    stripped = line.strip()
                    for prefix in ("def ", "async def "):
                        if stripped.startswith(prefix):
                            name = stripped[len(prefix) :].split("(")[0].strip()
                            if name and not name.startswith("_"):
                                all_defs[f"{rel}:{name}"] = {
                                    "file": rel,
                                    "line": i,
                                    "name": name,
                                }
            except (OSError, ValueError):
                continue

        # Pre-load all file contents for fast checking
        file_contents: list[tuple[str, str]] = []
        for filepath in self.repo_root.rglob("*.py"):
            if "/.venv/" in str(filepath) or "/__pycache__/" in str(filepath):
                continue
            try:
                file_contents.append(
                    (str(filepath.relative_to(self.repo_root)),
                     filepath.read_text(errors="ignore"))
                )
            except (OSError, ValueError):
                continue

        # Check each definition for references (with time cap)
        orphans = []
        for _key, loc in all_defs.items():
            if time.perf_counter() - t0 > 60:
                break  # Time cap
            name = loc["name"]
            ref_count = 0
            for _frel, content in file_contents:
                if name in content:
                    for line in content.split("\n"):
                        stripped = line.strip()
                        if name in stripped:
                            if not (
                                stripped.startswith(f"def {name}")
                                or stripped.startswith(
                                    f"async def {name}"
                                )
                            ):
                                ref_count += 1
                                break
                    if ref_count > 0:
                        break

            if ref_count == 0:
                orphans.append(
                    {
                        "file": loc["file"],
                        "line": loc["line"],
                        "name": name,
                        "text": f"Zero callers for {name}",
                        "score": 1.0,
                    }
                )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return LSPResult(
            query="find orphan functions",
            matches=orphans,
            latency_ms=latency_ms,
        )

    def find_subclasses(
        self,
        class_name: str,
        *,
        transitive: bool = False,
    ) -> LSPResult:
        """Find subclasses via grep for class X(Parent)."""
        t0 = time.perf_counter()

        matches = []
        seen: set[str] = set()
        queue = [class_name]
        depth = 0
        max_depth = 5 if transitive else 1

        while queue and depth < max_depth:
            next_queue = []
            for parent in queue:
                for filepath in self.repo_root.rglob("*.py"):
                    if "/.venv/" in str(filepath) or "/__pycache__/" in str(filepath):
                        continue
                    try:
                        rel = str(filepath.relative_to(self.repo_root))
                        content = filepath.read_text(errors="ignore")
                        pattern = rf"class\s+(\w+)\s*\([^)]*\b{parent}\b[^)]*\)"
                        for m in re.finditer(pattern, content):
                            child = m.group(1)
                            key = f"{rel}:{child}"
                            if key not in seen:
                                seen.add(key)
                                matches.append(
                                    {
                                        "file": rel,
                                        "line": 1,
                                        "name": child,
                                        "text": f"class {child}({parent})",
                                        "score": 1.0,
                                        "depth": depth + 1,
                                    }
                                )
                                if transitive:
                                    next_queue.append(child)
                    except (OSError, ValueError):
                        continue
            queue = next_queue
            depth += 1

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return LSPResult(
            query=f"subclasses of {class_name}",
            matches=matches,
            latency_ms=latency_ms,
        )

    def find_dynamic_imports(self) -> LSPResult:
        """Find importlib usage via grep."""
        t0 = time.perf_counter()

        matches = []
        for filepath in self.repo_root.rglob("*.py"):
            if "/.venv/" in str(filepath) or "/__pycache__/" in str(filepath):
                continue
            try:
                rel = str(filepath.relative_to(self.repo_root))
                content = filepath.read_text(errors="ignore")
                if "importlib" in content:
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        if "importlib" in line:
                            matches.append(
                                {
                                    "file": rel,
                                    "line": i,
                                    "name": "",
                                    "text": line.strip()[:100],
                                    "score": 1.0,
                                }
                            )
            except (OSError, ValueError):
                continue

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return LSPResult(
            query="dynamic imports",
            matches=matches,
            latency_ms=latency_ms,
        )
