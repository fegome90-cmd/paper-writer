"""Port for external validation tool wrappers.

Defines the interface that all tool wrappers must implement.
The orchestrator depends on this port, never on concrete wrappers.

See integrations/tools/ for implementations.
"""

from abc import ABC, abstractmethod
from typing import Any

from harness.ports.tool_resolver import ToolResolver


class ValidatorResult:
    """Structured result returned by every validator wrapper.

    Matches the canonical output contract from VALIDATOR_CONTRACTS.md.
    """

    def __init__(
        self,
        validator: str,
        status: str,
        summary: str,
        findings: list[dict[str, Any]],
        artifacts_checked: list[str],
    ) -> None:
        if status not in ("pass", "warn", "fail"):
            raise ValueError(f"Invalid status: {status}. Must be pass, warn, or fail.")
        self.validator = validator
        self.status = status
        self.summary = summary
        self.findings = findings
        self.artifacts_checked = artifacts_checked

    def to_dict(self) -> dict[str, Any]:
        return {
            "validator": self.validator,
            "status": self.status,
            "summary": self.summary,
            "findings": self.findings,
            "artifacts_checked": self.artifacts_checked,
        }


class ToolWrapper(ABC):
    """Port for external tool wrappers used during the validation stage.

    Each wrapper encapsulates a single external tool concern and returns
    a structured ValidatorResult. The orchestrator never calls subprocess
    directly — it calls wrapper instances through this interface.
    """

    def __init__(self, resolver: ToolResolver | None = None) -> None:
        """Initialize the wrapper with an optional tool resolver.

        Args:
            resolver: Optional ToolResolver for binary path resolution.
        """
        self._resolver = resolver

    @abstractmethod
    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        """Execute the tool and return a structured result."""
        pass

    def is_available(self) -> bool:
        """Return True if the tool is available.

        Default implementation checks the resolver if present.
        Pure-Python wrappers that don't override this will return True
        by default (assuming no resolver is needed).
        """
        if self._resolver:
            # Subclasses should provide their specific tool_id if they use a resolver
            tool_id = getattr(self, "tool_id", self.name)
            return self._resolver.resolve(tool_id) is not None
        return True

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the wrapped tool."""
        pass

    @property
    @abstractmethod
    def gate(self) -> str:
        """Primary gate affected by this wrapper."""
        pass


class ToolNotAvailableError(Exception):
    """Raised when an external tool is required but not installed."""

    def __init__(self, tool_name: str, install_hint: str = "") -> None:
        self.tool_name = tool_name
        self.install_hint = install_hint
        msg = f"Required tool '{tool_name}' is not available."
        if install_hint:
            msg += f" Install with: {install_hint}"
        super().__init__(msg)
