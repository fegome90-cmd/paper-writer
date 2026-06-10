"""H-B02: sample.jsonl must be distinguished from real MeSH.

Hypothesis: No test or code distinguishes synthetic sample.jsonl from real MeSH
data. The `source` field exists in concepts but no gate checks it, and the audit
system does not report the vocabulary source.

This test verifies:
1. sample.jsonl concepts have source="synthetic"
2. mesh.jsonl concepts have source="mesh"
3. Audit reports vocabulary source clearly
4. Audit output distinguishes synthetic from real MeSH
"""

import json
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
THESAURUS_SRC = REPO_ROOT / "skills" / "local" / "thesaurus" / "src"
VOCAB_DIR = REPO_ROOT / "skills" / "local" / "thesaurus" / "workspace" / "vocabulary"

SAMPLE_JSONL = VOCAB_DIR / "sample.jsonl"
MESH_JSONL = VOCAB_DIR / "mesh.jsonl"
MANIFEST_JSON = VOCAB_DIR / "manifest.json"


@pytest.fixture(autouse=True)
def _add_thesaurus_to_path():
    import sys

    if str(THESAURUS_SRC) not in sys.path:
        sys.path.insert(0, str(THESAURUS_SRC))
    yield


def _load_first_concept(path: Path) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        line = f.readline().strip()
        return json.loads(line)


class TestSampleJsonlSource:
    def test_first_concept_has_source_synthetic(self):
        concept = _load_first_concept(SAMPLE_JSONL)
        assert concept.get("source") == "synthetic", (
            f"source should be synthetic, got {concept.get('source')!r}"
        )

    def test_all_concepts_have_source_field(self):
        sources = set()
        with open(SAMPLE_JSONL, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                sources.add(record.get("source", ""))
        assert sources == {"synthetic"}, (
            f"All sample.jsonl concepts should have source='synthetic', got {sources}"
        )


class TestMeshJsonlSource:
    def test_first_concept_has_source_mesh(self):
        concept = _load_first_concept(MESH_JSONL)
        assert concept.get("source") == "mesh", (
            f"mesh.jsonl first concept source should be 'mesh', got {concept.get('source')!r}"
        )

    def test_all_sampled_concepts_have_source_mesh(self):
        sources = set()
        with open(MESH_JSONL, encoding="utf-8-sig") as f:
            for i, line in enumerate(f):
                if i >= 50:
                    break
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                sources.add(record.get("source", ""))
        assert sources == {"mesh"}, f"mesh.jsonl concepts should have source='mesh', got {sources}"


class TestManifestSource:
    def test_manifest_has_source_mesh(self):
        manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
        assert manifest.get("source") == "mesh", (
            f"manifest.json should have source='mesh', got {manifest.get('source')!r}"
        )

    def test_manifest_source_file_points_to_mesh(self):
        manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
        assert manifest.get("source_file") == "mesh.jsonl", (
            f"manifest.json source_file should be 'mesh.jsonl', got {manifest.get('source_file')!r}"
        )

    def test_no_manifest_for_sample_jsonl(self):
        sample_manifest = VOCAB_DIR / "sample.jsonl.manifest.json"
        assert not sample_manifest.exists(), (
            "sample.jsonl should NOT have its own manifest — it is not production data"
        )


class TestAuditReportsSource:
    def test_audit_includes_source_for_synthetic(self):
        from thesaurus.lite import LiteSemanticStore
        from thesaurus.mesh_loader import load_jsonl

        with tempfile.TemporaryDirectory(prefix="h_b02_") as tmpdir:
            db_path = Path(tmpdir) / "thesaurus.db"
            workspace = db_path.parent
            vocab = workspace / "vocabulary"
            vocab.mkdir(parents=True)

            concepts = load_jsonl(SAMPLE_JSONL)
            store = LiteSemanticStore(db_path=str(db_path))
            store.import_concepts(concepts[:5])

            info = store.audit()
            assert "source" in info, (
                f"audit() must include 'source' key, got keys: {sorted(info.keys())}"
            )
            assert info["source"] in ("synthetic", "mesh", "decs", "local", ""), (
                f"audit source should be a recognized vocabulary type, got {info['source']!r}"
            )

    def test_audit_output_shows_source_synthetic(self):
        from thesaurus.audit import format_audit
        from thesaurus.lite import LiteSemanticStore
        from thesaurus.mesh_loader import load_jsonl

        with tempfile.TemporaryDirectory(prefix="h_b02_") as tmpdir:
            db_path = Path(tmpdir) / "thesaurus.db"
            concepts = load_jsonl(SAMPLE_JSONL)
            store = LiteSemanticStore(db_path=str(db_path))
            store.import_concepts(concepts[:5])

            report = format_audit(store)
            assert "synthetic" in report.lower() or "source" in report.lower(), (
                f"Audit report should mention vocabulary source. Got:\n{report}"
            )

    def test_audit_distinguishes_synthetic_from_mesh(self):
        from thesaurus.lite import LiteSemanticStore
        from thesaurus.mesh_loader import load_jsonl

        with tempfile.TemporaryDirectory(prefix="h_b02_") as tmpdir:
            tmp = Path(tmpdir)

            db_synthetic = tmp / "synthetic" / "thesaurus.db"
            db_synthetic.parent.mkdir(parents=True)
            synthetic_concepts = load_jsonl(SAMPLE_JSONL)
            store_s = LiteSemanticStore(db_path=str(db_synthetic))
            store_s.import_concepts(synthetic_concepts[:5])
            audit_s = store_s.audit()

            db_mesh = tmp / "mesh" / "thesaurus.db"
            db_mesh.parent.mkdir(parents=True)
            mesh_concepts = load_jsonl(MESH_JSONL)
            store_m = LiteSemanticStore(db_path=str(db_mesh))
            store_m.import_concepts(mesh_concepts[:5])
            audit_m = store_m.audit()

            assert "source" in audit_s, "synthetic audit must include 'source'"
            assert "source" in audit_m, "mesh audit must include 'source'"
            assert audit_s["source"] != audit_m["source"], (
                f"Audit source for synthetic ({audit_s['source']!r}) must differ "
                f"from mesh ({audit_m['source']!r})"
            )
            assert audit_s["source"] == "synthetic", (
                f"Synthetic DB audit source should be 'synthetic', got {audit_s['source']!r}"
            )
            assert audit_m["source"] == "mesh", (
                f"MeSH DB audit source should be 'mesh', got {audit_m['source']!r}"
            )
