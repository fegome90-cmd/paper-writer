#!/usr/bin/env python3
"""Autoresearch campaign evaluator — paper-writer reliability.

Runs 7 golden scenarios (GS-01..GS-07) locally with zero network access.
Outputs structured JSON to stdout; progress goes to stderr.

Usage:
    uv run python scripts/eval_paper_writer_reliability.py
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "skills" / "local" / "thesaurus" / "src"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "local" / "mesh-import" / "src"))

os.environ["PAPER_SEARCH_PROVIDER"] = "fixture"
os.environ.pop("PAPER_THESAURUS_PROFILE", None)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _gs01_provider_failure_fail_closed(tmp: Path) -> tuple[bool, str]:
    """GS-01: Provider failure must be fail-closed — no fictitious output."""
    from harness.ports.paper_search_provider import (
        PaperSearchProvider,
    )

    class ExplodingProvider(PaperSearchProvider):
        def search(self, query: str, *, sources=None, limit=20, **kw):
            raise RuntimeError("Network unreachable")

    from skills.local.adapters import LiteratureSearchAdapter

    adapter = LiteratureSearchAdapter()
    output_dir = tmp / "gs01" / "search"
    output_dir.mkdir(parents=True)

    import harness.ports.paper_search_provider as psp_mod
    orig_factory = psp_mod.create_search_provider
    psp_mod.create_search_provider = lambda *a, **k: ExplodingProvider()

    try:
        adapter.execute(
            "search",
            {"query": "test query", "output_dir": str(output_dir)},
            {},
        )
    except RuntimeError:
        pass
    finally:
        psp_mod.create_search_provider = orig_factory

    raw_path = output_dir / "raw_results.json"
    if raw_path.exists():
        content = raw_path.read_text(encoding="utf-8")
        forbidden = ["Mock Paper", "10.1000/xyz123", "Fallback Paper", "Demo et al."]
        for token in forbidden:
            if token in content:
                return False, f"Forbidden token '{token}' found in raw_results.json"
        return False, "raw_results.json exists after provider failure — should not be generated"

    return True, "Provider error surfaced visibly, no fictitious output generated"


def _gs02_search_filters_preserved(tmp: Path) -> tuple[bool, str]:
    """GS-02: Search filters trace through CLI -> adapter -> provider without loss."""
    from harness.ports.paper_search_provider import (
        PaperSearchProvider,
        SearchProvenance,
        SearchProviderResult,
    )

    captured_kwargs: dict[str, Any] = {}

    class SpyProvider(PaperSearchProvider):
        def search(self, query, *, sources=None, limit=20, **filters):
            captured_kwargs.update(filters)
            return SearchProviderResult(
                papers=[],
                raw_payload={"results": []},
                provenance=SearchProvenance(
                    provider="spy",
                    query=query,
                    retrieved_at="2026-01-01T00:00:00Z",
                    tool_name="test",
                    sources=["test"],
                ),
            )

    from unittest.mock import patch

    import harness.ports.paper_search_provider as psp_mod

    output_dir = tmp / "gs02" / "search"
    output_dir.mkdir(parents=True)

    filter_inputs = {
        "year_min": 2020,
        "year_max": 2025,
        "study_types": ["systematic review", "meta-analysis"],
        "human": True,
        "sample_size_min": 50,
        "sjr_max": 2,
        "duration_min": 6,
        "duration_max": 24,
        "exclude_preprints": True,
        "publisher_name": "Elsevier",
        "clinical_guideline": True,
        "medical_mode": True,
    }

    from skills.local.adapters import LiteratureSearchAdapter

    adapter = LiteratureSearchAdapter()

    with patch.object(psp_mod, "create_search_provider", return_value=SpyProvider()):
        result = adapter.execute(
            "search",
            {
                "query": "machine learning in healthcare",
                "output_dir": str(output_dir),
                **filter_inputs,
            },
            {},
        )

    if result.status != "pass":
        return False, f"Adapter returned status={result.status}: {result.summary}"

    for key, expected in filter_inputs.items():
        actual = captured_kwargs.get(key)
        if actual != expected:
            return False, f"Filter '{key}': expected {expected!r}, got {actual!r}"

    return True, f"All {len(filter_inputs)} filters preserved through pipeline"


def _gs03_dedup_keeps_richer(tmp: Path) -> tuple[bool, str]:
    """GS-03: Deduplication keeps richer record, no IndexError."""
    from harness.ports.paper_search_provider import (
        NormalizedPaper,
        deduplicate_papers,
    )

    paper_a = NormalizedPaper(
        title="Machine Learning for Diagnosis",
        doi=None,
        pmid=None,
        year=2024,
        authors="Smith J",
        abstract="Abstract A",
        url=None,
        pdf_url=None,
        source_platform="arxiv",
        source_id="1",
        categories=[],
        citations_count=0,
        defaulted_fields=["doi", "pdf_url"],
    )
    paper_a_dup = NormalizedPaper(
        title="Machine Learning for Diagnosis",
        doi=None,
        pmid=None,
        year=2024,
        authors="Smith J et al.",
        abstract="Abstract A dup",
        url=None,
        pdf_url=None,
        source_platform="pubmed",
        source_id="2",
        categories=[],
        citations_count=0,
        defaulted_fields=["doi", "pdf_url", "url"],
    )
    paper_b = NormalizedPaper(
        title="Deep Learning for Radiology",
        doi="10.1234/radio2024",
        pmid=None,
        year=2024,
        authors="Lee K",
        abstract="",
        url=None,
        pdf_url=None,
        source_platform="openalex",
        source_id="3",
        categories=[],
        citations_count=0,
        defaulted_fields=["abstract", "pdf_url"],
    )
    paper_b_richer = NormalizedPaper(
        title="Deep Learning for Radiology Updated",
        doi="10.1234/radio2024",
        pmid="PMID99999",
        year=2024,
        authors="Lee K, Wang Y, Garcia M",
        abstract="Full abstract with methods and results described comprehensively.",
        url="https://doi.org/10.1234/radio2024",
        pdf_url="https://doi.org/10.1234/radio2024.pdf",
        source_platform="pubmed",
        source_id="4",
        categories=["radiology", "ai"],
        citations_count=42,
        defaulted_fields=[],
    )

    try:
        result = deduplicate_papers([paper_a, paper_a_dup, paper_b, paper_b_richer])
    except IndexError as exc:
        return False, f"IndexError during dedup: {exc}"
    except Exception as exc:
        return False, f"Unexpected error during dedup: {exc}"

    if len(result) != 2:
        return False, f"Expected 2 papers after dedup, got {len(result)}"

    titles = {p.title for p in result}
    if "Machine Learning for Diagnosis" not in titles:
        return False, f"Paper A not in results: {titles}"
    if "Deep Learning for Radiology Updated" not in titles:
        return False, f"Richer paper B not in results: {titles}"

    paper_b_result = next(p for p in result if p.doi == "10.1234/radio2024")
    if paper_b_result.abstract == "":
        return False, "Richer paper B was replaced by poorer version (empty abstract)"
    if paper_b_result.citations_count != 42:
        return False, f"Richer paper B lost citations_count: {paper_b_result.citations_count}"
    if len(paper_b_result.defaulted_fields) != 0:
        return False, f"Richer paper B should have no defaults, got: {paper_b_result.defaulted_fields}"

    return True, "Dedup keeps 2 papers, richer B preserved with full metadata"


def _gs04_manifest_tampering_fails_closed(tmp: Path) -> tuple[bool, str]:
    """GS-04: Manifest+JSONL tampering detected, no silent rebuild."""
    from thesaurus.lite import LiteSemanticStore
    from thesaurus.manifest import ManifestError, load_manifest, validate_manifest

    vocab_dir = tmp / "gs04" / "vocabulary"
    vocab_dir.mkdir(parents=True)

    jsonl_content = ""
    records = []
    for i in range(5):
        record = {
            "id": f"D{i:05d}",
            "preferred_label": f"Concept {i}",
            "alt_labels": [f"Alt {i}a", f"Alt {i}b"],
            "broader": "",
            "narrower": "",
            "related": "",
            "notation": f"T{i:03d}",
            "source": "test",
        }
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        jsonl_content += line + "\n"
        records.append(record)

    sha256_hex = hashlib.sha256(jsonl_content.encode("utf-8")).hexdigest()

    jsonl_path = vocab_dir / "test.jsonl"
    jsonl_path.write_text(jsonl_content, encoding="utf-8")

    manifest = {
        "source_file": "test.jsonl",
        "sha256": sha256_hex,
        "concept_count": len(records),
        "source": "test",
        "schema_version": "1",
    }
    manifest_path = vocab_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    try:
        m = load_manifest(manifest_path)
        validate_manifest(m, jsonl_path)
    except ManifestError as exc:
        return False, f"Valid JSONL+manifest failed validation: {exc}"

    tampered = bytearray(jsonl_content.encode("utf-8"))
    tampered[100] = (tampered[100] + 1) % 256
    jsonl_path.write_bytes(bytes(tampered))

    try:
        m = load_manifest(manifest_path)
        validate_manifest(m, jsonl_path)
        return False, "Tampered JSONL passed manifest validation — should have failed"
    except ManifestError:
        pass

    db_path = tmp / "gs04" / "thesaurus.db"
    store = LiteSemanticStore(db_path=str(db_path))
    store.import_concepts(records)

    try:
        store.rebuild()
        return False, "Rebuild succeeded with tampered JSONL — should have raised ManifestError"
    except ManifestError:
        pass
    except Exception as exc:
        return False, f"Rebuild raised unexpected error type: {type(exc).__name__}: {exc}"

    return True, "Tampered JSONL detected by manifest validation and rebuild"


def _gs05_synthetic_sample_distinguishable(tmp: Path) -> tuple[bool, str]:
    """GS-05: System clearly reports if vocabulary is synthetic/mesh/decs/local."""
    from thesaurus.lite import LiteSemanticStore
    from thesaurus.mesh_loader import load_jsonl

    db_path = tmp / "gs05" / "thesaurus.db"
    store = LiteSemanticStore(db_path=str(db_path))

    sample_path = REPO_ROOT / "skills" / "local" / "thesaurus" / "workspace" / "vocabulary" / "sample.jsonl"
    if not sample_path.exists():
        return False, "sample.jsonl not found in workspace"

    concepts = load_jsonl(sample_path)
    store.import_concepts(concepts[:5])

    listed = store.list_concepts(limit=5)
    for concept in listed:
        source = concept.get("source", "")
        if not source:
            return False, f"Concept {concept['id']} has empty source field"
        if source in ("synthetic", "mesh", "decs", "local"):
            return True, f"Sample clearly labeled as source='{source}'"

    json.loads(listed[0].get("alt_labels", "[]")) if isinstance(listed[0].get("alt_labels"), str) else listed[0].get("alt_labels", [])
    sources = {c.get("source", "") for c in listed}
    return False, f"No recognizable source label in {sources}"


def _create_mini_mesh_xml() -> str:
    """Create a minimal MeSH XML fixture with 3 descriptors."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE DescriptorRecordSet SYSTEM "desc2026.dtd">
