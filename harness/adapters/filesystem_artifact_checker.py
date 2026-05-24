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

    def check_any_file_exists(self, rel_paths: list[str]) -> None:
        paths = [self.repo_path / p for p in rel_paths]
        if not any(p.is_file() for p in paths):
            raise FileNotFoundError(f"No files found. Tried: {rel_paths}")

    def get_full_path_str(self, rel_path: str) -> str:
        return str(self.repo_path / rel_path)
