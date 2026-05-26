import re
from pathlib import Path

import yaml


def test_no_users_path_in_executable_code() -> None:
    """Verify no local absolute paths or examen_grado references exist in executable code."""
    imported_dir = Path(__file__).parents[2] / "skills" / "imported"
    py_files = list(imported_dir.glob("**/*.py"))

    # Pattern to search for raw paths or import drifts
    # Allow docstrings/comments that document the source (vendor metadata)
    # but fail if they appear in executable logic.
    users_pat = re.compile(r"(['\"])/Users/.*?(['\"])")
    examen_pat = re.compile(r"\bexamen_grado\b")
    file_pat = re.compile(r"(['\"])file://.*?(['\"])")

    for f in py_files:
        content = f.read_text(encoding="utf-8")
        # Remove comments and docstrings to inspect only executable logic
        # Simple docstring cleaner
        cleaned = re.sub(r'""".*?"""', "", content, flags=re.DOTALL)
        cleaned = re.sub(r"'''.*?'''", "", cleaned, flags=re.DOTALL)
        # Remove single-line comments
        lines = [line.split("#")[0] for line in cleaned.splitlines()]
        cleaned_code = "\n".join(lines)

        rel_path = f.relative_to(imported_dir.parents[2])
        assert not users_pat.search(cleaned_code), (
            f"Absolute /Users/ path found in executable code of {rel_path}"
        )
        assert not examen_pat.search(cleaned_code), (
            f"examen_grado reference found in executable code of {rel_path}"
        )
        assert not file_pat.search(cleaned_code), (
            f"file:// protocol path found in executable code of {rel_path}"
        )


def test_manifest_covers_all_imported_skills() -> None:
    """Verify skills/imported/MANIFEST.yaml is complete and valid."""
    repo_root = Path(__file__).parents[2]
    manifest_path = repo_root / "skills" / "imported" / "MANIFEST.yaml"
    assert manifest_path.is_file(), "MANIFEST.yaml is missing"

    with manifest_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "skills" in data, "MANIFEST.yaml must contain a 'skills' list"
    skills = data["skills"]
    assert len(skills) > 0, "MANIFEST.yaml must declare at least one skill"

    # Scan imported directory
    imported_dir = repo_root / "skills" / "imported"
    subdirs = [d.name for d in imported_dir.iterdir() if d.is_dir() and d.name != "__pycache__"]

    manifest_ids = [s["id"] for s in skills]
    manifest_paths = [s["local_path"] for s in skills]

    for subdir in subdirs:
        # Verify folder is registered
        assert subdir in manifest_ids or f"skills/imported/{subdir}" in manifest_paths, (
            f"Directory 'skills/imported/{subdir}' is not declared in MANIFEST.yaml"
        )


def test_skill_contracts_and_resources_exist() -> None:
    """Verify each imported skill has SKILL.md and all internal resources exist."""
    repo_root = Path(__file__).parents[2]
    manifest_path = repo_root / "skills" / "imported" / "MANIFEST.yaml"

    with manifest_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    for skill in data["skills"]:
        skill_dir = repo_root / skill["local_path"]
        assert skill_dir.is_dir(), f"Declared skill path does not exist: {skill_dir}"

        skill_md = skill_dir / "SKILL.md"
        assert skill_md.is_file(), f"SKILL.md is missing for skill {skill['id']} in {skill_dir}"

        # Parse markdown links to verify resource existence
        content = skill_md.read_text(encoding="utf-8")
        # Find markdown link patterns: [text](link)
        links = re.findall(r"\[.*?\]\((.*?)\)", content)

        for link in links:
            # We only verify relative file paths inside the skill directory
            # (e.g. "resources/foo.md")
            # Skip web URLs, absolute file links, or parent anchors
            if (
                link.startswith("http://")
                or link.startswith("https://")
                or link.startswith("#")
                or link.startswith("file://")
                or link.startswith("../")
            ):
                continue

            # Strip query params or anchor links
            clean_link = link.split("#")[0].split("?")[0]
            if not clean_link:
                continue

            resource_path = skill_dir / clean_link
            assert resource_path.exists(), (
                f"Referenced resource '{clean_link}' in {skill_md.name} does not exist"
            )
