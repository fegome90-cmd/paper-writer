"""Tests for claim-evidence factual accuracy validator."""

from __future__ import annotations

import json
from pathlib import Path

from validators.claim_evidence import (
    ClaimEvidenceValidator,
    _tokenize,
    compute_overlap,
)


class TestTokenize:
    def test_removes_stopwords(self) -> None:
        tokens = _tokenize("The model is a pre-trained network for code search")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "model" in tokens
        assert "pre-trained" in tokens

    def test_case_insensitive(self) -> None:
        tokens = _tokenize("CodeBERT codebert")
        assert tokens == {"codebert"}

    def test_strips_punctuation(self) -> None:
        tokens = _tokenize("results (98.5%) were significant.")
        assert "results" in tokens
        assert "significant" in tokens
        assert "(" not in str(tokens)

    def test_empty_string(self) -> None:
        assert _tokenize("") == set()


class TestComputeOverlap:
    def test_full_overlap(self) -> None:
        tokens = {"code", "generation", "retrieval"}
        assert compute_overlap(tokens, tokens) == 1.0

    def test_partial_overlap(self) -> None:
        claim = {"code", "generation", "retrieval", "augmented"}
        evidence = {"code", "generation", "language", "model"}
        overlap = compute_overlap(claim, evidence)
        assert 0.0 < overlap < 1.0
        assert abs(overlap - 0.5) < 0.01  # 2/4

    def test_no_overlap(self) -> None:
        claim = {"quantum", "entanglement"}
        evidence = {"code", "generation"}
        assert compute_overlap(claim, evidence) == 0.0

    def test_empty_claim(self) -> None:
        assert compute_overlap(set(), {"code"}) == 0.0


def _make_evidence_file(path: Path, papers: list[dict[str, str]]) -> None:
    """Write a screened_evidence.json with given papers."""
    data = {"evidence": papers}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _claim(text: str) -> dict[str, object]:
    """Create a minimal claim candidate dict."""
    return {"text": text, "section": "introduction", "line": 1}


class TestClaimEvidenceValidator:
    def test_no_evidence_returns_empty(self, tmp_path: Path) -> None:
        validator = ClaimEvidenceValidator(evidence_path=None)
        assert validator.check_claims([_claim("Some claim")]) == []

    def test_empty_evidence_file(self, tmp_path: Path) -> None:
        ev_path = tmp_path / "screened_evidence.json"
        ev_path.write_text('{"evidence": []}')
        validator = ClaimEvidenceValidator(evidence_path=ev_path)
        assert validator.check_claims([_claim("Claim about code.")]) == []

    def test_low_overlap_flagged(self, tmp_path: Path) -> None:
        ev_path = tmp_path / "screened_evidence.json"
        _make_evidence_file(ev_path, [
            {"abstract": "Quantum error correction in topological codes."},
        ])
        validator = ClaimEvidenceValidator(
            evidence_path=ev_path, overlap_threshold=0.30,
        )
        claims = [
            _claim(
                "Code generation models achieve state-of-the-art results "
                "on program synthesis benchmarks."
            ),
        ]
        findings = validator.check_claims(claims)
        assert len(findings) >= 1
        assert findings[0]["rule_id"] == "claim_evidence.low_overlap"

    def test_high_overlap_not_flagged(self, tmp_path: Path) -> None:
        ev_path = tmp_path / "screened_evidence.json"
        _make_evidence_file(ev_path, [
            {"abstract": "CodeBERT is a pre-trained model for code search "
                         "and code generation tasks."},
        ])
        validator = ClaimEvidenceValidator(
            evidence_path=ev_path, overlap_threshold=0.30,
        )
        claims = [
            _claim(
                "CodeBERT achieves strong results on code search benchmarks "
                "and code generation tasks."
            ),
        ]
        findings = validator.check_claims(claims)
        assert len(findings) == 0

    def test_overlap_threshold_configurable(self, tmp_path: Path) -> None:
        ev_path = tmp_path / "screened_evidence.json"
        _make_evidence_file(ev_path, [
            {"abstract": "We study retrieval augmented generation for code."},
        ])
        claims = [
            _claim("Retrieval augmented approaches improve code generation."),
        ]

        strict = ClaimEvidenceValidator(
            evidence_path=ev_path, overlap_threshold=0.80,
        )
        strict_findings = strict.check_claims(claims)

        lenient = ClaimEvidenceValidator(
            evidence_path=ev_path, overlap_threshold=0.10,
        )
        lenient_findings = lenient.check_claims(claims)

        assert len(strict_findings) >= len(lenient_findings)

    def test_finding_has_overlap_metadata(self, tmp_path: Path) -> None:
        ev_path = tmp_path / "screened_evidence.json"
        _make_evidence_file(ev_path, [
            {"abstract": "Quantum computing enables new algorithms."},
        ])
        validator = ClaimEvidenceValidator(
            evidence_path=ev_path, overlap_threshold=0.30,
        )
        claims = [
            _claim("Code generation models produce functionally correct programs."),
        ]
        findings = validator.check_claims(claims)
        assert len(findings) >= 1
        f = findings[0]
        assert "overlap_ratio" in f["evidence"]
        assert f["evidence"]["overlap_ratio"] < 0.30
        assert f["severity"] == "P2"

    def test_multiple_evidence_takes_best(self, tmp_path: Path) -> None:
        ev_path = tmp_path / "screened_evidence.json"
        _make_evidence_file(ev_path, [
            {"abstract": "Quantum error correction in topological codes."},
            {"abstract": "Code generation with pre-trained language models "
                         "improves developer productivity."},
        ])
        validator = ClaimEvidenceValidator(
            evidence_path=ev_path, overlap_threshold=0.30,
        )
        claims = [
            _claim("Pre-trained language models improve code generation quality."),
        ]
        findings = validator.check_claims(claims)
        # High overlap with second evidence — should NOT be flagged
        assert len(findings) == 0

    def test_multiple_claims_mixed(self, tmp_path: Path) -> None:
        ev_path = tmp_path / "screened_evidence.json"
        _make_evidence_file(ev_path, [
            {"abstract": "Retrieval augmented generation combines search with LLMs."},
        ])
        validator = ClaimEvidenceValidator(
            evidence_path=ev_path, overlap_threshold=0.30,
        )
        claims = [
            _claim("RAG systems combine retrieval with generation capabilities."),
            _claim("Quantum computers will revolutionize drug discovery."),
        ]
        findings = validator.check_claims(claims)
        # First claim should pass, second should be flagged
        assert len(findings) == 1
        assert "drug" in findings[0]["evidence"]["claim_snippet"] or \
               "quantum" in findings[0]["evidence"]["claim_snippet"].lower()
