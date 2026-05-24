"""Prose style validation rules.

Pure domain functions that check manuscript text for style issues:
passive voice, long sentences, etc. No file I/O or subprocess calls.
"""

import re
from typing import Any

# Passive voice pattern: was/were/is/are/been/being + past participle
_PASSIVE_RE = re.compile(
    r"\b(was|were|is|are|been|being)\s+(\w+ed|\w+en)\b",
    re.IGNORECASE,
)

# Sentence length threshold (characters)
_MAX_SENTENCE_LENGTH = 300


def validate_style(text: str, file_label: str = "") -> list[dict[str, Any]]:
    """Check text for style issues.

    Checks:
    - Passive voice constructions
    - Overly long sentences

    Args:
        text: Manuscript text content.
        file_label: Optional file name for finding location.

    Returns:
        List of finding dicts.
    """
    findings: list[dict[str, Any]] = []

    # Check passive voice
    for match in _PASSIVE_RE.finditer(text):
        findings.append(
            {
                "code": "passive_voice",
                "severity": "warning",
                "message": f"Possible passive voice: '{match.group()}'.",
                "location": file_label or "manuscript",
            }
        )

    # Check sentence length
    sentences = re.split(r"[.!?]+", text)
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > _MAX_SENTENCE_LENGTH:
            findings.append(
                {
                    "code": "long_sentence",
                    "severity": "warning",
                    "message": (
                        f"Sentence exceeds {_MAX_SENTENCE_LENGTH} characters "
                        f"({len(sentence)} chars). Consider splitting."
                    ),
                    "location": file_label or "manuscript",
                }
            )

    return findings
