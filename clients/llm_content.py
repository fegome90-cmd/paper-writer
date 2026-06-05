"""LLM content generation client using CLI tools (Codex, Gemini, Claude).

Provides a unified subprocess interface to generate academic content
from the SKILL.md prompts. Uses the same graceful degradation pattern
as clients/trifecta.py — if no LLM CLI is available, returns empty
content with a clear error message.

Supported CLIs (auto-detected in PATH):
  - pi      (Pi CLI)        — pi --mode json -nc -p @/tmp/prompt.txt
  - claude  (Claude Code)   — claude -p "prompt" --output-format text
  - codex   (Codex CLI)     — codex exec "prompt"
  - gemini  (Gemini CLI)    — gemini -p "prompt" --approval-mode yolo

Usage:
    from clients.llm_content import get_llm_client

    client = get_llm_client()
    if client is not None:
        result = client.generate("Write an introduction about X")
        if result.success:
            print(result.text)

Configuration via environment:
    PAPER_LLM_CLI=auto   - Auto-detect (default)
    PAPER_LLM_CLI=pi     - Force Pi CLI (uses PAPER_LLM_PROVIDER/MODEL env vars)
    PAPER_LLM_CLI=claude - Force Claude Code
    PAPER_LLM_CLI=codex  - Force Codex CLI
    PAPER_LLM_CLI=gemini - Force Gemini CLI
    PAPER_LLM_CLI=off    - Disabled

    PAPER_LLM_PROVIDER   - Provider for pi CLI (default: zai)
    PAPER_LLM_MODEL      - Model for pi CLI (default: glm-5-turbo)

Why subprocess and not SDK:
    - No new dependencies (same pattern as clients/trifecta.py)
    - Each CLI has its own auth already configured
    - Subprocess failures don't crash the caller
    - User picks their preferred tool
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResult:
    """Result of an LLM generation call."""

    success: bool
    text: str = ""
    error: str = ""
    model: str = ""
    cli_tool: str = ""
    elapsed_ms: int = 0


@dataclass
class LLMClient:
    """Subprocess client for an LLM CLI tool.

    NEVER raises. All errors are captured in LLMResult.
    """

    cli_command: str
    timeout: float = 120.0

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        """Generate text from a prompt via the CLI subprocess.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system prompt (not all CLIs support this).
            max_tokens: Optional max tokens hint.

        Returns:
            LLMResult with success=True and generated text, or error details.
        """
        import time

        t0 = time.monotonic()
        try:
            cmd = self._build_command(prompt, system_prompt, max_tokens)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                input=prompt if self._uses_stdin() else None,
            )
            elapsed = int((time.monotonic() - t0) * 1000)

            if result.returncode != 0:
                stderr = (result.stderr or "").strip()[:500]
                return LLMResult(
                    success=False,
                    error=f"CLI exited {result.returncode}: {stderr}",
                    cli_tool=self.cli_command,
                    elapsed_ms=elapsed,
                )

            text = (result.stdout or "").strip()
            if not text:
                return LLMResult(
                    success=False,
                    error="CLI returned empty output",
                    cli_tool=self.cli_command,
                    elapsed_ms=elapsed,
                )

            # Pi --mode json returns JSONL — extract assistant text
            if self.cli_command == "pi":
                text = self._extract_pi_text(text)

            if not text:
                return LLMResult(
                    success=False,
                    error="No usable text in CLI output",
                    cli_tool=self.cli_command,
                    elapsed_ms=elapsed,
                )

            return LLMResult(
                success=True,
                text=text,
                cli_tool=self.cli_command,
                elapsed_ms=elapsed,
            )

        except subprocess.TimeoutExpired:
            elapsed = int((time.monotonic() - t0) * 1000)
            return LLMResult(
                success=False,
                error=f"CLI timed out after {self.timeout}s",
                cli_tool=self.cli_command,
                elapsed_ms=elapsed,
            )
        except FileNotFoundError:
            return LLMResult(
                success=False,
                error=f"CLI not found: {self.cli_command}",
                cli_tool=self.cli_command,
            )
        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            return LLMResult(
                success=False,
                error=str(exc),
                cli_tool=self.cli_command,
                elapsed_ms=elapsed,
            )

    def _build_command(
        self,
        prompt: str,
        system_prompt: str | None,
        max_tokens: int | None,
    ) -> list[str]:
        """Build the subprocess command for the specific CLI."""
        if self.cli_command == "pi":
            return self._build_pi_command(prompt, system_prompt)

        if self.cli_command == "claude":
            cmd = ["claude", "-p", prompt, "--output-format", "text"]
            if system_prompt:
                cmd.extend(["--system-prompt", system_prompt])
            if max_tokens:
                cmd.extend(["--max-turns", "1"])
            return cmd

        elif self.cli_command == "codex":
            cmd = [
                "codex",
                "exec",
                "--approval-mode",
                "full-auto",
                prompt,
            ]
            return cmd

        elif self.cli_command == "gemini":
            cmd = [
                "gemini",
                "-p",
                prompt,
                "--approval-mode",
                "yolo",
                "--sandbox",
            ]
            return cmd

        return [self.cli_command, prompt]

    def _build_pi_command(
        self,
        prompt: str,
        system_prompt: str | None,
    ) -> list[str]:
        """Build pi CLI command using @file pattern from tmux-fork-orchestrator.

        Pi requires prompt via @file for multi-line content (inline has ~40%
        failure rate). Writes combined prompt+system to a temp file.
        """
        import tempfile

        provider = os.environ.get("PAPER_LLM_PROVIDER", "zai")
        model = os.environ.get("PAPER_LLM_MODEL", "glm-5-turbo")

        # Combine system + user prompt for pi @file
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n---\n\n{prompt}"

        # Write to temp file — pi reads @file
        fd, prompt_path = tempfile.mkstemp(
            prefix="paper-llm-", suffix=".txt", dir="/tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(full_prompt)

        return [
            "pi",
            "--provider", provider,
            "--model", model,
            "--mode", "json",
            "-nc",
            "-p", f"@{prompt_path}",
        ]

    @staticmethod
    def _extract_pi_text(raw_stdout: str) -> str:
        """Extract assistant text from pi --mode json JSONL output.

        Pi returns one JSON object per line. We look for 'assistant' role
        messages and concatenate their text content.
        """
        import json

        parts: list[str] = []
        for line in raw_stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                # Not JSON — might be plain text (fallback)
                parts.append(line)
                continue

            # pi JSONL format: {"role": "assistant", "content": "..."}
            # or {"type": "response", "text": "..."}
            role = obj.get("role", "")
            if role == "assistant":
                content = obj.get("content", "")
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    # content may be a list of content blocks
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            parts.append(block.get("text", ""))
            elif "text" in obj and role != "user":
                parts.append(obj["text"])

        return "\n\n".join(parts).strip()

    def _uses_stdin(self) -> bool:
        """Whether this CLI reads prompt from stdin."""
        return False


def _detect_available_cli() -> str | None:
    """Auto-detect which LLM CLI is available in PATH.

    Priority: pi > claude > codex > gemini (Pi is the preferred executor).
    """
    for cli in ("pi", "claude", "codex", "gemini"):
        if shutil.which(cli):
            return cli
    return None


def get_llm_client(
    timeout: float = 120.0,
) -> LLMClient | None:
    """Factory: return an LLMClient based on PAPER_LLM_CLI env var.

    Returns:
        LLMClient instance, or None if disabled/no CLI available.
    """
    mode = os.environ.get("PAPER_LLM_CLI", "auto").lower()

    if mode == "off":
        return None

    if mode == "auto":
        cli = _detect_available_cli()
        if cli is None:
            return None
    elif mode in ("pi", "claude", "codex", "gemini"):
        if not shutil.which(mode):
            return None
        cli = mode
    else:
        return None

    return LLMClient(cli_command=cli, timeout=timeout)


def generate_section(
    section_name: str,
    prompt_template: str,
    evidence: list[dict[str, Any]],
    bib_keys: list[str],
    outline_context: str = "",
) -> LLMResult:
    """Generate a complete academic section using an LLM CLI.

    Assembles the full prompt from the SKILL.md template, evidence,
    and bib keys, then calls the LLM.

    Args:
        section_name: Section being generated (e.g., 'introduction').
        prompt_template: The SKILL.md prompt for this section.
        evidence: List of evidence dicts with title, abstract, doi.
        bib_keys: Available citation keys from references.bib.
        outline_context: Text from the outline for structural guidance.

    Returns:
        LLMResult with the generated section content.
    """
    client = get_llm_client()
    if client is None:
        return LLMResult(
            success=False,
            error="No LLM CLI available (set PAPER_LLM_CLI=claude|codex|gemini)",
        )

    # Build context block with real evidence
    evidence_block = ""
    if evidence:
        evidence_block = "## Available Evidence\n\n"
        for i, paper in enumerate(evidence[:8], 1):
            title = paper.get("title", "Untitled")
            authors = paper.get("authors", "Unknown")
            year = paper.get("year", "N/A")
            abstract = (paper.get("abstract", "") or "")[:300]
            evidence_block += f"{i}. **{title}** ({authors}, {year})\n   {abstract}\n\n"

    # Build citation reference
    cite_block = ""
    if bib_keys:
        cite_block = f"## Available Citation Keys\n\n{', '.join(f'@{k}' for k in bib_keys[:15])}\n"

    # Assemble full prompt
    full_prompt = f"""{prompt_template}

---

## Context

You are writing the **{section_name.title()}** section for a systematic review paper.

{evidence_block}

{cite_block}

{f"## Outline Context\\n\\n{outline_context[:2000]}" if outline_context else ""}

---

**INSTRUCTIONS**:
1. Write ONLY the section content, no meta-comments or placeholders
2. Use APA 7th edition in-text citations: (Author, Year)
3. Use the citation keys provided above — do NOT invent references
4. Follow the structure and tone specified in the prompt
5. Write as a human academic researcher, not an AI
6. Be specific with evidence — cite actual findings, not vague claims"""

    system_prompt = (
        "You are an expert academic writer publishing in Q1 journals. "
        "Write clear, precise, human-like academic prose. "
        "Never use AI-sounding phrases. Always verify claims against evidence."
    )

    return client.generate(
        prompt=full_prompt,
        system_prompt=system_prompt,
    )
