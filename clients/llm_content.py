"""LLM content generation client using CLI tools (Codex, Gemini, Claude).

Provides a unified subprocess interface to generate academic content
from the SKILL.md prompts. Uses the same graceful degradation pattern
as clients/trifecta.py — if no LLM CLI is available, returns empty
content with a clear error message.

Supported CLIs (auto-detected in PATH):
  - pi      (Pi CLI)        — pi --mode text -nc -p @/tmp/prompt.txt
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


def _strip_cot_prefix(text: str) -> str:
    """Strip chain-of-thought planning text that models emit before real content.

    Models sometimes produce sentences like "I can see that...", "Good. I now
    have full context...", or "Here is the section:" before the actual prose.
    This function finds the first line that looks like academic content and
    discards everything before it.

    A line is considered "real content" if:
    - It is >60 characters long (substantial text)
    - Starts with an uppercase letter or a citation marker
    - Does NOT contain CoT markers ("I can see", "Let me", "Here is", etc.)
    """
    import re

    cot_markers = re.compile(
        r"(?:I can see|I now have|Let me|Here is the \w+ section"
        r"|BEGIN SECTION:|Good\. I now have|I have written|The section is"
        r"|Let me produce|Let me now)",
        re.IGNORECASE,
    )

    lines = text.split("\n")
    content_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip empty lines, markdown headers, HTML comments
        if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
            continue
        # Skip lines that contain CoT markers
        if cot_markers.search(stripped):
            continue
        # First surviving line that is substantial enough is real content
        if len(stripped) >= 60:
            content_start = i
            break

    if content_start > 0:
        return "\n".join(lines[content_start:]).strip()
    return text


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
    timeout: float = 300.0

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

        prompt_path: str | None = None
        t0 = time.monotonic()
        try:
            cmd = self._build_command(prompt, system_prompt, max_tokens)
            # For pi: extract the temp file path so we can clean it up
            if self.cli_command == "pi" and cmd[-1].startswith("@"):
                prompt_path = cmd[-1][1:]
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

            output = (result.stdout or "").strip()

            # Strip ANSI escape sequences and tmux OSC notifications from pi output
            import re

            output = re.sub(r"\x1b\][^\x07]*\x07", "", output)
            output = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output)

            # Strip chain-of-thought prefix: models sometimes emit planning text
            # before the actual content. Strategy: find the first line that looks
            # like real academic prose (>80 chars, starts with capital, no CoT markers)
            # and discard everything before it.
            output = _strip_cot_prefix(output)

            if not output:
                return LLMResult(
                    success=False,
                    error="CLI returned empty output",
                    cli_tool=self.cli_command,
                    elapsed_ms=elapsed,
                )

            return LLMResult(
                success=True,
                text=output,
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
        finally:
            # Clean up pi temp file to prevent /tmp leak
            if prompt_path is not None:
                try:
                    os.unlink(prompt_path)
                except OSError:
                    pass

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
        fd, prompt_path = tempfile.mkstemp(prefix="paper-llm-", suffix=".txt", dir="/tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(full_prompt)

        return [
            "pi",
            "--provider",
            provider,
            "--model",
            model,
            "--mode",
            "text",
            "-nc",
            "-p",
            f"@{prompt_path}",
        ]

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
    timeout: float = 300.0,
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
    evidence: list[dict[str, Any]],
    bib_keys: list[str],
    outline_context: str = "",
) -> LLMResult:
    """Generate a complete academic section using an LLM CLI.

    Assembles the prompt from evidence and bib keys, then calls the LLM.

    Args:
        section_name: Section being generated (e.g., 'introduction').
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

    # Build context block with real evidence — keep it SHORT
    evidence_block = ""
    if evidence:
        evidence_block = "## Available Evidence\n\n"
        for i, paper in enumerate(evidence[:8], 1):
            title = paper.get("title", "Untitled")
            authors = paper.get("authors", "Unknown")
            year = paper.get("year", "N/A")
            evidence_block += f"{i}. {title} ({authors}, {year})\n"

    # Build citation reference — keys only
    cite_block = ""
    if bib_keys:
        cite_block = f"## Citation Keys\n\n{', '.join(f'@{k}' for k in bib_keys[:15])}\n"

    # Keep outline context short — just the section structure
    outline_snippet = ""
    if outline_context:
        outline_snippet = f"## Section Structure\n\n{outline_context[:500]}\n"

    # CONCISE prompt — no verbose SKILL.md template
    topic = os.environ.get("PAPER_TOPIC", "retrieval-augmented code generation (RACG)")
    full_prompt = f"""Write the {section_name.title()} section for a systematic review on {topic}.

{evidence_block}

{cite_block}

{outline_snippet}

Rules:
- Write ONLY the section text. No markdown headers with #, no meta-commentary, no planning.
- Use APA 7th in-text citations: (Author, Year) or (Su et al., 2024).
- Cite ONLY from the keys above. Do NOT invent references.
- Academic tone, Q1 journal standard.
- Write 3-5 substantial paragraphs.

BEGIN SECTION:"""

    system_prompt = (
        "You are an expert academic writer publishing in Q1 journals. "
        "Write clear, precise, human-like academic prose. "
        "Never use AI-sounding phrases. Always verify claims against evidence. "
        "CRITICAL: Output ONLY the section text. No file paths, no meta-commentary, "
        "no summaries of what you wrote, no markdown code blocks. Just the section content."
    )

    return client.generate(
        prompt=full_prompt,
        system_prompt=system_prompt,
    )
