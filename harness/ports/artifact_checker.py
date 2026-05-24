from abc import ABC, abstractmethod


class ArtifactChecker(ABC):
    """Port defining artifact presence checks, decoupling gates from filesystem."""

    @abstractmethod
    def check_dir_exists(self, rel_path: str) -> None:
        """Raises FileNotFoundError if the directory does not exist."""
        pass

    @abstractmethod
    def check_file_exists(self, rel_path: str) -> None:
        """Raises FileNotFoundError if the file does not exist."""
        pass

    @abstractmethod
    def check_any_file_exists(self, rel_paths: list[str]) -> None:
        """Raises FileNotFoundError if none of the files exist."""
        pass

    @abstractmethod
    def get_full_path_str(self, rel_path: str) -> str:
        """Returns the full path representation as a string."""
        pass
