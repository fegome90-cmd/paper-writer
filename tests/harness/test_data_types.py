"""Construction tests for data types not directly referenced in other tests.

These types are tested indirectly through integration and orchestrator tests,
but adding explicit imports + construction tests closes the static coverage gap.
"""

from clients.trifecta import TrifectaResult, TrifectaUnavailableError
from harness.ports.skill_adapter import SkillResult
from harness.services.gates import Check, GateResult, run_gate
from parsers.source_map import SourcePosition


class TestTrifectaTypes:
    def test_unavailable_error_is_exception(self) -> None:
        err = TrifectaUnavailableError("test")
        assert isinstance(err, Exception)
        assert str(err) == "test"

    def test_result_construction(self) -> None:
        result = TrifectaResult(success=True, data={"key": "value"})
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error == ""


class TestSkillResult:
    def test_construction(self) -> None:
        result = SkillResult(
            adapter="test",
            status="pass",
            summary="test passed",
            artifacts=["output.txt"],
            gate_changes={"test_gate": True},
        )
        assert result.status == "pass"
        assert result.summary == "test passed"

    def test_invalid_status_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            SkillResult(
                adapter="test",
                status="invalid",
                summary="",
                artifacts=[],
                gate_changes={},
            )


class TestGateTypes:
    def test_check_construction(self) -> None:
        check = Check(id="test", description="desc", run_fn=lambda: None)
        assert check.id == "test"
        assert check.soft is False

    def test_gate_result_construction(self) -> None:
        result = GateResult(gate="test_gate", status="pass")
        assert result.gate == "test_gate"
        assert result.status == "pass"
        assert result.blockers == []

    def test_run_gate_executes_checks(self) -> None:
        check = Check(
            id="always_pass",
            description="always passes",
            run_fn=lambda: None,
        )
        result = run_gate("test_gate", [check], [])
        assert result.status == "pass"


class TestSourcePosition:
    def test_construction(self) -> None:
        pos = SourcePosition(line=10, column=5, char_offset=42)
        assert pos.line == 10
        assert pos.column == 5
        assert pos.char_offset == 42
