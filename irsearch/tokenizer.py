"""Module 2 - Tokenization.

Splits raw text into word tokens and remembers where each one sits
(character span for snippets/highlighting, word position for phrase queries).
Tokens are returned *un-normalised*; case folding lives in ``normalizer``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# A word = run of letters/digits (Unicode aware). Underscores and punctuation split words.
_WORD = re.compile(r"[^\W_]+", re.UNICODE)


@dataclass(frozen=True)
class Token:
    text: str      # surface form, exactly as written
    start: int     # character offsets in the source text
    end: int
    position: int  # 0-based word index in the document


def tokenize(text: str) -> list[Token]:
    return [Token(m.group(), m.start(), m.end(), i) for i, m in enumerate(_WORD.finditer(text))]
