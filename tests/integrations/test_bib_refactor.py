from pathlib import Path
from unittest.mock import MagicMock
from integrations.tools.bibtex_tidy import BibliographyNormalizer
from harness.ports.tool_resolver import ToolResolver, ToolResolution

def test_bib_normalizer_uses_resolver():
    """Verify BibliographyNormalizer uses the injected ToolResolver."""
    mock_resolver = MagicMock(spec=ToolResolver)
    mock_resolver.resolve.return_value = ToolResolution(
        path=Path("/mock/bibtex-tidy"),
        version="1.12.0",
        source="mock"
    )
    
    normalizer = BibliographyNormalizer(resolver=mock_resolver)
    
    assert normalizer.is_available() is True
    mock_resolver.resolve.assert_called_with("bibtex-tidy", "1.11.0")

def test_bib_normalizer_version_too_old():
    """Verify BibliographyNormalizer reports unavailable if version is too old."""
    mock_resolver = MagicMock(spec=ToolResolver)
    # Resolver returns None if version is too old per design
    mock_resolver.resolve.return_value = None
    
    normalizer = BibliographyNormalizer(resolver=mock_resolver)
    
    assert normalizer.is_available() is False
    mock_resolver.resolve.assert_called_with("bibtex-tidy", "1.11.0")
