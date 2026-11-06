"""Module 6 - Wildcard processing.

Supports ``*`` (any run of characters, incl. none) and ``?`` (exactly one character).

Uses a *permuterm index*: every term ``hello`` is stored under all rotations of
``hello$`` (``hello$``, ``ello$h``, ``llo$he`` ...). A wildcard query is rotated so
its wildcard sits at the end, which turns it into a fast prefix lookup (binary search).
Candidates are then verified with a small iterative glob matcher.

Safety: no user text is ever compiled into a regular expression, so a hostile pattern
cannot cause catastrophic backtracking. The matcher is iterative, the number of
wildcard characters is capped, and the number of expansions is capped.
"""
from __future__ import annotations

from bisect import bisect_left

MAX_WILDCARDS = 6
MAX_EXPANSIONS = 500
_WILD = "*?"


def has_wildcard(term: str) -> bool:
    return any(c in term for c in _WILD)


def glob_match(pattern: str, text: str) -> bool:
    """Iterative glob matching with ``*`` and ``?`` (worst case O(len(pattern)*len(text)))."""
    p = t = 0
    star = -1
    mark = 0
    while t < len(text):
        if p < len(pattern) and pattern[p] == "*":
            star, mark = p, t
            p += 1
        elif p < len(pattern) and (pattern[p] == "?" or pattern[p] == text[t]):
            p += 1
            t += 1
        elif star != -1:
            p = star + 1
            mark += 1
            t = mark
        else:
            return False
    while p < len(pattern) and pattern[p] == "*":
        p += 1
    return p == len(pattern)


class PermutermIndex:
    def __init__(self, vocabulary) -> None:
        pairs = []
        for term in vocabulary:
            padded = term + "$"
            for i in range(len(padded)):
                pairs.append((padded[i:] + padded[:i], term))
        pairs.sort()
        self._keys = [k for k, _ in pairs]
        self._terms = [t for _, t in pairs]

    def expand(self, pattern: str) -> list[str]:
        """Return the vocabulary terms matching ``pattern`` (already normalised)."""
        if sum(pattern.count(c) for c in _WILD) > MAX_WILDCARDS:
            raise ValueError(f"Too many wildcard characters (max {MAX_WILDCARDS}).")
        if pattern.strip("*") == "":
            return []                                  # bare '*' would match everything
        last = max(pattern.rfind("*"), pattern.rfind("?"))
        rotated = (pattern + "$")[last + 1:] + pattern[: last + 1]
        cut = min((rotated.find(c) for c in _WILD if c in rotated), default=len(rotated))
        prefix = rotated[:cut]

        found: set[str] = set()
        i = bisect_left(self._keys, prefix)
        while i < len(self._keys) and self._keys[i].startswith(prefix):
            term = self._terms[i]
            if term not in found and glob_match(pattern, term):
                found.add(term)
                if len(found) >= MAX_EXPANSIONS:
                    break
            i += 1
        return sorted(found)
