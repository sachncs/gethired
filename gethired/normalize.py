"""Text normalisation helpers.

Used by the validator (grounding, ATS gates) and by the plagiarism check.
All helpers are pure functions with no I/O.
"""

from __future__ import annotations

import re
from typing import Final

NUMBER_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(\d[\d,]*)\s*\+?"),
    re.compile(r"\$(\d[\d,]*(?:\.\d+)?)"),
    re.compile(r"(\d+(?:\.\d+)?)\s*%"),
)

NUMBER_WORDS: Final[dict[str, int]] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
    "million": 1000000,
    "billion": 1000000000,
}

LATEX_RE: Final[re.Pattern[str]] = re.compile(
    r"\\(?:textbf|textsc|emph|textit|href)\s*\{([^}]*)\}(?:\{([^}]*)\})?"
)

MATH_RE: Final[re.Pattern[str]] = re.compile(r"\$([^$]*)\$")

ESCAPE_RE: Final[re.Pattern[str]] = re.compile(r"\\([&%$#_{}~^])")

WORD_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z][A-Za-z0-9+#.-]*")

WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")


def numbers(text: str) -> set[int]:
    """Return the set of integers expressed numerically in ``text``.

    Handles forms like ``10000``, ``10,000+``, ``10K``, ``10k``, ``$5000``,
    ``5%``, ``5.5``, and ``ten thousand``.
    """
    found: set[int] = set()
    for pattern in NUMBER_PATTERNS:
        for match in pattern.finditer(text):
            digits = match.group(1).replace(",", "")
            try:
                found.add(int(float(digits)))
            except ValueError:
                continue

    for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*([kKmMbB])\b", text):
        digits = float(match.group(1))
        suffix = match.group(2).lower()
        multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[suffix]
        found.add(int(digits * multiplier))

    for match in re.finditer(
        r"\b((?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
        r"nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|"
        r"thousand|million|billion)(?:[\s-]+(?:zero|one|two|three|four|five|six|"
        r"seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
        r"seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
        r"eighty|ninety|hundred|thousand|million|billion))*)",
        text.lower(),
    ):
        phrase = match.group(1)
        tokens = [token for token in re.split(r"[\s-]+", phrase) if token]
        value = 0
        current = 0
        matched_any = False
        for token in tokens:
            if token not in NUMBER_WORDS:
                continue
            matched_any = True
            n = NUMBER_WORDS[token]
            if n in {100, 1000, 1000000, 1000000000}:
                current = max(current, 1) * n if current else n
            else:
                current += n
        if matched_any:
            value += current
            found.add(value)

    return found


def strip_latex(text: str) -> str:
    """Remove common LaTeX command wrappers, returning plain text."""
    working = LATEX_RE.sub(lambda m: m.group(2) or m.group(1) or "", text)
    working = MATH_RE.sub(lambda m: m.group(1), working)
    working = ESCAPE_RE.sub(lambda m: m.group(1), working)
    return working


def flatten(text: str) -> str:
    """Collapse whitespace, strip, and lowercase; used by the ATS PDF-vs-TXT gate."""
    return WHITESPACE_RE.sub(" ", text).strip().lower()


def tokenize(text: str) -> tuple[str, ...]:
    """Tokenise text into normalised words for n-gram overlap detection."""
    return tuple(token.lower() for token in WORD_RE.findall(text))


def verb(token: str) -> bool:
    """Lightweight action-verb check used by the ATS ``ACTION_VERBS_FIRST`` gate.

    Args:
        token: The first word of a bullet.

    Returns:
        ``True`` if ``token`` looks like an action verb.
    """
    return VERB_LOOKUP.match(token) is not None


VERB_LOOKUP: Final[re.Pattern[str]] = re.compile(
    r"^(?:"
    r"a(?:chieved|dded|dministered|dvised|llocated|nalyzed|pplied|ssembled|ssessed|uthored|udited)"
    r"|b(?:uilt|oosted|rought|udgeted)"
    r"|c(?:oached|oded|ollaborated|ollected|ommunicated|ompleted|omposed|onceived|onducted|onfigured|onstructed|ontributed|onverted|reated|ultivated|ut)"
    r"|d(?:ecreased|elivered|deployed|esigned|etermined|eveloped|irected|iscovered|rove|rafted)"
    r"|e(?:ngineered|stablished|valuated|xpanded|xpedited|xtracted)"
    r"|f(?:acilitated|inalised|inalized|ormulated|ounded)"
    r"|g(?:enerated|uided)"
    r"|h(?:anded|eaded|elped)"
    r"|i(?:dentified|implemented|improved|increased|nitiated|ntegrated|ntegrated|nvented|nvestigated)"
    r"|l(?:aunched|ed|everaged)"
    r"|m(?:anaged|apped|igrated|odeled|odelled|odified|onitored)"
    r"|n(?:egotiated)"
    r"|o(?:rganized|rchestrated|utlined)"
    r"|p(?:articipated|erformed|lanned|repared|resented|rioritised|rioritized|roduced|rogrammed|romoted|roposed|rototyped|rovided)"
    r"|r(?:ecommended|educed|efactored|eleased|eliably|esolved|esourced|estored|estructured|esulted|etained|eviewed|evised)"
    r"|s(?:aved|caled|cheduled|ecured|elected|et|implified|old|olved|pecified|tarted|teered|treamlined|tructured|ucceeded|uggested|upervised|upported|ynced)"
    r"|t(?:rained|ransformed|uned|urned)"
    r"|u(?:ndertook|pdated|sed|tilized)"
    r"|v(?:alidated|erified)"
    r"|w(?:on|orked|rote)"
    r")$",
    re.IGNORECASE,
)


def ngrams(tokens: tuple[str, ...], n: int) -> tuple[str, ...]:
    """Return all ``n``-grams from ``tokens`` as space-joined strings."""
    if n <= 0 or len(tokens) < n:
        return ()
    return tuple(" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1))


__all__ = [
    "flatten",
    "ngrams",
    "numbers",
    "strip_latex",
    "tokenize",
    "verb",
]
