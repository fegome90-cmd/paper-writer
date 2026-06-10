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
# 500 is appropriate for academic prose — typical sentences are 150-250 chars,
# complex sentences with citations can reach 400-500.
_MAX_SENTENCE_LENGTH = 500

# Common academic abbreviations that should NOT trigger sentence splits.
# The sentence splitter replaces these with placeholders before splitting.
_ABBREVIATION_GUARDS: list[tuple[str, str]] = [
    (r"\bet al\.", "et al_"),
    (r"\be\.g\.", "e_g_"),
    (r"\bi\.e\.", "i_e_"),
    (r"\bDr\.", "Dr_"),
    (r"\bProf\.", "Prof_"),
    (r"\bFig\.", "Fig_"),
    (r"\bEq\.", "Eq_"),
    (r"\bvs\.", "vs_"),
    (r"\bcf\.", "cf_"),
    (r"\bapprox\.", "approx_"),
    (r"\bdept\.", "dept_"),
    (r"\bUniv\.", "Univ_"),
    (r"\bNo\.", "No_"),
    (r"\bVol\.", "Vol_"),
    (r"\bpp\.", "pp_"),
    (r"\bSr\.", "Sr_"),
    (r"\bJr\.", "Jr_"),
    (r"\bSt\.", "St_"),
]

# Strong claims without hedging
_UNBACKED_CLAIMS_LIST: list[str] = [
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
_UNBACKED_CLAIMS_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in _UNBACKED_CLAIMS_LIST) + r")\b",
    re.IGNORECASE,
)

# Forbidden phrases in academic writing
_FORBIDDEN_PHRASES_LIST: list[str] = [
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
_FORBIDDEN_PHRASES_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in _FORBIDDEN_PHRASES_LIST) + r")\b",
    re.IGNORECASE,
)

# Informal words/phrases
_INFORMAL_WORDS_LIST: list[str] = [
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
_INFORMAL_WORDS_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in _INFORMAL_WORDS_LIST) + r")\b",
    re.IGNORECASE,
)


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
    if not text:
        return []
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
    # Protect academic abbreviations before splitting (e.g. → e_g_, et al. → et al_)
    safe_text = text
    for pattern, replacement in _ABBREVIATION_GUARDS:
        safe_text = re.sub(pattern, replacement, safe_text)
    sentences = re.split(r"[.!?]+", safe_text)
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
    for match in _UNBACKED_CLAIMS_RE.finditer(text):
        claim = match.group().lower()
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
    for match in _FORBIDDEN_PHRASES_RE.finditer(text):
        phrase = match.group().lower()
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
    for match in _INFORMAL_WORDS_RE.finditer(text):
        word = match.group().lower()
        findings.append(
            {
                "code": "informal_language",
                "severity": "warning",
                "message": f"Informal language detected: '{word}'. Use formal academic tone.",
                "location": location,
            }
        )

    return findings
