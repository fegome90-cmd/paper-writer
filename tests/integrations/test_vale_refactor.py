from pathlib import Path
from unittest.mock import MagicMock
from integrations.tools.vale import StyleLinter
from harness.ports.tool_resolver import ToolResolver, ToolResolution

def test_vale_uses_resolver():
    """Verify StyleLinter uses the injected ToolResolver during run()."""
    mock_resolver = MagicMock(spec=ToolResolver)
    mock_resolver.resolve.return_value = ToolResolution(
        path=Path("/usr/bin/vale"),
        version="3.0.0",
        source="global"
    )
    
    linter = StyleLinter(resolver=mock_resolver)
    
    # Create a dummy file to lint
    dummy_file = Path("dummy.md")
    dummy_file.write_text("Hello world")
    
    try:
        # Mock subprocess.run to avoid actual vale execution
        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout="{}")
            linter.run({"manuscript_files": [str(dummy_file)]}, {})
            
        mock_resolver.resolve.assert_called_with("vale")
    finally:
        dummy_file.unlink()

def test_vale_fallback_when_resolver_fails():
    """Verify StyleLinter falls back to built-in if resolver returns None."""
    mock_resolver = MagicMock(spec=ToolResolver)
    mock_resolver.resolve.return_value = None
    
    linter = StyleLinter(resolver=mock_resolver)
    dummy_file = Path("dummy_fallback.md")
    dummy_file.write_text("Hello world")
    
    try:
        with patch("validators.style.validate_style", return_value=[]) as mock_val:
            linter.run({"manuscript_files": [str(dummy_file)]}, {})
            assert mock_val.called
            
        mock_resolver.resolve.assert_called_with("vale")
    finally:
        dummy_file.unlink()
