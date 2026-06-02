import os
import re
import shutil
import subprocess
from pathlib import Path

from harness.ports.tool_resolver import ToolResolution, ToolResolver


class LocalToolResolver(ToolResolver):
    """Local implementation of ToolResolver using a waterfall strategy."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path

    def resolve(
        self, tool_id: str, min_version: str | None = None
    ) -> ToolResolution | None:
        """Resolve tool path and verify version."""
        # 1. ENV Var (e.g. PANDOC_BIN)
        env_key = f"{tool_id.upper().replace('-', '_')}_BIN"
        env_path_str = os.environ.get(env_key)
        if env_path_str:
            res = self._build_resolution(Path(env_path_str), "env")
            if self._verify_min_version(res, min_version):
                return res

        # 2. Local toolchain
        local_path = (
            self.repo_path / "tools" / "node" / "node_modules" / ".bin" / tool_id
        )
        if local_path.exists() and os.access(local_path, os.X_OK):
            res = self._build_resolution(local_path, "local")
            if self._verify_min_version(res, min_version):
                return res

        # 3. Global PATH
        global_bin = shutil.which(tool_id)
        if global_bin:
            res = self._build_resolution(Path(global_bin), "global")
            if self._verify_min_version(res, min_version):
                return res

        return None

    def _build_resolution(self, path: Path, source: str) -> ToolResolution | None:
        """Helper to get version and build ToolResolution."""
        try:
            result = subprocess.run(
                [str(path), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return None
            version = result.stdout.strip()
            return ToolResolution(path=path, version=version, source=source)
        except (OSError, subprocess.SubprocessError):
            return None

    def _verify_min_version(
        self, res: ToolResolution | None, min_version: str | None
    ) -> bool:
        """Helper to compare versions."""
        if res is None:
            return False
        if min_version is None:
            return True
        
        found_v = self._parse_version(res.version)
        min_v = self._parse_version(min_version)
        
        if found_v is None or min_v is None:
            return False
            
        return found_v >= min_v

    @staticmethod
    def _parse_version(version_str: str) -> tuple[int, int, int] | None:
        """Parse version string into semver tuple."""
        # Extract first semver-looking part
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_str)
        if not match:
            # Fallback for simpler versions like "1.11"
            match = re.search(r"(\d+)\.(\d+)", version_str)
            if not match:
                return None
            return (int(match.group(1)), int(match.group(2)), 0)
            
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
