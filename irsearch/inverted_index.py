"""Module 4 - Inverted index construction.

Positional inverted index:   term -> { doc_id -> [word positions] }
Positions make exact phrase queries ("information retrieval") possible.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .document_loader import Document
from .normalizer import normalize
from .tokenizer import Token, tokenize


class InvertedIndex:
    def __init__(self) -> None:
        self.postings: dict[str, dict[int, list[int]]] = defaultdict(dict)
        self.documents: dict[int, Document] = {}
        self.doc_tokens: dict[int, list[Token]] = {}   # kept for snippets

    # -- construction ---------------------------------------------------
    def build(self, documents: Iterable[Document]) -> "InvertedIndex":
        for doc in documents:
            self.add_document(doc)
        return self

    def add_document(self, doc: Document) -> None:
        tokens = tokenize(doc.text)
        self.documents[doc.doc_id] = doc
        self.doc_tokens[doc.doc_id] = tokens
        for tok in tokens:
            self.postings[normalize(tok.text)].setdefault(doc.doc_id, []).append(tok.position)

    # -- lookups --------------------------------------------------------
    def docs_for(self, term: str) -> set[int]:
        return set(self.postings.get(term, ()))

    def positions(self, term: str, doc_id: int) -> list[int]:
        return self.postings.get(term, {}).get(doc_id, [])

    @property
    def all_doc_ids(self) -> set[int]:
        return set(self.documents)

    @property
    def vocabulary(self) -> list[str]:
        return sorted(self.postings)
