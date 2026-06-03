"""Gate subcommand handlers for paper CLI."""
import argparse
import json
import sys
import time
from pathlib import Path


def _cmd_gate_method(args: argparse.Namespace) -> None:
    """Run methodological gate (Phase 0)."""
    from engine.formatter import format_gate_result
    from parsers.manuscript import ManuscriptParser
    from validators.method_gate import MethodGateValidator

    path = Path(args.file)
    if not path.is_file():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    t0 = time.time()
    manuscript = ManuscriptParser().parse(path)
    validator = MethodGateValidator()
    result = validator.validate(
        manuscript=manuscript,
        study_type=args.study_type,
        checklist_name=args.checklist,
        na_items=args.na,
    )
    elapsed = int((time.time() - t0) * 1000)
    result["metadata"]["execution_time_ms"] = elapsed

    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_gate_result(result))

    # Fail-closed: exit code 1 if gate blocked
    if not result.get("gate_passed", True):
        sys.exit(1)


