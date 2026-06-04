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
    Also performs dependency risk analysis (dead hubs: highly-connected
    orphaned symbols). Requires MCP_TRIFECTA_MODE=real to be useful.
    """

    from validators.code_health import (
        analyze_code_health,
        analyze_dependency_risk,
    )

    t0 = time.time()
    report = analyze_code_health()
    dep_report = analyze_dependency_risk()
    elapsed = int((time.time() - t0) * 1000)

    output = {
        "summary": report.summary(),
        "trifecta_enabled": report.trifecta_enabled,
        "actionable_count": len(report.findings),
        "filtered_count": report.filtered_count,
        "total_orphans_seen": report.total_orphans_seen,
        "dependency_risk_summary": dep_report.summary(),
        "dead_hub_count": len(dep_report.findings),
        "elapsed_ms": elapsed,
        "error": report.error or dep_report.error,
        "findings": [f.to_dict() for f in report.findings],
        "dead_hubs": [f.to_dict() for f in dep_report.findings],
    }

    if args.output == "json":
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(output["summary"])
        if report.findings:
            print()
            for finding in report.findings:
                print(f"  {finding.file_rel}::{finding.symbol_name} ({finding.orphan_type})")
        if dep_report.findings:
            print(f"\n{dep_report.summary()}")
            for hub in dep_report.findings:
                print(
                    f"  {hub.file_rel}::{hub.symbol_name} "
                    f"(in_degree={hub.in_degree}, {hub.risk_reason})"
                )
        if report.error or dep_report.error:
            err = report.error or dep_report.error
            print(f"  Note: {err}", file=sys.stderr)

    # Exit 1 if there are actionable findings, 0 otherwise
    sys.exit(1 if (report.findings or dep_report.findings) else 0)


def _cmd_audit_factuality(args: argparse.Namespace) -> None:
    """Audit claim-evidence factual accuracy via keyword overlap.

    Compares claim sentences against screened evidence abstracts.
    Claims with low overlap (<30%) are flagged as potential hallucinations.
    """
    from validators.claim_evidence import ClaimEvidenceValidator

    evidence_path = Path(args.evidence)
    if not evidence_path.exists():
        print(f"Error: evidence file not found: {evidence_path}", file=sys.stderr)
        sys.exit(1)

    manuscript_path = Path(args.file)
    if not manuscript_path.exists():
        print(f"Error: manuscript not found: {manuscript_path}", file=sys.stderr)
        sys.exit(1)

    validator = ClaimEvidenceValidator(
        evidence_path=evidence_path,
        overlap_threshold=getattr(args, "threshold", 0.30),
    )

    # Parse manuscript for claims
    from parsers.manuscript import ManuscriptParser
    parser = ManuscriptParser()
    manuscript = parser.parse(manuscript_path)

    t0 = time.time()
    findings = validator.validate(manuscript)
    elapsed = int((time.time() - t0) * 1000)

    output = {
        "command": "audit_factuality",
        "file": str(manuscript_path),
        "evidence_file": str(evidence_path),
        "overlap_threshold": validator.overlap_threshold,
        "findings_count": len(findings),
        "elapsed_ms": elapsed,
        "findings": findings,
    }

    if args.output == "json":
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"Claim-evidence factuality audit: {len(findings)} findings")
        if findings:
            for f in findings:
                ov = f["evidence"]["overlap_ratio"]
                print(f"  [{ov:.0%}] {f['evidence']['claim_snippet'][:80]}")

    sys.exit(1 if findings else 0)


def _cmd_audit_tables(args: argparse.Namespace) -> None:
    """Validate draft sections for required tables and figures.

    Checks for markdown tables and mermaid diagrams.
    """
    from validators.table_figure import validate_tables_figures

    draft_dir = Path(args.draft_dir)
    findings = validate_tables_figures(draft_dir)

    output = {
        "command": "audit_tables",
        "draft_dir": str(draft_dir),
        "findings_count": len(findings),
        "findings": findings,
    }

    if args.output == "json":
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        if findings:
            print(f"Table/figure validation: {len(findings)} issues")
            for f in findings:
                print(f"  [{f['severity']}] {f['rule_id']}: {f['message']}")
        else:
            print("Table/figure validation: all checks passed")

    sys.exit(1 if findings else 0)


def _cmd_audit_quality_appraisal(args: argparse.Namespace) -> None:
    """Run quality appraisal on screened evidence.

    Scores studies on 5 dimensions: venue, citations, methodology,
    reproducibility, recency.
    """
    from validators.quality_appraisal import QualityAppraisalValidator

    evidence_path = Path(args.evidence)
    if not evidence_path.exists():
        print(f"Error: evidence file not found: {evidence_path}", file=sys.stderr)
        sys.exit(1)

    validator = QualityAppraisalValidator()
    evidence_data = json.loads(evidence_path.read_text(encoding="utf-8"))
    papers = evidence_data.get("evidence", [])

    t0 = time.time()
    findings = validator.validate(papers)
    elapsed = int((time.time() - t0) * 1000)

    output = {
        "command": "audit_quality_appraisal",
        "total_appraised": len(papers),
        "findings_count": len(findings),
        "elapsed_ms": elapsed,
        "findings": [f if isinstance(f, dict) else str(f) for f in findings],
    }

    if args.output == "json":
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"Quality appraisal: {len(papers)} studies, {len(findings)} findings")
        for f in findings:
            if isinstance(f, dict):
                print(f"  [{f.get('severity', '?')}] {f.get('rule_id', '?')}")

    sys.exit(1 if findings else 0)
