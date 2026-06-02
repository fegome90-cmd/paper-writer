from unittest.mock import MagicMock
from tests.harness.mocks import InMemoryToolWrapper
from harness.ports.tool_resolver import ToolResolver

def test_mock_wrapper_accepts_resolver():
    """Verify InMemoryToolWrapper accepts an optional resolver."""
    mock_resolver = MagicMock(spec=ToolResolver)
    wrapper = InMemoryToolWrapper("test_gate", resolver=mock_resolver)
    assert wrapper.gate == "test_gate"
    # Just prove it doesn't crash on init
