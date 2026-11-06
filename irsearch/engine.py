"""Small facade that wires the modules together (used by the GUI, tests and CLI)."""
from __future__ import annotations

from pathlib import Path

from .document_loader import load_documents
from .inverted_index import InvertedIndex
from .query_processor import QueryProcessor, SearchResponse


class SearchEngine:
    def __init__(self, folder: str | Path) -> None:
        self.documents = load_documents(folder)
        self.index = InvertedIndex().build(self.documents)
        self.processor = QueryProcessor(self.index)

    @property
    def stats(self) -> tuple[int, int]:
        return len(self.documents), len(self.index.postings)

    def search(self, query: str) -> SearchResponse:
        return self.processor.search(query)
