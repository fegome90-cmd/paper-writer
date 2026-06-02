from pathlib import Path
from typing import Any
import pytest
from harness.ports.tool_resolver import ToolResolution, ToolResolver

def test_tool_resolution_dataclass():
    """Verify ToolResolution can be instantiated."""
    res = ToolResolution(path=Path("/usr/bin/pandoc"), version="3.1.0", source="global")
    assert res.path == Path("/usr/bin/pandoc")
    assert res.version == "3.1.0"
    assert res.source == "global"

def test_tool_resolver_interface():
    """Verify ToolResolver ABC can be subclassed and enforced."""
    class DummyResolver(ToolResolver):
        def resolve(self, tool_id: str, min_version: str | None = None) -> ToolResolution | None:
            if tool_id == "found":
                return ToolResolution(Path("/bin/found"), "1.0.0", "env")
            return None

    resolver = DummyResolver()
    result = resolver.resolve("found")
    assert result.path == Path("/bin/found")
    assert resolver.resolve("missing") is None

def test_tool_resolver_abc_enforcement():
    """Verify ToolResolver cannot be instantiated directly."""
    with pytest.raises(TypeError):
        ToolResolver()
