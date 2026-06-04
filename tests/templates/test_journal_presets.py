"""Tests for journal presets (Nature, Springer, Elsevier)."""

from __future__ import annotations

from pathlib import Path

TEMPLATES_DIR = Path("templates/journals")


class TestNaturePreset:
    def test_preset_loads(self) -> None:
        import yaml

        preset_path = TEMPLATES_DIR / "nature" / "preset.yaml"
        data = yaml.safe_load(preset_path.read_text(encoding="utf-8"))
        assert data["name"] == "Nature"
        assert "abstract" in data["required_sections"]

    def test_template_exists(self) -> None:
        assert (TEMPLATES_DIR / "nature" / "template.qmd").exists()

    def test_bib_exists(self) -> None:
        assert (TEMPLATES_DIR / "nature" / "references.bib").exists()


class TestSpringerPreset:
    def test_preset_loads(self) -> None:
        from templates.journals.springer import get_springer_preset

        data = get_springer_preset()
        assert data["name"] == "Springer"
        assert data["latex_class"] == "sn-jnl"
        req = data.get("required_sections", [])
        assert isinstance(req, list)
        assert "literature_review" in req

    def test_template_exists(self) -> None:
        assert (TEMPLATES_DIR / "springer" / "template.qmd").exists()

    def test_abstract_max_words(self) -> None:
        from templates.journals.springer import get_springer_preset

        data = get_springer_preset()
        assert data["abstract_max_words"] == 250


class TestElsevierPreset:
    def test_preset_loads(self) -> None:
        from templates.journals.elsevier import get_elsevier_preset

        data = get_elsevier_preset()
        assert data["name"] == "Elsevier"
        assert data["latex_class"] == "elsarticle"

    def test_template_exists(self) -> None:
        assert (TEMPLATES_DIR / "elsevier" / "template.qmd").exists()

    def test_sections(self) -> None:
        from templates.journals.elsevier import get_elsevier_preset

        data = get_elsevier_preset()
        req = data.get("required_sections", [])
        assert isinstance(req, list)
        assert "introduction" in req
        assert "conclusion" in req
