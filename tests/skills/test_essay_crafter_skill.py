from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "local" / "essay_crafter"
SKILL_MD = SKILL_DIR / "SKILL.md"


def test_essay_crafter_references_all_local_resources() -> None:
    content = SKILL_MD.read_text(encoding="utf-8")

    expected_paths = [
        "assets/evidence_passport.schema.json",
        "assets/outline_template.md",
        "references/evidence_passport.md",
        "references/structure_gate.md",
        "references/paragraph_density.md",
        "references/editorial_cleanup.md",
        "references/integrity_pipeline.md",
        "references/structured_output_complements.md",
    ]

    for rel_path in expected_paths:
        assert rel_path in content, f"Missing skill reference: {rel_path}"
        assert (SKILL_DIR / rel_path).is_file(), f"Missing skill resource file: {rel_path}"


def test_essay_crafter_declares_structure_and_cleanup_gates() -> None:
    content = SKILL_MD.read_text(encoding="utf-8")

    required_phrases = [
        "roadmap sentence",
        "one primary analytical dimension",
        "one rhetorical job only",
        "orphan tokens",
        "architecture editor",
    ]

    for phrase in required_phrases:
        assert phrase in content, f"Expected gate phrase missing: {phrase}"


def test_integrity_pipeline_includes_new_gate_order() -> None:
    content = (SKILL_DIR / "references" / "integrity_pipeline.md").read_text(
        encoding="utf-8"
    )

    required_gates = [
        "Roadmap gate",
        "Structure gate",
        "Paragraph density gate",
        "Editorial cleanup gate",
        "architecture editor",
    ]

    for gate in required_gates:
        assert gate in content, f"Missing integrity pipeline gate: {gate}"
