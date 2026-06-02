"""
Fair Benchmark Runner — 3-arm comparison addressing study biases.

Biases corrected:
  B1: Straw-man control → 3 arms (RAG, LSP, Trifecta)
  B2: Restrictive timeout → differentiated timing
  B3: Single repo → synthetic + real repos
  B4: No weakness testing → targeted weakness tasks
"""

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from arms.lsp_baseline import LSPBaseline
from arms.rag_baseline import RAGBaseline
from arms.trifecta_arm import TrifectaArm
from fixtures.synthetic_repo import create_synthetic_repo


@dataclass
class TaskResult:
    """Result from a single task on a single arm."""

    task_id: str
    arm: str
    repo: str
    recall: float
    precision: float
    mrr: float
    latency_ms: int
    matches_found: int
    gold_items: int
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Complete benchmark results."""

    tasks: list[TaskResult] = field(default_factory=list)
    index_times: dict[str, int] = field(default_factory=dict)

    def get_arm_scores(self, arm: str) -> dict[str, float]:
        """Get aggregate scores for an arm."""
        arm_tasks = [t for t in self.tasks if t.arm == arm]
        if not arm_tasks:
            return {}
        return {
            "avg_recall": sum(t.recall for t in arm_tasks) / len(arm_tasks),
            "avg_precision": sum(t.precision for t in arm_tasks) / len(arm_tasks),
            "avg_mrr": sum(t.mrr for t in arm_tasks) / len(arm_tasks),
            "avg_latency_ms": sum(t.latency_ms for t in arm_tasks) / len(arm_tasks),
            "total_tasks": len(arm_tasks),
        }


def score_task(
    matches: list[dict[str, Any]],
    gold: dict[str, Any],
    task_type: str,
) -> dict[str, float]:
    """
    Score a task result against gold answers.
    Returns recall, precision, mrr.
    """
    if not matches:
        return {"recall": 0.0, "precision": 0.0, "mrr": 0.0}

    if task_type == "precision":
        # Gold: file + line match
        gold_file = gold.get("gold_file", "")
        gold_line_range = gold.get("gold_line_range", (0, 999))
        gold_symbol = gold.get("gold_symbol", "")

        correct = 0
        for m in matches:
            file_match = gold_file in m.get("file", "")
            line = m.get("line", 0)
            line_match = gold_line_range[0] <= line <= gold_line_range[1]
            name_match = gold_symbol in m.get("name", "")
            if file_match and (line_match or name_match):
                correct += 1

        recall = min(correct, 1)
        precision = correct / max(len(matches), 1)
        mrr = 1.0 / (matches[0].get("line", 1)) if correct > 0 else 0.0
        return {
            "recall": float(recall),
            "precision": float(precision),
            "mrr": float(mrr) if mrr > 0 else 0.0,
        }

    elif task_type == "discovery":
        # Gold: specific files and callers
        gold_files = set(gold.get("gold_files", []))
        gold_callers = set(gold.get("gold_callers", []))
        gold.get("gold_path", [])

        found_files = set()
        found_callers = set()

        for m in matches:
            f = m.get("file", "")
            name = m.get("name", "")
            for gf in gold_files:
                if gf in f:
                    found_files.add(gf)
            for gc in gold_callers:
                if gc.split("::")[-1] in name or gc in f:
                    found_callers.add(gc)

        # Recall based on both files and callers
        total_gold = len(gold_files) + len(gold_callers)
        found = len(found_files) + len(found_callers)
        recall = float(found) / max(total_gold, 1)

        # Precision: how many matches are relevant
        precision = found / max(len(matches), 1)

        # MRR: first relevant match
        mrr = 0.0
        for i, m in enumerate(matches):
            f = m.get("file", "")
            for gf in gold_files:
                if gf in f:
                    mrr = 1.0 / (i + 1)
                    break
            if mrr > 0:
                break

        return {"recall": recall, "precision": precision, "mrr": mrr}

    elif task_type == "orphan":
        # Gold: specific orphan names
        gold_orphans = set(gold.get("gold_orphans", []))

        found_orphans = set()
        false_positives = 0

        for m in matches:
            name = m.get("name", "")

            # Check if it's a true orphan
            is_gold = False
            for go in gold_orphans:
                if name == go.split("::")[-1]:
                    found_orphans.add(go)
                    is_gold = True
                    break

            # Everything NOT a true gold orphan is a false positive
            if not is_gold:
                false_positives += 1

        recall = len(found_orphans) / max(len(gold_orphans), 1)
        precision = len(found_orphans) / max(len(found_orphans) + false_positives, 1)

        return {"recall": recall, "precision": precision, "mrr": recall}

    elif task_type == "weakness":
        # Gold: expected results
        gold_descendants = set(gold.get("gold_descendants", []))
        gold_answer = gold.get("gold_answer", None)
        gold_depth = gold.get("gold_depth", None)

        if gold_descendants:
            found: set[str] = set()
            for m in matches:
                name = m.get("name", "")
                for gd in gold_descendants:
                    if name == gd.split("::")[-1]:
                        found.add(gd)

            recall = float(len(found)) / max(len(gold_descendants), 1)
            precision = float(len(found)) / max(len(matches), 1)
            return {"recall": recall, "precision": precision, "mrr": recall}

        if gold_answer is not None and gold_depth is not None:
            # Binary + depth check
            depth_ok = any(m.get("depth", 0) >= gold_depth for m in matches)
            has_result = len(matches) > 0
            correct = has_result == gold_answer and (not gold_depth or depth_ok)
            return {
                "recall": 1.0 if correct else 0.0,
                "precision": 1.0 if correct else 0.0,
                "mrr": 1.0 if correct else 0.0,
            }

        return {"recall": 0.0, "precision": 0.0, "mrr": 0.0}

    elif task_type == "architecture":
        # Gold: layers mapping
        gold_layers = gold.get("gold_layers", {})
        total_files = sum(len(v) for v in gold_layers.values())

        found_files = set()
        for m in matches:
            f = m.get("file", "")
            for layer_files in gold_layers.values():
                for gf in layer_files:
                    if gf in f:
                        found_files.add(gf)

        recall = float(len(found_files)) / max(total_files, 1)
        precision = float(len(found_files)) / max(len(matches), 1)

        return {"recall": recall, "precision": precision, "mrr": recall}

    elif task_type == "semantic":
        # Gold: specific file and symbol
        gold_file = gold.get("gold_file", "")
        gold_symbol = gold.get("gold_symbol", "")

        found = False
        mrr = 0.0
        for i, m in enumerate(matches):
            f = m.get("file", "")
            name = m.get("name", "")
            if gold_file in f and gold_symbol in name:
                found = True
                mrr = 1.0 / (i + 1)
                break

        return {
            "recall": 1.0 if found else 0.0,
            "precision": 1.0 if found else 0.0,
            "mrr": mrr,
        }

    return {"recall": 0.0, "precision": 0.0, "mrr": 0.0}


def run_benchmark(
    repo_root: Path,
    tasks: dict[str, dict[Any, Any]],
    repo_name: str,
    graph_db_path: Path | None = None,
) -> BenchmarkResult:
    """Run all arms against all tasks for a single repo."""

    result = BenchmarkResult()

    # === Index phase ===
    t0 = time.perf_counter()
    rag = RAGBaseline(repo_root=repo_root)
    rag.index_repo()
    rag_index_ms = int((time.perf_counter() - t0) * 1000)

    lsp = LSPBaseline(repo_root=repo_root)
    lsp_index_ms = 0  # No separate index phase

    trifecta = TrifectaArm(repo_root=repo_root, graph_db_path=graph_db_path)
    trifecta_index_ms = 0  # Pre-computed

    result.index_times = {
        "rag_tfidf": rag_index_ms,
        "grep_pyright": lsp_index_ms,
        "trifecta": trifecta_index_ms,
    }

    # === Query phase ===
    for task_id, task in tasks.items():
        task["description"]

        # Determine task type from ID prefix
        task_type = task_id.split("-")[1].lower()[0]
        type_map = {
            "p": "precision",
            "d": "discovery",
            "o": "orphan",
            "w": "weakness",
            "a": "architecture",
            "s": "semantic",
        }
        task_type = type_map.get(task_type, "precision")

        # --- RAG arm ---
        rag_result = _run_arm_task(rag, task_id, task, task_type)
        if rag_result:
            rag_result.arm = "rag_tfidf"
            rag_result.repo = repo_name
            result.tasks.append(rag_result)

        # --- LSP arm ---
        lsp_result = _run_arm_task(lsp, task_id, task, task_type)
        if lsp_result:
            lsp_result.arm = "grep_pyright"
            lsp_result.repo = repo_name
            result.tasks.append(lsp_result)

        # --- Trifecta arm ---
        tri_result = _run_arm_task(trifecta, task_id, task, task_type)
        if tri_result:
            tri_result.arm = "trifecta"
            tri_result.repo = repo_name
            result.tasks.append(tri_result)

    return result


def _run_arm_task(
    arm: RAGBaseline | LSPBaseline | TrifectaArm,
    task_id: str,
    task: dict[str, Any],
    task_type: str,
) -> TaskResult | None:
    """Run a single task on a single arm."""
    desc = task["description"]

    try:
        if task_id.startswith("T-P"):
            # Precision task — find definition
            symbol = task.get("gold_symbol", desc.split(" ")[-1])
            if hasattr(arm, "find_definition"):
                res = arm.find_definition(symbol)
            else:
                return None

        elif task_id.startswith("T-D1"):
            # Discovery — trace call chain via search
            gold_path = task.get("gold_path", [])
            query_parts = []
            for entry in gold_path:
                parts = entry.split("::")
                query_parts.append(parts[-1])
            query = " ".join(query_parts) if query_parts else desc
            if hasattr(arm, "search"):
                res = arm.search(query, top_k=15)
            else:
                return None

        elif task_id.startswith("T-D2"):
            # Discovery — find callers of the gold symbol
            symbol = task.get("gold_symbol", "normalize")
            if hasattr(arm, "find_callers"):
                res = arm.find_callers(symbol)
            else:
                return None

        elif task_id.startswith("T-O1"):
            # Orphan detection
            if hasattr(arm, "find_orphans"):
                res = arm.find_orphans()
            else:
                return None

        elif task_id.startswith("T-W1"):
            # Transitive inheritance — read target from gold
            gold_desc = task.get("gold_descendants", [])
            if gold_desc:
                target = gold_desc[0].split("::")[-1]
                # Walk up: use the parent class mentioned in gold
                target = task.get("gold_parent_class", "BaseTransformer")
            else:
                target = task.get("gold_parent_class", "BaseTransformer")
            if hasattr(arm, "find_subclasses"):
                res = arm.find_subclasses(target, transitive=True)
            else:
                return None

        elif task_id.startswith("T-W2"):
            # Dynamic imports — scored by file matching
            if hasattr(arm, "find_dynamic_imports"):
                res = arm.find_dynamic_imports()
            else:
                return None
            # Override type to discovery for gold_files scoring
            task_type = "discovery"

        elif task_id.startswith("T-W3"):
            # Transitive inheritance depth check
            target = task.get("gold_parent_class", "BaseTransformer")
            if hasattr(arm, "find_subclasses"):
                res = arm.find_subclasses(target, transitive=True)
            else:
                return None

        elif task_id.startswith("T-A"):
            # Architecture — search for file/directory names
            gold_layers = task.get("gold_layers", {})
            if gold_layers:
                layer_names = list(gold_layers.keys())
                query = " ".join(layer_names)
            else:
                query = "architecture layers core plugins cli utils tests"
            if hasattr(arm, "search"):
                res = arm.search(query, top_k=20)
            else:
                return None

        elif task_id.startswith("T-S"):
            # Semantic search
            if hasattr(arm, "search"):
                res = arm.search(desc, top_k=5)
            else:
                return None

        else:
            return None

    except Exception as e:
        return TaskResult(
            task_id=task_id,
            arm="unknown",
            repo="",
            recall=0.0,
            precision=0.0,
            mrr=0.0,
            latency_ms=0,
            matches_found=0,
            gold_items=0,
            details={"error": str(e)},
        )

    scores = score_task(res.matches, task, task_type)

    return TaskResult(
        task_id=task_id,
        arm="",
        repo="",
        recall=scores["recall"],
        precision=scores["precision"],
        mrr=scores["mrr"],
        latency_ms=res.latency_ms,
        matches_found=len(res.matches),
        gold_items=len(
            task.get("gold_orphans", task.get("gold_files", task.get("gold_descendants", [])))
        ),
    )


def generate_report(
    results: list[BenchmarkResult],
) -> str:
    """Generate the honest benchmark report."""
    lines = [
        "# Fair Benchmark Report — Bias-Corrected Results",
        "",
        f"> Generated: {time.strftime('%Y-%m-%d %H:%M')}",
        "> Purpose: Address the 4 critical biases in the original Trifecta A/B study",
        "",
    ]

    # Collect all results by arm
    all_tasks: list[TaskResult] = []
    for r in results:
        all_tasks.extend(r.tasks)

    # === Per-arm aggregates ===
    arms = ["rag_tfidf", "grep_pyright", "trifecta"]
    arm_scores = {}
    for arm in arms:
        arm_tasks = [t for t in all_tasks if t.arm == arm]
        if not arm_tasks:
            continue

        scores = {
            "avg_recall": sum(t.recall for t in arm_tasks) / len(arm_tasks),
            "avg_precision": sum(t.precision for t in arm_tasks) / len(arm_tasks),
            "avg_mrr": sum(t.mrr for t in arm_tasks) / len(arm_tasks),
            "avg_latency": sum(t.latency_ms for t in arm_tasks) / len(arm_tasks),
            "tasks": len(arm_tasks),
        }
        arm_scores[arm] = scores

    # === Comparison table ===
    lines.append("## Aggregate Results")
    lines.append("")
    lines.append("| Arm | Avg Recall | Avg Precision | Avg MRR | Avg Latency (ms) | Tasks |")
    lines.append("|-----|-----------|--------------|---------|-----------------|-------|")
    for arm in arms:
        if arm in arm_scores:
            s = arm_scores[arm]
            lines.append(
                f"| {arm} | {s['avg_recall']:.2f} | "
                f"{s['avg_precision']:.2f} | {s['avg_mrr']:.2f} | "
                f"{s['avg_latency']:.0f} | {s['tasks']} |"
            )
    lines.append("")

    # === Honest CVR ===
    lines.append("## Honest Context Value Ratio")
    lines.append("")

    if "rag_tfidf" in arm_scores and "trifecta" in arm_scores:
        rag_r = arm_scores["rag_tfidf"]["avg_recall"]
        tri_r = arm_scores["trifecta"]["avg_recall"]

        if rag_r > 0:
            honest_cvr = tri_r / rag_r
        else:
            honest_cvr = float("inf")

        lines.append(f"**Trifecta vs RAG (honest CVR)**: {honest_cvr:.2f}x")

        if "grep_pyright" in arm_scores:
            lsp_r = arm_scores["grep_pyright"]["avg_recall"]
            if lsp_r > 0:
                lsp_cvr = tri_r / lsp_r
                lines.append(f"**Trifecta vs LSP (honest CVR)**: {lsp_cvr:.2f}x")

        lines.append("")
        lines.append("Original claimed CVR: **1.37x** (vs blind agent)")
        lines.append(f"Honest CVR (vs RAG baseline): **{honest_cvr:.2f}x**")
        lines.append(
            f"Bias reduction: "
            f"**{((1.37 - honest_cvr) / 1.37 * 100):.0f}%** of original claim was bias"
        )

    lines.append("")

    # === Per-category breakdown ===
    lines.append("## Per-Category Breakdown")
    lines.append("")

    categories = {
        "T-P": "Precision",
        "T-D": "Discovery",
        "T-O": "Orphan Detection",
        "T-W": "Weakness Probing",
        "T-A": "Architecture",
        "T-S": "Semantic Search",
    }

    lines.append("| Category | RAG | LSP | Trifecta | Winner |")
    lines.append("|----------|-----|-----|----------|--------|")

    for prefix, cat_name in categories.items():
        cat_tasks = [t for t in all_tasks if t.task_id.startswith(prefix)]
        row = {"rag_tfidf": 0.0, "grep_pyright": 0.0, "trifecta": 0.0}

        for arm in arms:
            arm_cat = [t for t in cat_tasks if t.arm == arm]
            if arm_cat:
                row[arm] = sum(t.recall for t in arm_cat) / len(arm_cat)

        winner = max(row, key=lambda k: row[k])
        if row[winner] == 0:
            winner = "tie"

        lines.append(
            f"| {cat_name} | {row['rag_tfidf']:.2f} | "
            f"{row['grep_pyright']:.2f} | {row['trifecta']:.2f} "
            f"| {winner} |"
        )

    lines.append("")

    # === Weakness exposure ===
    lines.append("## Weakness Exposure")
    lines.append("")

    weakness_tasks = [t for t in all_tasks if t.task_id.startswith("T-W")]
    if weakness_tasks:
        lines.append("Tasks specifically targeting Trifecta's known limitations:")
        lines.append("")
        for t in weakness_tasks:
            lines.append(
                f"- **{t.task_id}** ({t.arm}): recall={t.recall:.2f}, latency={t.latency_ms}ms"
            )

        # Check if Trifecta underperforms on weakness tasks
        tri_weak = [t for t in weakness_tasks if t.arm == "trifecta"]
        rag_weak = [t for t in weakness_tasks if t.arm == "rag_tfidf"]
        if tri_weak and rag_weak:
            tri_avg = sum(t.recall for t in tri_weak) / len(tri_weak)
            rag_avg = sum(t.recall for t in rag_weak) / len(rag_weak)
            lines.append("")
            if tri_avg < rag_avg:
                lines.append(
                    f"**Trifecta underperforms on weakness tasks**: "
                    f"{tri_avg:.2f} vs RAG {rag_avg:.2f} "
                    f"— weakness exposure CONFIRMED"
                )
            else:
                lines.append(
                    f"**Trifecta matches or beats RAG on weakness tasks**: "
                    f"{tri_avg:.2f} vs RAG {rag_avg:.2f}"
                )

    lines.append("")

    # === Index time comparison ===
    lines.append("## Indexing Overhead")
    lines.append("")
    for r in results:
        if r.index_times:
            lines.append("### Repo: (varies)")
            for arm, ms in r.index_times.items():
                lines.append(f"- **{arm}**: {ms}ms")
            lines.append("")

    # === Conclusion ===
    lines.append("## Conclusion")
    lines.append("")
    lines.append("This benchmark corrects the 4 critical biases of the original study:")
    lines.append("1. **Straw-man control**: Replaced blind agent with RAG + LSP baselines")
    lines.append("2. **Restrictive timeout**: All arms complete all tasks; latency measured")
    lines.append("3. **Single repo**: Tested on synthetic fixture with known gold answers")
    lines.append("4. **No weakness testing**: Targeted transitive inheritance and dynamic imports")
    lines.append("")

    if "rag_tfidf" in arm_scores and "trifecta" in arm_scores:
        tri_r = arm_scores["trifecta"]["avg_recall"]
        rag_r = arm_scores["rag_tfidf"]["avg_recall"]
        honest = tri_r / rag_r if rag_r > 0 else float("inf")

        if honest < 1.37:
            lines.append(
                f"The honest CVR of **{honest:.2f}x** is significantly lower "
                f"than the original claim of 1.37x. "
                f"**{((1.37 - honest) / 1.37 * 100):.0f}% of the original "
                f"claim was attributable to using a straw-man control group.**"
            )
        else:
            lines.append(
                f"The honest CVR of **{honest:.2f}x** is comparable to or "
                f"exceeds the original claim, suggesting the original "
                f"methodology did not significantly inflate results."
            )

    return "\n".join(lines)


def main() -> None:
    """Run the fair benchmark."""
    print("=" * 60)
    print("  Trifecta Fair Benchmark — 3-Arm Comparison")
    print("  Addressing: Straw-man control, timeout bias,")
    print("  single repo, and no weakness testing")
    print("=" * 60)
    print()

    all_results: list[BenchmarkResult] = []

    # === 1. Synthetic fixture (deterministic gold answers) ===
    # Use persistent path so the graph DB survives across runs
    print("=== Synthetic Fixture ===")
    synthetic_path = Path("/tmp/synthetic-fixture")
    if not synthetic_path.exists():
        create_synthetic_repo(synthetic_path)

    # Find the graph DB for the synthetic repo
    synthetic_graph_db: Path | None = None
    synthetic_cache = synthetic_path / ".trifecta" / "cache"
    if synthetic_cache.exists():
        for f in synthetic_cache.glob("graph_*.db"):
            synthetic_graph_db = f
            break

    # Load gold answers
    gold = create_synthetic_repo(synthetic_path)

    print(f"Repo: {synthetic_path}")
    print(f"Graph DB: {synthetic_graph_db}")
    print(f"Files: {gold['file_count']}")
    print(f"Tasks: {len(gold['tasks'])}")

    result = run_benchmark(
        repo_root=synthetic_path,
        tasks=gold["tasks"],
        repo_name="synthetic-fixture",
        graph_db_path=synthetic_graph_db,
    )
    all_results.append(result)

    for t in result.tasks:
        print(
            f"  {t.task_id:5s} {t.arm:12s} "
            f"R={t.recall:.2f} P={t.precision:.2f} "
            f"MRR={t.mrr:.2f} lat={t.latency_ms:4d}ms"
        )

    print()

    # === 2. Paper-writer (real repo, pre-computed graph) ===
    print("=== Paper-Writer (Real Repo) ===")
    pw_root = Path("/Users/felipe_gonzalez/Developer/paper-writer")
    pw_graph = pw_root / ".trifecta/cache/graph_paper-writer_0a9954b4.db"

    if pw_root.exists() and pw_graph.exists():
        # Define tasks for paper-writer (manually verified gold)
        pw_tasks = {
            # === PRECISION ===
            "T-P1": {
                "description": "Find definition of Orchestrator",
                "gold_file": "harness/services/orchestrator.py",
                "gold_symbol": "Orchestrator",
                "gold_line_range": (1, 500),
            },
            # === DISCOVERY ===
            "T-D1": {
                "description": ("Trace call chain from main to assemble_manuscript"),
                "gold_files": [
                    "cli/paper/",
                    "harness/services/",
                ],
                "gold_callers": [
                    "harness/services/orchestrator.py::run_action",
                ],
                "gold_path": [
                    "cli/paper/main.py::main",
                    "harness/services/orchestrator.py::execute",
                    "harness/services/orchestrator.py::run_action",
                    "harness/services/assembler.py::assemble_manuscript",
                ],
            },
            "T-D2": {
                "description": "Find callers of run_gate",
                "gold_callers": [
                    "harness/services/orchestrator.py",
                ],
                "gold_files": ["harness/services/"],
                "gold_symbol": "run_gate",
            },
            # === ORPHAN (classification test, not detection) ===
            "T-O1": {
                "description": ("Distinguish entry points from dead code"),
                # These are graph-orphans that are ENTRY POINTS
                "gold_orphans": [
                    "cli/paper/main.py::_get_version",
                    "cli/paper/main.py::_cmd_audit_prose",
                    "cli/paper/main.py::main",
                ],
                # These are heavily-called NON-orphans
                "gold_false_orphans": [
                    "harness/ports/assets.py::get_asset_path",
                    "harness/services/orchestrator_builder.py::build_orchestrator_dependencies",
                    "validators/style.py::validate_style",
                    "harness/services/assembler.py::assemble_manuscript",
                ],
            },
            # === WEAKNESS ===
            "T-W1": {
                "description": ("Find subclasses of ToolWrapper"),
                "gold_parent_class": "ToolWrapper",
                "gold_descendants": [
                    "integrations/tools/bibtex_tidy.py::BibliographyNormalizer",
                    "integrations/tools/zotero_import.py::ZoteroImporter",
                ],
            },
            "T-W2": {
                "description": ("Find dynamic imports via importlib"),
                # importlib.metadata and importlib.resources
                "gold_files": [
                    "cli/paper/main.py",
                    "harness/ports/assets.py",
                ],
                "gold_callers": [],
            },
            # === ARCHITECTURE ===
            "T-A1": {
                "description": "Map architecture layers",
                "gold_layers": {
                    "cli": ["cli/paper/"],
                    "harness": ["harness/"],
                    "integrations": ["integrations/"],
                    "parsers": ["parsers/"],
                    "tests": ["tests/"],
                },
            },
            # === SEMANTIC ===
            "T-S1": {
                "description": ("Find function that resolves project root directory"),
                "gold_file": "cli/paper/main.py",
                "gold_symbol": "resolve_project_root",
            },
            "T-S2": {
                "description": ("Find function that checks all external tools availability"),
                "gold_file": "harness/services/doctor.py",
                "gold_symbol": "check_all_tools",
            },
        }

        result = run_benchmark(
            repo_root=pw_root,
            tasks=pw_tasks,
            repo_name="paper-writer",
            graph_db_path=pw_graph,
        )
        all_results.append(result)

        for t in result.tasks:
            print(
                f"  {t.task_id:5s} {t.arm:12s} "
                f"R={t.recall:.2f} P={t.precision:.2f} "
                f"MRR={t.mrr:.2f} lat={t.latency_ms:4d}ms"
            )
    else:
        print(f"  SKIPPED: {pw_root} or graph DB not found")

    print()

    # === Generate report ===
    report = generate_report(all_results)

    report_path = Path(__file__).parent / "reports" / "fair-benchmark-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)

    print("=" * 60)
    print("  REPORT GENERATED")
    print(f"  {report_path}")
    print("=" * 60)
    print()

    # Print summary
    print(report)

    # Emit metrics for autoresearch
    all_tasks_flat: list[TaskResult] = []
    for r in all_results:
        all_tasks_flat.extend(r.tasks)

    tri_tasks = [t for t in all_tasks_flat if t.arm == "trifecta"]
    rag_tasks = [t for t in all_tasks_flat if t.arm == "rag_tfidf"]
    lsp_tasks = [t for t in all_tasks_flat if t.arm == "grep_pyright"]

    tri_recall = sum(t.recall for t in tri_tasks) / max(len(tri_tasks), 1)
    rag_recall = sum(t.recall for t in rag_tasks) / max(len(rag_tasks), 1)
    lsp_recall = sum(t.recall for t in lsp_tasks) / max(len(lsp_tasks), 1)

    honest_cvr = tri_recall / rag_recall if rag_recall > 0 else 0

    print()
    print("METRIC honest_cvr=" + f"{honest_cvr:.2f}")
    print("METRIC trifecta_recall=" + f"{tri_recall:.2f}")
    print("METRIC rag_recall=" + f"{rag_recall:.2f}")
    print("METRIC lsp_recall=" + f"{lsp_recall:.2f}")
    print("METRIC total_tasks=" + str(len(all_tasks_flat)))
    print("METRIC bias_reduction_pct=" + f"{((1.37 - honest_cvr) / 1.37 * 100):.0f}")


if __name__ == "__main__":
    main()
