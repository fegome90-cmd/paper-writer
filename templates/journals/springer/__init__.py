"""Springer journal preset loader."""

from pathlib import Path

_PRESET_DIR = Path(__file__).parent


def get_springer_preset() -> dict[str, object]:
    """Load Springer preset configuration."""
    import yaml

    with open(Path(__file__).parent / "preset.yaml", encoding="utf-8") as f:
        data: dict[str, object] = yaml.safe_load(f)
    return data
