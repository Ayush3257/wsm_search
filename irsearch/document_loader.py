"""Module 1 - Document loading.

Safely reads plain-text (.txt) files from a single folder.

Safety rules enforced here:
  * only regular ``*.txt`` files directly inside the folder (no recursion)
  * symlinks are skipped, so a link can never point outside the folder
  * per-file size cap and total file-count cap
  * decoded as UTF-8 with ``errors="replace"`` - bad bytes never crash the app
  * files are only ever opened read-only
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MAX_FILE_BYTES = 5 * 1024 * 1024   # 5 MB per document
MAX_FILES = 5000


class DocumentLoadError(Exception):
    """Raised when the document folder is missing or unusable."""


@dataclass(frozen=True)
class Document:
    doc_id: int
    name: str      # file name, e.g. "inverted_index.txt"
    text: str

    @property
    def title(self) -> str:
        return self.name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()


def load_documents(folder: str | Path) -> list[Document]:
    root = Path(folder)
    if not root.is_dir():
        raise DocumentLoadError(f"Document folder not found: {root}")

    docs: list[Document] = []
    for path in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if len(docs) >= MAX_FILES:
            break
        if path.suffix.lower() != ".txt" or path.is_symlink() or not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                text = fh.read(MAX_FILE_BYTES)
        except OSError:
            continue  # unreadable file: skip, never crash
        docs.append(Document(doc_id=len(docs), name=path.name, text=text))

    if not docs:
        raise DocumentLoadError(f"No .txt documents found in: {root}")
    return docs
