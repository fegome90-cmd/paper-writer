import pytest

from mesh_import.normalize import normalize_text


@pytest.mark.parametrize(
    "input_text, expected",
    [
        ("café", "cafe"),
        ("Café", "cafe"),
        ("CAFÉ", "cafe"),
        ("Ñoño", "nono"),
        ("naïve", "naive"),
        ("über", "uber"),
        ("", ""),
        ("already normalized", "already normalized"),
        ("hello world", "hello world"),
        ("Straße", "strasse"),
        ("Σημειώση", "σημειωση"),
    ],
)
def test_normalize_parametrized(input_text, expected):
    assert normalize_text(input_text) == expected


def test_normalize_nfc_composition():
    composed = "caf\u00e9"
    decomposed = "cafe\u0301"
    assert normalize_text(composed) == normalize_text(decomposed) == "cafe"


def test_normalize_preserves_ascii():
    assert normalize_text("plain ASCII 123") == "plain ascii 123"
