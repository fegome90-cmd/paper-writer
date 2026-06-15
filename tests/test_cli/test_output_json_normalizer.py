"""Tests for output.to_json_value normalizer (P2.8.21).

Proves that Path/Enum/dataclass/datetime/tuple are normalized explicitly
(no default=str per spec S9) and non-string dict keys are rejected.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pytest

from cli.paper.output import to_json_value


class _Color(Enum):
    RED = "red"
    GREEN = "green"


@dataclass
class _Item:
    name: str
    count: int


class TestJsonNormalizerHandlesComplexTypes:
    """P2.8.21 part 1: Path/Enum/dataclass/datetime/tuple normalization."""

    def test_path_normalized_to_str(self) -> None:
        assert to_json_value(Path("/tmp/x.yaml")) == "/tmp/x.yaml"

    def test_enum_normalized_to_value(self) -> None:
        assert to_json_value(_Color.RED) == "red"

    def test_dataclass_normalized_to_dict(self) -> None:
        result = to_json_value(_Item(name="alpha", count=3))
        assert result == {"name": "alpha", "count": 3}

    def test_datetime_normalized_to_isoformat(self) -> None:
        dt = datetime.datetime(2026, 6, 13, 12, 30, 0)
        assert to_json_value(dt) == "2026-06-13T12:30:00"

    def test_date_normalized_to_isoformat(self) -> None:
        d = datetime.date(2026, 6, 13)
        assert to_json_value(d) == "2026-06-13"

    def test_tuple_normalized_to_list(self) -> None:
        assert to_json_value((1, "a", True)) == [1, "a", True]

    def test_nested_combination(self) -> None:
        payload = {
            "path": Path("/x"),
            "color": _Color.GREEN,
            "item": _Item(name="beta", count=2),
            "when": datetime.date(2026, 1, 1),
            "tags": ("x", "y"),
        }
        result = to_json_value(payload)
        assert result == {
            "path": "/x",
            "color": "green",
            "item": {"name": "beta", "count": 2},
            "when": "2026-01-01",
            "tags": ["x", "y"],
        }


class TestJsonNormalizerRejectsInvalidInput:
    """P2.8.21 part 2: non-string dict keys rejected; unknown types raise."""

    def test_non_string_dict_key_raises_typeerror(self) -> None:
        with pytest.raises(TypeError):
            to_json_value({123: "x"})

    def test_unknown_type_raises_typeerror(self) -> None:
        class _Unknown:
            pass

        with pytest.raises(TypeError):
            to_json_value(_Unknown())

    def test_circular_dataclass_reference_raises_typeerror_not_recursionerror(self) -> None:
        """W1 fix: self-referential dataclass must raise TypeError, not RecursionError.

        A dataclass that references itself (directly or transitively) would make
        asdict() + to_json_value recurse infinitely. The depth/seen guard converts
        that into a clear TypeError so the user gets an actionable message.
        """
        from dataclasses import dataclass

        @dataclass
        class _Node:
            name: str
            parent: _Node | None = None

        root = _Node(name="root")
        root.parent = root  # circular reference

        with pytest.raises(TypeError, match=r"circular|cycle|depth|recursion"):
            to_json_value(root)
