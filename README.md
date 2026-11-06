# Lexicon – Boolean Search Engine (Python, Tkinter)

Pure standard-library project: no pip installs, no network, no `eval`.

```
python main.py                 # searches data/documents
python main.py path/to/folder  # your own folder of .txt files
python -m unittest discover -s tests
```
(Tkinter ships with the python.org installers; on Debian/Ubuntu: `sudo apt install python3-tk`.)

## Modules
| # | File | Job |
|---|------|-----|
| 1 | `irsearch/document_loader.py` | safely reads `.txt` files |
| 2 | `irsearch/tokenizer.py` | text → tokens with spans & positions |
| 3 | `irsearch/normalizer.py` | Unicode NFKC + case folding |
| 4 | `irsearch/inverted_index.py` | positional inverted index |
| 5 | `irsearch/query_processor.py` | lexer, recursive-descent parser, boolean/phrase evaluation, snippets |
| 6 | `irsearch/wildcard.py` | permuterm index for `*` and `?` |
| 7 | `irsearch/gui.py` | Tkinter UI: input box, Search button, read-only results |

`irsearch/engine.py` wires 1-6 together; `main.py` starts the GUI.

## Query syntax
`AND`, `OR`, `NOT` (UPPERCASE; lowercase `and` is an ordinary word), parentheses, `"exact phrase"`,
`*` / `?` wildcards. Precedence NOT > AND > OR; neighbouring terms mean AND.

## Safety measures
* Query is parsed, never evaluated or compiled to a regex (no injection / ReDoS); caps on length, tokens, nesting, wildcard count and expansions.
* Loader: `.txt` only, no symlinks, no recursion, 5 MB/file cap, read-only, bad bytes replaced.
* Result area is a disabled `Text` widget (read-only); it is unlocked only for the instant the app writes into it.
* Search errors are shown inline; unexpected errors never close the app.
