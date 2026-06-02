"""
Synthetic fixture repo for deterministic benchmark validation.
Known gold answers, controlled complexity, intentional patterns.
"""

import textwrap
from pathlib import Path


def create_synthetic_repo(base_dir: Path) -> dict:
    """
    Create a synthetic Python repo with known structure.
    Returns gold answer dict for benchmark tasks.
    """
    base_dir.mkdir(parents=True, exist_ok=True)

    # === core/engine.py — main processing pipeline ===
    (base_dir / "core").mkdir(exist_ok=True)
    (base_dir / "core" / "__init__.py").write_text("from core.engine import DataProcessor\n")
    (base_dir / "core" / "engine.py").write_text(
        textwrap.dedent('''\
        """Core data processing engine."""

        from core.transforms import normalize, validate
        from core.output import format_result
        from typing import Optional


        class DataProcessor:
            """Main processor for data pipeline."""

            def __init__(self, config: dict):
                self.config = config
                self._cache: dict = {}

            def process(self, data: list[dict]) -> list[dict]:
                """Process raw data through the pipeline."""
                validated = [validate(item) for item in data]
                normalized = [normalize(item, self.config) for item in validated]
                results = [self._transform(item) for item in normalized]
                return [format_result(r) for r in results]

            def _transform(self, item: dict) -> dict:
                """Internal transformation step."""
                key = item.get("id", "unknown")
                if key in self._cache:
                    return self._cache[key]
                result = {**item, "processed": True}
                self._cache[key] = result
                return result

            def clear_cache(self) -> None:
                """Clear the internal cache."""
                self._cache.clear()


        def build_processor(config_path: str) -> DataProcessor:
            """Factory function to create a DataProcessor from config file."""
            config = {"source": config_path, "mode": "standard"}
            return DataProcessor(config)


        def legacy_process(data: list[dict]) -> list[dict]:
            """Legacy processing function — deprecated, use DataProcessor.process instead."""
            return [normalize(item, {}) for item in data]
    ''')
    )

    # === core/transforms.py — transformation functions ===
    (base_dir / "core" / "transforms.py").write_text(
        textwrap.dedent('''\
        """Data transformation functions."""

        from typing import Any


        def normalize(item: dict, config: dict) -> dict:
            """Normalize a data item according to config."""
            normalized = {}
            for key, value in item.items():
                if isinstance(value, str):
                    normalized[key] = value.strip().lower()
                else:
                    normalized[key] = value
            return normalized


        def validate(item: dict) -> dict:
            """Validate a data item has required fields."""
            required = ["id", "name"]
            missing = [f for f in required if f not in item]
            if missing:
                raise ValueError(f"Missing required fields: {missing}")
            return item


        def enrich(item: dict, extra: dict) -> dict:
            """Add extra fields to a data item."""
            return {**item, **extra}


        def deduplicate(items: list[dict], key: str = "id") -> list[dict]:
            """Remove duplicates from a list of items."""
            seen: set[Any] = set()
            result = []
            for item in items:
                if item.get(key) not in seen:
                    seen.add(item.get(key))
                    result.append(item)
            return result
    ''')
    )

    # === core/output.py — output formatting ===
    (base_dir / "core" / "output.py").write_text(
        textwrap.dedent('''\
        """Output formatting functions."""

        import json


        def format_result(item: dict) -> dict:
            """Format a processed result for output."""
            return {
                "id": item.get("id"),
                "data": json.dumps(item, default=str),
                "status": "complete",
            }


        def format_batch(items: list[dict]) -> str:
            """Format a batch of results as JSON lines."""
            lines = [json.dumps(format_result(item)) for item in items]
            return "\\n".join(lines)


        def write_output(items: list[dict], path: str) -> None:
            """Write formatted results to a file."""
            with open(path, "w") as f:
                f.write(format_batch(items))
    ''')
    )

    # === core/base.py — base classes (for inheritance testing) ===
    (base_dir / "core" / "base.py").write_text(
        textwrap.dedent('''\
        """Base classes for the processing pipeline."""

        from abc import ABC, abstractmethod
        from typing import Any


        class BaseTransformer(ABC):
            """Abstract base class for transformers."""

            @abstractmethod
            def transform(self, item: dict) -> dict:
                ...

            def validate_input(self, item: dict) -> bool:
                """Check if input is valid for transformation."""
                return isinstance(item, dict) and "id" in item


        class BaseValidator(ABC):
            """Abstract base class for validators."""

            @abstractmethod
            def validate(self, item: dict) -> bool:
                ...

            def get_errors(self, item: dict) -> list[str]:
                """Get validation errors for an item."""
                if not self.validate(item):
                    return ["Validation failed"]
                return []


        class LoggingMixin:
            """Mixin that adds logging capability."""

            def log(self, message: str) -> None:
                """Log a message."""
                print(f"[{self.__class__.__name__}] {message}")
    ''')
    )

    # === plugins/advanced.py — extends base classes (3-level inheritance) ===
    (base_dir / "plugins").mkdir(exist_ok=True)
    (base_dir / "plugins" / "__init__.py").write_text("")
    (base_dir / "plugins" / "advanced.py").write_text(
        textwrap.dedent('''\
        """Advanced processing plugins."""

        import importlib
        from core.base import BaseTransformer, BaseValidator, LoggingMixin
        from typing import Any


        class AdvancedTransformer(BaseTransformer, LoggingMixin):
            """Transformer with advanced features."""

            def __init__(self, rules: dict):
                self.rules = rules

            def transform(self, item: dict) -> dict:
                self.log(f"Transforming item {item.get('id')}")
                result = {}
                for key, rule in self.rules.items():
                    if key in item:
                        result[key] = rule(item[key])
                return result


        class StrictValidator(BaseValidator):
            """Validator that checks all fields strictly."""

            def __init__(self, required_fields: list[str]):
                self.required_fields = required_fields

            def validate(self, item: dict) -> bool:
                return all(f in item for f in self.required_fields)


        class CachedTransformer(AdvancedTransformer):
            """Transformer with caching — 3 levels of inheritance:
            BaseTransformer -> AdvancedTransformer -> CachedTransformer"""

            def __init__(self, rules: dict, max_size: int = 100):
                super().__init__(rules)
                self._cache: dict[str, dict] = {}
                self._max_size = max_size

            def transform(self, item: dict) -> dict:
                key = str(item.get("id"))
                if key in self._cache:
                    return self._cache[key]
                result = super().transform(item)
                if len(self._cache) >= self._max_size:
                    self._cache.clear()
                self._cache[key] = result
                return result


        def load_plugin(module_name: str) -> Any:
            """Dynamically load a plugin module — IMPORTLIB usage."""
            return importlib.import_module(module_name)
    ''')
    )

    # === cli/main.py — entry point ===
    (base_dir / "cli").mkdir(exist_ok=True)
    (base_dir / "cli" / "__init__.py").write_text("")
    (base_dir / "cli" / "main.py").write_text(
        textwrap.dedent('''\
        """CLI entry point for the processing pipeline."""

        import argparse
        import sys

        from core.engine import build_processor, legacy_process


        def main(argv: list[str] | None = None) -> int:
            """Main CLI entry point."""
            parser = argparse.ArgumentParser(description="Data processor")
            parser.add_argument("--config", required=True, help="Config file path")
            parser.add_argument("--input", required=True, help="Input data file")
            parser.add_argument("--output", help="Output file path")
            parser.add_argument("--legacy", action="store_true", help="Use legacy processor")
            args = parser.parse_args(argv)

            import json
            with open(args.input) as f:
                data = json.load(f)

            if args.legacy:
                results = legacy_process(data)
            else:
                processor = build_processor(args.config)
                results = processor.process(data)

            if args.output:
                from core.output import write_output
                write_output(results, args.output)
            else:
                for r in results:
                    print(r)

            return 0


        if __name__ == "__main__":
            sys.exit(main())
    ''')
    )

    # === utils/helpers.py — standalone utility functions ===
    (base_dir / "utils").mkdir(exist_ok=True)
    (base_dir / "utils" / "__init__.py").write_text("")
    (base_dir / "utils" / "helpers.py").write_text(
        textwrap.dedent('''\
        """Standalone utility functions — some are ORPHANS (no callers)."""

        from typing import Any


        def slugify(text: str) -> str:
            """Convert text to URL-friendly slug."""
            return text.lower().replace(" ", "-").replace("_", "-")


        def truncate(text: str, max_length: int = 100) -> str:
            """Truncate text to max length with ellipsis."""
            if len(text) <= max_length:
                return text
            return text[:max_length - 3] + "..."


        def safe_get(data: dict, path: str, default: Any = None) -> Any:
            """Safely get nested dict value using dot notation."""
            keys = path.split(".")
            current = data
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            return current


        # ORPHAN FUNCTIONS — no callers anywhere in the codebase
        def fibonacci(n: int) -> int:
            """Calculate nth Fibonacci number. UNUSED."""
            if n <= 1:
                return n
            return fibonacci(n - 1) + fibonacci(n - 2)


        def rot13(text: str) -> str:
            """Apply ROT13 cipher. UNUSED."""
            result = []
            for c in text:
                if "a" <= c <= "z":
                    result.append(chr((ord(c) - ord("a") + 13) % 26 + ord("a")))
                elif "A" <= c <= "Z":
                    result.append(chr((ord(c) - ord("A") + 13) % 26 + ord("A")))
                else:
                    result.append(c)
            return "".join(result)


        def xml_to_dict(xml_string: str) -> dict:
            """Convert simple XML to dict. UNUSED."""
            # Simplified — not production ready
            import re
            result = {}
            for match in re.finditer(r"<(\\w+)>([^<]*)</\\1>", xml_string):
                result[match.group(1)] = match.group(2)
            return result
    ''')
    )

    # === tests/test_pipeline.py ===
    (base_dir / "tests").mkdir(exist_ok=True)
    (base_dir / "tests" / "__init__.py").write_text("")
    (base_dir / "tests" / "test_pipeline.py").write_text(
        textwrap.dedent('''\
        """Tests for the processing pipeline."""

        import pytest
        from core.engine import DataProcessor, build_processor, legacy_process
        from core.transforms import normalize, validate, enrich, deduplicate
        from core.output import format_result, format_batch
        from core.base import BaseTransformer, BaseValidator


        class TestDataProcessor:
            def test_process_basic(self):
                proc = DataProcessor({"mode": "standard"})
                data = [{"id": 1, "name": "Test"}]
                result = proc.process(data)
                assert len(result) == 1
                assert result[0]["status"] == "complete"

            def test_clear_cache(self):
                proc = DataProcessor({})
                proc._cache = {"a": 1}
                proc.clear_cache()
                assert proc._cache == {}


        class TestTransforms:
            def test_normalize(self):
                assert normalize({"k": "  HELLO  "}, {}) == {"k": "hello"}

            def test_validate_missing(self):
                with pytest.raises(ValueError):
                    validate({"id": 1})

            def test_deduplicate(self):
                items = [{"id": 1}, {"id": 2}, {"id": 1}]
                assert len(deduplicate(items)) == 2
    ''')
    )

    # === pyproject.toml ===
    (base_dir / "pyproject.toml").write_text(
        textwrap.dedent("""\
        [project]
        name = "synthetic-fixture"
        version = "0.1.0"
        requires-python = ">=3.11"
    """)
    )

    # Return gold answers for benchmark tasks
    return {
        "repo_root": str(base_dir),
        "file_count": 15,
        "node_counts": {
            "function": 20,  # approximate
            "class": 8,
            "method": 12,
        },
        "tasks": {
            # === PRECISION TASKS ===
            "T-P1": {
                "description": "Find the definition of process method",
                "gold_file": "core/engine.py",
                "gold_line_range": (14, 18),
                "gold_symbol": "process",
            },
            "T-P2": {
                "description": "Find the definition of normalize function",
                "gold_file": "core/transforms.py",
                "gold_line_range": (7, 14),
                "gold_symbol": "normalize",
            },
            # === DISCOVERY TASKS ===
            "T-D1": {
                "description": "Trace the call chain from main() to format_result",
                "gold_path": [
                    "cli/main.py::main",
                    "core/engine.py::build_processor",
                    "core/engine.py::DataProcessor.process",
                    "core/output.py::format_result",
                ],
                "gold_files": ["cli/main.py", "core/engine.py", "core/output.py"],
            },
            "T-D2": {
                "description": "Find all callers of normalize()",
                "gold_callers": [
                    "core/engine.py::DataProcessor.process",
                    "core/engine.py::legacy_process",
                ],
                "gold_file": "core/transforms.py",
                "gold_symbol": "normalize",
            },
            # === ORPHAN TASKS ===
            "T-O1": {
                "description": (
                    "Find all functions with zero callers"
                ),
                # True orphans: never called from anywhere
                "gold_orphans": [
                    "utils/helpers.py::rot13",
                    "utils/helpers.py::xml_to_dict",
                ],
                # fibonacci is recursive (self-edge), NOT an orphan
                "gold_non_orphans": [
                    "utils/helpers.py::fibonacci",
                ],
                "gold_false_orphans": [
                    # These ARE called — should NOT appear
                    "core/transforms.py::enrich",
                    "utils/helpers.py::slugify",
                ],
            },
            # === WEAKNESS TASKS ===
            "T-W1": {
                "description": "Find all descendants of BaseTransformer (including transitive)",
                "gold_parent_class": "BaseTransformer",
                "gold_descendants": [
                    "plugins/advanced.py::AdvancedTransformer",  # direct
                    "plugins/advanced.py::CachedTransformer",  # transitive
                ],
                "note": "Trifecta only resolves direct inheritance — should MISS CachedTransformer",
            },
            "T-W2": {
                "description": "Find what load_plugin() dynamically imports",
                "gold_dynamic_imports": "unknown_at_static_time",
                "note": "Trifecta is blind to importlib",
            },
            "T-W3": {
                "description": "CachedTransformer inherits from BaseTransformer?",
                "gold_answer": True,
                "gold_depth": 2,  # CachedTransformer -> AdvancedTransformer -> BaseTransformer
                "note": "Requires transitive inheritance resolution",
            },
            # === ARCHITECTURE TASKS ===
            "T-A1": {
                "description": "Map the architecture layers of this codebase",
                "gold_layers": {
                    "cli": ["cli/main.py"],
                    "core": [
                        "core/engine.py",
                        "core/transforms.py",
                        "core/output.py",
                        "core/base.py",
                    ],
                    "plugins": ["plugins/advanced.py"],
                    "utils": ["utils/helpers.py"],
                    "tests": ["tests/test_pipeline.py"],
                },
            },
            # === SEMANTIC TASKS ===
            "T-S1": {
                "description": "Find the function that removes duplicate items",
                "gold_file": "core/transforms.py",
                "gold_symbol": "deduplicate",
                "note": "Low lexical overlap — 'remove duplicates' vs 'deduplicate'",
            },
            "T-S2": {
                "description": "Find the function that creates a slug from text",
                "gold_file": "utils/helpers.py",
                "gold_symbol": "slugify",
                "note": "'create a slug' vs 'slugify' — needs synonym understanding",
            },
        },
    }


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        gold = create_synthetic_repo(Path(tmp) / "synthetic-fixture")
        print(f"Created repo at {gold['repo_root']}")
        print(f"Files: {gold['file_count']}")
        print(f"Tasks: {len(gold['tasks'])}")
        for tid, task in gold["tasks"].items():
            print(f"  {tid}: {task['description'][:60]}...")
