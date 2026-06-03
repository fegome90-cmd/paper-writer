"""Audit subcommand handlers for paper CLI."""
import argparse
import json
import sys
import time
from pathlib import Path


def _cmd_audit_prose(args: argparse.Namespace) -> None:
    """Run prose analysis (Phase 0)."""
    from engine.formatter import format_terminal
    from parsers.manuscript import ManuscriptParser
    from validators.prose import ProseValidator

    path = Path(args.file)
    if not path.is_file():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    t0 = time.time()
    manuscript = ManuscriptParser().parse(path)
    validator = ProseValidator(whitelist=set(args.whitelist or []))
    findings = validator.validate(manuscript)
    elapsed = int((time.time() - t0) * 1000)

    by_sev: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0}
    by_cat: dict[str, int] = {}
    for f in findings:
        sev = f.get("severity", "P2")
        by_sev[sev] = by_sev.get(sev, 0) + 1
        rg = f.get("rule_id", "").rsplit(".", 1)[0]
        by_cat[rg] = by_cat.get(rg, 0) + 1

    result = {
        "command": "audit_prose",
        "file": str(path),
        "format": manuscript.format,
        "findings": findings,
        "summary": {
            "total_findings": len(findings),
            "by_severity": by_sev,
            "by_category": by_cat,
        },
        "metadata": {
            "parser_version": "1.0",
            "rules_loaded": validator.rules_count,
            "rules_enabled": validator.rules_count,
            "execution_time_ms": elapsed,
        },
    }

    # Validate key fields against expected schema
    required_keys = {"command", "file", "findings", "summary", "metadata"}
    missing = required_keys - set(result.keys())
    if missing:
        print(f"Warning: result missing schema fields: {missing}", file=sys.stderr)

    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_terminal(findings))


def _cmd_audit_claims(args: argparse.Namespace) -> None:
    """Run claim candidate detection (Phase 0)."""

    from parsers.manuscript import ManuscriptParser
    from validators.claims import ClaimsValidator, build_claims_report

    path = Path(args.file)
    if not path.is_file():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    t0 = time.time()
    manuscript = ManuscriptParser().parse(path)
    validator = ClaimsValidator(whitelist=set(args.whitelist or []))
    candidates = validator.validate(manuscript)
    elapsed = int((time.time() - t0) * 1000)

    result = build_claims_report(manuscript, candidates, elapsed, rules_loaded=len(validator.rules))

    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        from engine.formatter import format_claims_output

        print(format_claims_output(result))


def _cmd_audit_citations(args: argparse.Namespace) -> None:
    """Verify citations against Crossref + Semantic Scholar."""

    from engine.formatter import format_terminal
    from parsers.manuscript import ManuscriptParser
    from validators.citation_verify import CitationVerifyValidator

    path = Path(args.file)
    if not path.is_file():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    t0 = time.time()
    manuscript = ManuscriptParser().parse(path)
    validator = CitationVerifyValidator(offline=args.offline)
    findings = validator.validate(manuscript)
    elapsed = int((time.time() - t0) * 1000)

    by_sev: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0}
    for f in findings:
        sev = f.get("severity", "P2")
        by_sev[sev] = by_sev.get(sev, 0) + 1

    result = {
        "command": "audit_citations",
        "file": str(path),
        "format": manuscript.format,
        "findings": findings,
        "summary": {
            "total_findings": len(findings),
            "by_severity": by_sev,
        },
        "metadata": {
            "parser_version": "1.0",
            "offline": args.offline,
            "execution_time_ms": elapsed,
        },
    }

    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_terminal(findings))

    if any(f.get("severity") == "P0" for f in findings):
        sys.exit(1)


def _cmd_audit_ethics(args: argparse.Namespace) -> None:
    """Check AI disclosure compliance."""

    from engine.formatter import format_terminal
    from parsers.manuscript import ManuscriptParser
    from validators.ethics import EthicsValidator

    path = Path(args.file)
    if not path.is_file():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    t0 = time.time()
    manuscript = ManuscriptParser().parse(path)
    validator = EthicsValidator()
    findings = validator.validate(manuscript)
    elapsed = int((time.time() - t0) * 1000)

    result = {
        "command": "audit_ethics",
        "file": str(path),
        "format": manuscript.format,
        "findings": findings,
        "summary": {
            "total_findings": len(findings),
        },
        "metadata": {
            "parser_version": "1.0",
            "execution_time_ms": elapsed,
        },
    }

    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_terminal(findings))

    if any(f.get("severity") == "P0" for f in findings):
        sys.exit(1)


def _cmd_audit_writing_quality(args: argparse.Namespace) -> None:
    """Detect AI-typical writing patterns."""

    from engine.formatter import format_terminal
    from parsers.manuscript import ManuscriptParser
    from validators.writing_quality import WritingQualityValidator

    path = Path(args.file)
    if not path.is_file():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    t0 = time.time()
    manuscript = ManuscriptParser().parse(path)
    validator = WritingQualityValidator(whitelist=set(args.whitelist or []))
    findings = validator.validate(manuscript)
    elapsed = int((time.time() - t0) * 1000)

    by_sev: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0}
    for f in findings:
        sev = f.get("severity", "P2")
        by_sev[sev] = by_sev.get(sev, 0) + 1

    result = {
        "command": "audit_writing_quality",
        "file": str(path),
        "format": manuscript.format,
        "findings": findings,
        "summary": {
            "total_findings": len(findings),
            "by_severity": by_sev,
        },
        "metadata": {
            "parser_version": "1.0",
            "rules_loaded": len(validator.rules),
            "execution_time_ms": elapsed,
        },
    }

    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_terminal(findings))

    # Fail-closed: exit code 1 if P0 findings
    if any(f.get("severity") == "P0" for f in findings):
        sys.exit(1)



def _cmd_audit_code_health(args: argparse.Namespace) -> None:
    """Run code health audit using Trifecta graph index.

    Finds actionable dead code / orphan methods in the project, filtering
    out known false positives (tests, mixin inheritance, CLI dispatch).
    Requires MCP_TRIFECTA_MODE=real to be useful.
    """

    from validators.code_health import analyze_code_health

    t0 = time.time()
    report = analyze_code_health()
    elapsed = int((time.time() - t0) * 1000)

    output = {
        "summary": report.summary(),
        "trifecta_enabled": report.trifecta_enabled,
        "actionable_count": len(report.findings),
        "filtered_count": report.filtered_count,
        "total_orphans_seen": report.total_orphans_seen,
        "elapsed_ms": elapsed,
        "error": report.error,
        "findings": [f.to_dict() for f in report.findings],
    }

    if args.output == "json":
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(output["summary"])
        if report.findings:
            print()
            for finding in report.findings:
                print(f"  {finding.file_rel}::{finding.symbol_name} ({finding.orphan_type})")
        if report.error:
            print(f"  Note: {report.error}", file=sys.stderr)

    # Exit 1 if there are actionable findings, 0 otherwise
    sys.exit(1 if report.findings else 0)


