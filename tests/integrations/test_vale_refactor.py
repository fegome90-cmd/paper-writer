from pathlib import Path
from unittest.mock import MagicMock
from integrations.tools.vale import StyleLinter
from harness.ports.tool_resolver import ToolResolver, ToolResolution

def test_vale_uses_resolver():
    """Verify StyleLinter uses the injected ToolResolver."""
    mock_resolver = MagicMock(spec=ToolResolver)
    mock_resolver.resolve.return_value = ToolResolution(
        path=Path("/usr/bin/vale"),
        version="3.0.0",
        source="global"
    )
    
    linter = StyleLinter(resolver=mock_resolver)
    
    # Vale is optional, so is_available should still be True even if resolver fails,
    # but we want to see it CALL the resolver to try finding the binary.
    assert linter.is_available() is True
    mock_resolver.resolve.assert_called_with("vale")

def test_vale_fallback_when_resolver_fails():
    """Verify StyleLinter still available if resolver returns None (built-in fallback)."""
    mock_resolver = MagicMock(spec=ToolResolver)
    mock_resolver.resolve.return_value = None
    
    linter = StyleLinter(resolver=mock_resolver)
    
    assert linter.is_available() is True
    mock_resolver.resolve.assert_called_with("vale")
