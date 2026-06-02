"""
Arm A: TF-IDF RAG Baseline
Pure text retrieval — no structural knowledge, no AST, no graph.
Represents the "current industry standard" for RAG code search.
"""

import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RetrievalResult:
    """Result from a RAG retrieval query."""
    query: str
    matches: list[dict[str, Any]]  # [{file, line, text, score}]
    latency_ms: int
    arm: str = "rag_tfidf"


@dataclass
class RAGBaseline:
    """
    TF-IDF based RAG baseline.
    Indexes all Python files, retrieves top-k chunks per query.
    No structural knowledge — pure text similarity.
    """

    repo_root: Path
    index: dict[str, list[str]] = field(default_factory=dict)
    idf: dict[str, float] = field(default_factory=dict)
    doc_freq: Counter = field(default_factory=Counter)
    total_docs: int = 0
    chunks: list[dict[str, Any]] = field(default_factory=list)
    _indexed: bool = False
    index_time_ms: int = 0

    def index_repo(self) -> None:
        """Index all Python files into TF-IDF chunks."""
        t0 = time.perf_counter()

        python_files = list(self.repo_root.rglob("*.py"))
        python_files = [
            f for f in python_files
            if "/.venv/" not in str(f)
            and "/__pycache__/" not in str(f)
            and "/node_modules/" not in str(f)
            and "/.trifecta/" not in str(f)
            and "/benchmarks/" not in str(f)
        ]

        self.total_docs = 0
        self.chunks = []

        for filepath in python_files:
            rel_path = filepath.relative_to(self.repo_root)
            content = filepath.read_text(errors="ignore")
            lines = content.split("\n")

            # Chunk by function/class definition blocks
            current_chunk: list[str] = []
            current_start = 0
            chunk_name = ""

            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(("def ", "class ", "async def ")):
                    # Flush previous chunk
                    if current_chunk:
                        self._add_chunk(
                            rel_path, current_start, i,
                            chunk_name, "\n".join(current_chunk),
                        )
                    current_chunk = [line]
                    current_start = i
                    chunk_name = stripped.split("(")[0].replace("def ", "").replace(
                        "class ", ""
                    ).replace("async ", "").strip()
                else:
                    current_chunk.append(line)

            # Flush last chunk
            if current_chunk:
                self._add_chunk(
                    rel_path, current_start, len(lines),
                    chunk_name, "\n".join(current_chunk),
                )

            # Also index the whole file as a "document"
            tokens = self._tokenize(content)
            self.index[str(rel_path)] = tokens
            for t in set(tokens):
                self.doc_freq[t] += 1
            self.total_docs += 1

        # Compute IDF
        for term, df in self.doc_freq.items():
            self.idf[term] = math.log(self.total_docs / (1 + df))

        self._indexed = True
        self.index_time_ms = int((time.perf_counter() - t0) * 1000)

    def _add_chunk(
        self,
        file: Path,
        start: int,
        end: int,
        name: str,
        content: str,
    ) -> None:
        tokens = self._tokenize(content)
        self.chunks.append({
            "file": str(file),
            "start_line": start + 1,  # 1-indexed
            "end_line": end,
            "name": name,
            "content": content,
            "tokens": tokens,
        })
        for t in set(tokens):
            self.doc_freq[t] += 1

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization: lowercase, split on non-alphanumeric."""
        return re.findall(r"[a-z0-9_]+", text.lower())

    def _tfidf_score(
        self, query_tokens: list[str], doc_tokens: list[str],
    ) -> float:
        """Compute TF-IDF cosine similarity."""
        if not doc_tokens or not query_tokens:
            return 0.0

        doc_counter = Counter(doc_tokens)
        doc_len = len(doc_tokens)

        score = 0.0
        for qt in query_tokens:
            if qt in doc_counter and qt in self.idf:
                tf = doc_counter[qt] / doc_len
                score += tf * self.idf[qt]

        # Normalize by query length
        if query_tokens:
            score /= len(query_tokens)

        return score

    def search(
        self, query: str, top_k: int = 10,
    ) -> RetrievalResult:
        """Search for relevant chunks using TF-IDF."""
        t0 = time.perf_counter()

        if not self._indexed:
            self.index_repo()

        query_tokens = self._tokenize(query)

        # Score chunks
        scored = []
        for chunk in self.chunks:
            score = self._tfidf_score(query_tokens, chunk["tokens"])
            if score > 0:
                scored.append((score, chunk))

        # Also score whole files
        for file_path, tokens in self.index.items():
            score = self._tfidf_score(query_tokens, tokens)
            if score > 0:
                scored.append((score * 0.5, {  # Lower weight for file-level
                    "file": file_path,
                    "start_line": 1,
                    "end_line": 0,
                    "name": Path(file_path).stem,
                    "content": "",
                }))

        # Sort and take top-k
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        matches = []
        for score, chunk in top:
            matches.append({
                "file": chunk["file"],
                "line": chunk["start_line"],
                "name": chunk.get("name", ""),
                "text": chunk["content"][:200],
                "score": round(score, 4),
            })

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return RetrievalResult(
            query=query,
            matches=matches,
            latency_ms=latency_ms,
            arm="rag_tfidf",
        )

    def find_definition(self, symbol_name: str) -> RetrievalResult:
        """Find where a symbol is defined — text-based grep."""
        t0 = time.perf_counter()

        if not self._indexed:
            self.index_repo()

        matches = []
        for chunk in self.chunks:
            content = chunk["content"]
            # Look for def/class followed by the symbol name
            patterns = [
                f"def {symbol_name}",
                f"async def {symbol_name}",
                f"class {symbol_name}",
            ]
            for pattern in patterns:
                if pattern in content:
                    matches.append({
                        "file": chunk["file"],
                        "line": chunk["start_line"],
                        "name": symbol_name,
                        "text": content[:200],
                        "score": 1.0,
                    })
                    break

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return RetrievalResult(
            query=f"definition of {symbol_name}",
            matches=matches,
            latency_ms=latency_ms,
            arm="rag_tfidf",
        )

    def find_callers(self, symbol_name: str) -> RetrievalResult:
        """Find callers of a function — text-based grep."""
        t0 = time.perf_counter()

        if not self._indexed:
            self.index_repo()

        matches = []
        seen_files: set[str] = set()

        for chunk in self.chunks:
            if symbol_name in chunk["content"]:
                # Exclude the definition itself
                has_def = (
                    f"def {symbol_name}" in chunk["content"]
                    or f"class {symbol_name}" in chunk["content"]
                )
                if not has_def or chunk["name"] != symbol_name:
                    key = f"{chunk['file']}:{chunk['start_line']}"
                    if key not in seen_files:
                        seen_files.add(key)
                        matches.append({
                            "file": chunk["file"],
                            "line": chunk["start_line"],
                            "name": chunk.get("name", ""),
                            "text": chunk["content"][:200],
                            "score": 0.8 if not has_def else 0.4,
                        })

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return RetrievalResult(
            query=f"callers of {symbol_name}",
            matches=matches,
            latency_ms=latency_ms,
            arm="rag_tfidf",
        )

    def find_orphans(self) -> RetrievalResult:
        """Find functions with zero callers — requires full scan."""
        t0 = time.perf_counter()

        if not self._indexed:
            self.index_repo()

        # Collect all defined symbols
        all_defined: dict[str, dict] = {}
        for chunk in self.chunks:
            name = chunk.get("name", "")
            if name and (
                chunk["content"].strip().startswith("def ")
                or chunk["content"].strip().startswith("async def ")
            ):
                all_defined[name] = {
                    "file": chunk["file"],
                    "line": chunk["start_line"],
                }

        # For each defined symbol, check if it appears in any OTHER chunk
        orphans = []
        for name, loc in all_defined.items():
            caller_count = 0
            for chunk in self.chunks:
                if chunk.get("name") == name:
                    continue  # Skip self
                if name in chunk["content"]:
                    caller_count += 1
            if caller_count == 0:
                orphans.append({
                    "file": loc["file"],
                    "line": loc["line"],
                    "name": name,
                    "text": f"Zero callers found for {name}",
                    "score": 1.0,
                })

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return RetrievalResult(
            query="find orphan functions",
            matches=orphans,
            latency_ms=latency_ms,
            arm="rag_tfidf",
        )

    def find_subclasses(
        self, class_name: str, *, transitive: bool = False,
    ) -> RetrievalResult:
        """Find subclasses — text-based grep for class X(Y)."""
        t0 = time.perf_counter()

        if not self._indexed:
            self.index_repo()

        matches = []
        seen: set[str] = set()
        queue = [class_name]

        depth = 0
        max_depth = 5 if transitive else 1

        while queue and depth < max_depth:
            next_queue = []
            for parent in queue:
                for chunk in self.chunks:
                    content = chunk["content"]
                    # Match "class Child(Parent)"
                    pattern = rf"class\s+(\w+)\s*\([^)]*\b{parent}\b[^)]*\)"
                    for m in re.finditer(pattern, content):
                        child = m.group(1)
                        key = f"{chunk['file']}:{child}"
                        if key not in seen:
                            seen.add(key)
                            matches.append({
                                "file": chunk["file"],
                                "line": chunk["start_line"],
                                "name": child,
                                "text": content[:200],
                                "score": 1.0,
                                "depth": depth + 1,
                            })
                            if transitive:
                                next_queue.append(child)
            queue = next_queue
            depth += 1

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return RetrievalResult(
            query=f"subclasses of {class_name}",
            matches=matches,
            latency_ms=latency_ms,
            arm="rag_tfidf",
        )

    def find_dynamic_imports(self) -> RetrievalResult:
        """Find importlib.import_module calls — text grep."""
        t0 = time.perf_counter()

        if not self._indexed:
            self.index_repo()

        matches = []
        for chunk in self.chunks:
            if "importlib" in chunk["content"]:
                matches.append({
                    "file": chunk["file"],
                    "line": chunk["start_line"],
                    "name": chunk.get("name", ""),
                    "text": chunk["content"][:200],
                    "score": 1.0,
                })

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return RetrievalResult(
            query="dynamic imports via importlib",
            matches=matches,
            latency_ms=latency_ms,
            arm="rag_tfidf",
        )
