"""Module 3 - Text normalisation / case folding.

The *same* function is applied to document words and to query words, which is
what guarantees that "Retrieval", "RETRIEVAL" and "retrieval" are one term.
"""
from __future__ import annotations

import unicodedata


def normalize(word: str) -> str:
    """Unicode-normalise (NFKC) then case-fold. ``casefold`` is stronger than ``lower``
    (e.g. German 'Straße' -> 'strasse')."""
    return unicodedata.normalize("NFKC", word).casefold()