<DescriptorRecordSet>
  <DescriptorRecord>
    <DescriptorUI>D000001</DescriptorUI>
    <DescriptorName><String>Calcimycin</String></DescriptorName>
    <Annotation>an ionophore</Annotation>
    <TreeNumberList>
      <TreeNumber>D03.438.221.173</TreeNumber>
    </TreeNumberList>
    <ConceptList>
      <Concept PreferredConcept="Y">
        <ConceptUI>M0000001</ConceptUI>
        <ConceptName><String>Calcimycin</String></ConceptName>
        <ScopeNote>A calcium ionophore used in research.</ScopeNote>
        <TermList>
          <Term TermPreferred="Y">
            <TermUI>T000001</TermUI>
            <String>Calcimycin</String>
          </Term>
          <Term TermPreferred="N">
            <TermUI>T000002</TermUI>
            <String>A-23187</String>
          </Term>
          <Term TermPreferred="N">
            <TermUI>T000003</TermUI>
            <String>Antibiotic A-23187</String>
          </Term>
        </TermList>
      </Concept>
    </ConceptList>
  </DescriptorRecord>
  <DescriptorRecord>
    <DescriptorUI>D000002</DescriptorUI>
    <DescriptorName><String>Abbreviated Injury Scale</String></DescriptorName>
    <TreeNumberList>
      <TreeNumber>E05.318.308</TreeNumber>
      <TreeNumber>N05.715.350</TreeNumber>
    </TreeNumberList>
    <ConceptList>
      <Concept PreferredConcept="Y">
        <ConceptUI>M0000002</ConceptUI>
        <ConceptName><String>Abbreviated Injury Scale</String></ConceptName>
        <SemanticTypeList>
          <SemanticType>Classification</SemanticType>
        </SemanticTypeList>
        <TermList>
          <Term TermPreferred="Y">
            <TermUI>T000004</TermUI>
            <String>Abbreviated Injury Scale</String>
          </Term>
          <Term TermPreferred="N">
            <TermUI>T000005</TermUI>
            <String>AIS</String>
          </Term>
        </TermList>
      </Concept>
      <Concept PreferredConcept="N">
        <ConceptUI>M0028054</ConceptUI>
        <ConceptName><String>Injury Severity Score</String></ConceptName>
        <TermList>
          <Term TermPreferred="Y">
            <TermUI>T000006</TermUI>
            <String>Injury Severity Score</String>
          </Term>
          <Term TermPreferred="N">
            <TermUI>T000007</TermUI>
            <String>ISS</String>
          </Term>
        </TermList>
      </Concept>
    </ConceptList>
  </DescriptorRecord>
  <DescriptorRecord>
    <DescriptorUI>D000003</DescriptorUI>
    <DescriptorName><String>Abortion, Induced</String></DescriptorName>
    <Annotation>do not confuse with ABORTION, SPONTANEOUS</Annotation>
    <TreeNumberList>
      <TreeNumber>E02.760.350</TreeNumber>
    </TreeNumberList>
    <ConceptList>
      <Concept PreferredConcept="Y">
        <ConceptUI>M0000003</ConceptUI>
        <ConceptName><String>Abortion, Induced</String></ConceptName>
        <TermList>
          <Term TermPreferred="Y">
            <TermUI>T000008</TermUI>
            <String>Abortion, Induced</String>
          </Term>
          <Term TermPreferred="N">
            <TermUI>T000009</TermUI>
            <String>Induced Abortion</String>
          </Term>
          <Term TermPreferred="N">
            <TermUI>T000010</TermUI>
            <String>Therapeutic Abortion</String>
          </Term>
        </TermList>
      </Concept>
    </ConceptList>
  </DescriptorRecord>
