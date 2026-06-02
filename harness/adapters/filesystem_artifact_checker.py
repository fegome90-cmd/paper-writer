from pathlib import Path

from harness.ports.artifact_checker import ArtifactChecker


class FilesystemArtifactChecker(ArtifactChecker):
    """Adapter implementing ArtifactChecker using local filesystem paths."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path

    def check_dir_exists(self, rel_path: str) -> None:
        path = self.repo_path / rel_path
        if not path.is_dir():
            raise FileNotFoundError(f"Directory '{rel_path}' not found at {path}")

    def check_file_exists(self, rel_path: str) -> None:
        path = self.repo_path / rel_path
        if not path.is_file():
            raise FileNotFoundError(f"File '{rel_path}' not found at {path}")
        if path.stat().st_size == 0:
            raise ValueError(f"File '{rel_path}' exists but is empty (0 bytes)")

    def check_any_file_exists(self, rel_paths: list[str]) -> None:
        paths = [self.repo_path / p for p in rel_paths]
        existing = [p for p in paths if p.is_file()]
        if not existing:
            raise FileNotFoundError(f"No files found. Tried: {rel_paths}")
        non_empty = [p for p in existing if p.stat().st_size > 0]
        if not non_empty:
            names = [str(p) for p in existing]
            raise ValueError(f"All render outputs exist but are empty (0 bytes): {names}")

    def get_full_path_str(self, rel_path: str) -> str:
        return str(self.repo_path / rel_path)
