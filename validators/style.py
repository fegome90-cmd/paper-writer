"""Prose style validation rules.

Pure domain functions that check manuscript text for style issues:
passive voice, long sentences, strong claims, informal language,
and forbidden phrases. No file I/O or subprocess calls.
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

# Strong claims without hedging
_UNBACKED_CLAIMS: list[str] = [
    "proves that",
    "proven that",
    "conclusively",
    "without a doubt",
    "it is clear that",
    "it is obvious that",
    "it is evident that",
    "undeniably",
    "unquestionably",
    "definitively",
    "for the first time",
    "never before",
    "first ever",
    "no study has",
    "no research has",
    "we prove",
    "we have proven",
    "this proves",
    "this confirms",
    "this establishes",
]

# Forbidden phrases in academic writing
_FORBIDDEN_PHRASES: list[str] = [
    "in order to",
    "due to the fact that",
    "for the purpose of",
    "in the event that",
    "in spite of the fact that",
    "on account of",
    "the reason why is that",
    "it is important to note that",
    "it should be noted that",
    "it is worth mentioning that",
    "as a matter of fact",
    "at the end of the day",
    "needless to say",
    "it goes without saying",
]

# Informal words/phrases
_INFORMAL_WORDS: list[str] = [
    "basically",
    "literally",
    "obviously",
    "pretty much",
    "kind of",
    "sort of",
    "a lot",
    "lots of",
    "stuff",
    "things",
    "gonna",
    "wanna",
    "gotta",
]


def validate_style(text: str, file_label: str = "") -> list[dict[str, Any]]:
    """Check text for style issues.

    Checks:
    - Passive voice constructions
    - Overly long sentences
    - Unbacked strong claims
    - Forbidden academic phrases
    - Informal language

    Args:
        text: Manuscript text content.
        file_label: Optional file name for finding location.

    Returns:
        List of finding dicts.
    """
    findings: list[dict[str, Any]] = []
    location = file_label or "manuscript"

    # Check passive voice
    for match in _PASSIVE_RE.finditer(text):
        findings.append(
            {
                "code": "passive_voice",
                "severity": "warning",
                "message": f"Possible passive voice: '{match.group()}'.",
                "location": location,
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
                    "location": location,
                }
            )

    # Check unbacked strong claims
    text_lower = text.lower()
    for claim in _UNBACKED_CLAIMS:
        if claim in text_lower:
            findings.append(
                {
                    "code": "unbacked_claim",
                    "severity": "warning",
                    "message": (
                        f"Strong claim without hedging: '{claim}'. "
                        f"Consider adding a qualifier (e.g., 'suggests', 'may') "
                        f"and cite supporting evidence."
                    ),
                    "location": location,
                }
            )

    # Check forbidden phrases
    for phrase in _FORBIDDEN_PHRASES:
        if phrase in text_lower:
            findings.append(
                {
                    "code": "forbidden_phrase",
                    "severity": "error",
                    "message": (
                        f"Forbidden phrase in academic writing: '{phrase}'. "
                        f"Remove or replace with precise language."
                    ),
                    "location": location,
                }
            )

    # Check informal language
    for word in _INFORMAL_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", text_lower):
            findings.append(
                {
                    "code": "informal_language",
                    "severity": "warning",
                    "message": f"Informal language detected: '{word}'. Use formal academic tone.",
                    "location": location,
                }
            )

    return findings