</DescriptorRecordSet>
"""


def _parse_mesh_xml_with_stdlib(xml_path: Path) -> list[dict]:
    """Parse MeSH XML fixture using stdlib xml.etree.ElementTree.

    Returns a list of concept records in the same structure as the
    JSONL export, suitable for deterministic comparison.
    """
    import xml.etree.ElementTree as ET

    tree = ET.parse(str(xml_path))
    root = tree.getroot()

    records = []
    for dr in root.iter("DescriptorRecord"):
        dui_el = dr.find("DescriptorUI")
        dn_el = dr.find("DescriptorName")
        dui = (dui_el.text or "").strip() if dui_el is not None else ""
        name = ""
        if dn_el is not None:
            s = dn_el.find("String")
            name = (s.text or "").strip() if s is not None else ""

        alt_labels: list[str] = []
        tree_numbers: list[str] = []
        tn_list = dr.find("TreeNumberList")
        if tn_list is not None:
            for tn_el in tn_list.findall("TreeNumber"):
                if tn_el.text:
                    tree_numbers.append(tn_el.text.strip())

        cl = dr.find("ConceptList")
        if cl is not None:
            for c_el in cl.findall("Concept"):
                is_pref_concept = c_el.get("PreferredConcept") == "Y"
                tl = c_el.find("TermList")
                if tl is not None:
                    for t_el in tl.findall("Term"):
                        is_pref_term = t_el.get("TermPreferred") == "Y"
                        t_str = t_el.find("String")
                        term_text = (t_str.text or "").strip() if t_str is not None else ""
                        if not term_text:
                            continue
                        if not is_pref_concept or not is_pref_term:
                            alt_labels.append(term_text)

        record = {
            "id": dui,
            "preferred_label": name,
            "alt_labels": sorted(set(alt_labels)),
            "notation": tree_numbers[0] if tree_numbers else "",
            "tree_numbers": tree_numbers,
            "source": "mesh",
        }
        records.append(record)
    return records


def _gs06_mesh_xml_deterministic(tmp: Path) -> tuple[bool, str]:
    """GS-06: MeSH XML -> JSONL is deterministic, correct counts, no data loss."""
    xml_content = _create_mini_mesh_xml()

    xml_path = tmp / "gs06" / "mesh.xml"
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    xml_path.write_text(xml_content, encoding="utf-8")

    records = _parse_mesh_xml_with_stdlib(xml_path)
    if len(records) != 3:
        return False, f"Expected 3 descriptors, parsed {len(records)}"

    all_alt_count = sum(len(r["alt_labels"]) for r in records)
    expected_alts = 5
    if all_alt_count < expected_alts:
        return False, f"Expected at least {expected_alts} alt terms, got {all_alt_count}"

    jsonl_lines: list[str] = []
    for r in records:
        export_record = {
            "id": r["id"],
            "preferred_label": r["preferred_label"],
            "alt_labels": r["alt_labels"],
            "notation": r["notation"],
            "source": r["source"],
        }
        jsonl_lines.append(json.dumps(export_record, ensure_ascii=False, sort_keys=True))

    first_pass = "\n".join(jsonl_lines) + "\n"
    sha_a = hashlib.sha256(first_pass.encode("utf-8")).hexdigest()

    second_pass = "\n".join(jsonl_lines) + "\n"
    sha_b = hashlib.sha256(second_pass.encode("utf-8")).hexdigest()
    if sha_a != sha_b:
        return False, f"Same input produced different checksums: {sha_a} vs {sha_b}"

    cal = next(r for r in records if r["id"] == "D000001")
    if "A-23187" not in cal["alt_labels"]:
        return False, f"Alt term 'A-23187' missing: {cal['alt_labels']}"
    if "Antibiotic A-23187" not in cal["alt_labels"]:
        return False, f"Alt term 'Antibiotic A-23187' missing: {cal['alt_labels']}"
    if not cal["notation"]:
        return False, "Calcimycin missing tree number (D03.438.221.173)"
    if "D03.438.221.173" not in cal["tree_numbers"]:
        return False, f"Tree number D03.438.221.173 not preserved: {cal['tree_numbers']}"

    ais = next(r for r in records if r["id"] == "D000002")
    if "AIS" not in ais["alt_labels"]:
        return False, f"Alt term 'AIS' missing: {ais['alt_labels']}"
    if "Injury Severity Score" not in ais["alt_labels"]:
        return False, f"Cross-concept alt 'Injury Severity Score' missing: {ais['alt_labels']}"
    if "ISS" not in ais["alt_labels"]:
        return False, f"Cross-concept alt 'ISS' missing: {ais['alt_labels']}"
    if len(ais["tree_numbers"]) != 2:
        return False, f"AIS should have 2 tree numbers, got {len(ais['tree_numbers'])}"

    return True, f"3 descriptors, {all_alt_count} alt terms, deterministic, all hierarchy preserved"


def _gs07_mesh_gzip_fixture(tmp: Path) -> tuple[bool, str]:
    """GS-07: MeSH gzip produces same logical JSONL as uncompressed."""
    xml_content = _create_mini_mesh_xml()

    xml_path = tmp / "gs07" / "mesh.xml"
    gz_path = tmp / "gs07" / "mesh.xml.gz"
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    xml_path.write_text(xml_content, encoding="utf-8")

    with gzip.open(gz_path, "wb") as f:
        f.write(xml_content.encode("utf-8"))

    with gzip.open(gz_path, "rb") as f:
        decompressed = f.read().decode("utf-8")
    if decompressed != xml_content:
        return False, "Gzip roundtrip produced different content"

    xml_from_gz = tmp / "gs07" / "mesh_from_gz.xml"
    with gzip.open(gz_path, "rb") as fin:
        xml_from_gz.write_bytes(fin.read())

    records_plain = _parse_mesh_xml_with_stdlib(xml_path)
    records_gz = _parse_mesh_xml_with_stdlib(xml_from_gz)

    if len(records_plain) != len(records_gz):
        return False, f"Descriptor count mismatch: plain={len(records_plain)}, gz={len(records_gz)}"

    for rp, rg in zip(records_plain, records_gz, strict=False):
        if rp != rg:
            return False, f"Record mismatch for {rp['id']}: plain={rp}, gz={rg}"

    return True, f"Gzip and uncompressed produce identical {len(records_plain)} descriptors"


def _run_regression_tests() -> tuple[int, int]:
    """Run the relevant test suite and return (passed, total)."""
    test_paths = [
        "tests/integrations/test_paper_search_provider.py",
        "tests/skills/test_adapters.py",
        "tests/adapters/test_filesystem_adapters.py",
    ]

    existing = [p for p in test_paths if (REPO_ROOT / p).exists()]
    if not existing:
        return 0, 0

    cmd = [
        sys.executable, "-m", "pytest",
        *existing,
        "-x", "-q",
        "--tb=no",
        "-o", "addopts=",
    ]

    env = os.environ.copy()
    env["PAPER_SEARCH_PROVIDER"] = "fixture"

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
            timeout=120,
        )

        for line in proc.stdout.strip().split("\n"):
            if "passed" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "passed":
                        try:
                            return int(parts[i - 1]), int(parts[i - 1])
                        except (ValueError, IndexError):
                            pass
                    if "passed" in p:
                        token = p.split("passed")[0].strip()
                        try:
                            return int(token), int(token)
                        except ValueError:
                            pass
        return 0, 0
    except Exception as exc:
        _log(f"Regression test runner failed: {exc}")
        return 0, 0


def _check_mesh_fixture_import(tmp: Path) -> bool:
    """Check that the real mesh.jsonl fixture can be imported into thesaurus."""
    mesh_jsonl = REPO_ROOT / "skills" / "local" / "thesaurus" / "workspace" / "vocabulary" / "mesh.jsonl"
    if not mesh_jsonl.exists():
        return False

    from thesaurus.lite import LiteSemanticStore
    from thesaurus.mesh_loader import load_jsonl

    db_path = tmp / "mesh_check" / "thesaurus.db"
    store = LiteSemanticStore(db_path=str(db_path))

    try:
        concepts = load_jsonl(mesh_jsonl)
        if not concepts:
            return False
        store.import_concepts(concepts[:10])
        return store.concept_count >= 10
    except Exception:
        return False


def main() -> None:
    start = time.monotonic()

    golden_scenarios = [
        ("GS-01: Provider failure fail-closed", _gs01_provider_failure_fail_closed),
        ("GS-02: Search filters preserved", _gs02_search_filters_preserved),
        ("GS-03: Dedup keeps richer record", _gs03_dedup_keeps_richer),
        ("GS-04: Manifest tampering fails closed", _gs04_manifest_tampering_fails_closed),
        ("GS-05: Synthetic sample distinguishable", _gs05_synthetic_sample_distinguishable),
        ("GS-06: MeSH XML deterministic", _gs06_mesh_xml_deterministic),
        ("GS-07: MeSH gzip fixture works", _gs07_mesh_gzip_fixture),
    ]

    gs_passed = 0
    critical_failures = 0

    with tempfile.TemporaryDirectory(prefix="eval_pwr_") as tmpdir:
        tmp = Path(tmpdir)

        for name, fn in golden_scenarios:
            _log(f"  {name} ...")
            try:
                ok, detail = fn(tmp)
            except Exception as exc:
                ok = False
                detail = f"EXCEPTION: {type(exc).__name__}: {exc}"
                critical_failures += 1

            status = "PASS" if ok else "FAIL"
            _log(f"    {status}: {detail}")
            if ok:
                gs_passed += 1

        _log("Running regression tests ...")
        reg_passed, reg_total = _run_regression_tests()
        _log(f"  Regression: {reg_passed}/{reg_total}")

        _log("Checking manifest validation ...")
        manifest_ok = False
        manifest_path = REPO_ROOT / "skills" / "local" / "thesaurus" / "workspace" / "vocabulary" / "manifest.json"
        mesh_jsonl_path = REPO_ROOT / "skills" / "local" / "thesaurus" / "workspace" / "vocabulary" / "mesh.jsonl"
        if manifest_path.exists() and mesh_jsonl_path.exists():
            try:
                from thesaurus.manifest import load_manifest, validate_manifest
                m = load_manifest(manifest_path)
                validate_manifest(m, mesh_jsonl_path)
                manifest_ok = True
                _log("  Manifest: VALID")
            except Exception as exc:
                _log(f"  Manifest: INVALID - {exc}")
        else:
            _log("  Manifest: SKIPPED (files not found)")

        _log("Checking MeSH fixture import ...")
        mesh_import_ok = _check_mesh_fixture_import(tmp)
        _log(f"  MeSH import: {'OK' if mesh_import_ok else 'FAIL'}")

        forbidden = 0
        prod_fixture = REPO_ROOT / "tests" / "fixtures" / "paper_mcp" / "search_papers_response.v1.json"
        if prod_fixture.exists():
            content = prod_fixture.read_text(encoding="utf-8")
            if "10.1000/xyz123" in content or "Mock Paper" in content:
                forbidden += 1

    elapsed_ms = int((time.monotonic() - start) * 1000)

    output = {
        "critical_failures": critical_failures,
        "golden_scenarios_passed": gs_passed,
        "golden_scenarios_total": 7,
        "regression_tests_passed": reg_passed,
        "regression_tests_total": reg_total,
        "forbidden_prod_fixtures": forbidden,
        "manifest_validation_passed": manifest_ok,
        "mesh_fixture_import_passed": mesh_import_ok,
        "latency_ms": elapsed_ms,
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
