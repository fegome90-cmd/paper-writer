"""Port for external tool resolution.

Defines the interface for locating and verifying external binaries
(Pandoc, Vale, bibtex-tidy) across different environments.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ToolResolution:
    """Consolidated result of a tool resolution attempt."""

    path: Path
    version: str
    source: str  # 'env' | 'local' | 'global'


class ToolResolver(ABC):
    """Interface for resolving external tool paths and versions."""

    @abstractmethod
    def resolve(
        self, tool_id: str, min_version: str | None = None
    ) -> ToolResolution | None:
        """Locate a tool and verify its version if requested.

        Args:
            tool_id: Unique identifier for the tool (e.g., 'pandoc').
            min_version: Optional minimum version string (semver).

        Returns:
            ToolResolution if found and version satisfies requirement, else None.
        """
        pass


class ToolResolutionError(Exception):
    """Base exception for tool resolution failures."""

    pass
