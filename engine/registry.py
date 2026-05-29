from __future__ import annotations

from typing import Any


class CheckRegistry:
    """A registry of rules, inspired by proselint's Check Registry pattern.

    Rules are namespaced (e.g. 'prose.overclaim.definitive_causal') and
    can be enabled/disabled at runtime.
    """

    def __init__(self) -> None:
        self._rules: dict[str, dict[str, Any]] = {}
        self._disabled: set[str] = set()

    def register(self, rule: dict[str, Any]) -> None:
        rule_id = rule.get("id")
        if not rule_id:
            return
        self._rules[rule_id] = rule

    def register_many(self, rules: list[dict[str, Any]]) -> None:
        for rule in rules:
            self.register(rule)

    def get(self, rule_id: str) -> dict[str, Any] | None:
        return self._rules.get(rule_id)

    def disable(self, rule_id: str) -> None:
        self._disabled.add(rule_id)

    def enable(self, rule_id: str) -> None:
        self._disabled.discard(rule_id)

    def active_rules(self) -> list[dict[str, Any]]:
        return [r for rid, r in self._rules.items() if rid not in self._disabled]

    @property
    def count(self) -> int:
        return len(self._rules)

    @property
    def enabled_count(self) -> int:
        return len(self._rules) - len(self._disabled)

    @property
    def all_ids(self) -> list[str]:
        return list(self._rules.keys())
