from pathlib import Path
from unittest.mock import MagicMock
from integrations.tools.pandoc import PandocRenderer
from harness.ports.tool_resolver import ToolResolver, ToolResolution

def test_pandoc_uses_resolver():
    """Verify PandocRenderer uses the injected ToolResolver."""
    mock_resolver = MagicMock(spec=ToolResolver)
    mock_resolver.resolve.return_value = ToolResolution(
        path=Path("/usr/bin/pandoc"),
        version="3.1.0",
        source="global"
    )
    
    renderer = PandocRenderer(resolver=mock_resolver)
    
    assert renderer.is_available() is True
    # Should call with "pandoc", not "pandoc-renderer"
    mock_resolver.resolve.assert_called_with("pandoc")
