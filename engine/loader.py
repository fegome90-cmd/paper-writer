from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_rules(rules_dir: str | Path) -> list[dict[str, Any]]:
    """Load all YAML rule files from a directory.

    Each file must have:
      - rule_group (e.g. 'prose.overclaim')
      - rules[] with id, patterns[], message, severity, scope, recommendation

    Args:
        rules_dir: Path to directory containing .yml rule files.

    Returns:
        Flattened list of rule dicts.
    """
    rules_path = Path(rules_dir)
    if not rules_path.is_dir():
        return []

    all_rules: list[dict[str, Any]] = []
    for fpath in sorted(rules_path.glob("*.yml")):
        with open(fpath, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data or "rules" not in data:
            continue
        rule_group = data.get("rule_group", "")
        default_severity = data.get("severity_default", "P2")
        for rule in data["rules"]:
            rule = {**rule}
            rule["rule_group"] = rule_group
            rule.setdefault("severity", default_severity)
            rule.setdefault("scope", "sentence")
            rule.setdefault("recommendation", "")
            rule.setdefault("evidence_required", [])
            all_rules.append(rule)

    return all_rules


def load_checklist(checklist_path: str | Path) -> dict[str, Any] | None:
    """Load a single checklist YAML file for method gate.

    Returns None if file does not exist or is invalid.
    """
    from typing import cast

    path = Path(checklist_path)
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not raw or "guideline" not in raw:
        return None
    data = cast(dict[str, Any], raw)
    data["file"] = str(path)
    return data


def load_checklists(
    checklists_dir: str | Path,
) -> dict[str, dict[str, Any]]:
    """Load all checklist YAML files from a directory.

    Returns dict keyed by checklist.study_types (or filename).
    """
    path = Path(checklists_dir)
    if not path.is_dir():
        return {}

    checklists: dict[str, dict[str, Any]] = {}
    for fpath in sorted(path.glob("*.yml")):
        cl = load_checklist(fpath)
        if cl is None:
            continue
        for st in cl.get("study_types", ["*"]):
            checklists[st] = cl
    return checklists
