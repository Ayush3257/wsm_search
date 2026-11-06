"""Entry point:  python main.py [documents_folder]"""
import sys
from pathlib import Path

from irsearch.document_loader import DocumentLoadError
from irsearch.engine import SearchEngine

DEFAULT_FOLDER = Path(__file__).parent / "data" / "documents"


def main() -> int:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FOLDER
    try:
        engine = SearchEngine(folder)
    except DocumentLoadError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    from irsearch.gui import SearchApp      # imported late so the engine works without a display
    SearchApp(engine).mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
