import sys, types, unittest, tempfile, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from irsearch.document_loader import load_documents, DocumentLoadError
from irsearch.engine import SearchEngine
from irsearch.normalizer import normalize
from irsearch.query_processor import QueryError, parse_query
from irsearch.tokenizer import tokenize
from irsearch.wildcard import glob_match, PermutermIndex

DOCS = ROOT / "data" / "documents"


def names(resp):
    return {r.name for r in resp.results}


class Basics(unittest.TestCase):
    def test_tokenize(self):
        self.assertEqual([t.text for t in tokenize("Hello, World_x 42!")], ["Hello", "World", "x", "42"])

    def test_normalize(self):
        self.assertEqual(normalize("RETRIEVAL"), "retrieval")
        self.assertEqual(normalize("Straße"), "strasse")

    def test_loader_errors(self):
        with self.assertRaises(DocumentLoadError):
            load_documents(ROOT / "nope")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(DocumentLoadError):
                load_documents(d)

    def test_loader_skips_symlink_and_non_txt(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.txt").write_text("alpha")
            Path(d, "b.md").write_text("beta")
            os.symlink("/etc/passwd", Path(d, "c.txt"))
            Path(d, "bad.txt").write_bytes(b"ok \xff\xfe bytes")
            self.assertEqual([x.name for x in load_documents(d)], ["a.txt", "bad.txt"])


class Search(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = SearchEngine(DOCS)

    def test_case_insensitive(self):
        self.assertEqual(names(self.e.search("RETRIEVAL")), names(self.e.search("retrieval")))
        self.assertTrue(names(self.e.search("RETRIEVAL")))

    def test_and_or_not(self):
        a, b = names(self.e.search("index")), names(self.e.search("phrase"))
        self.assertEqual(names(self.e.search("index AND phrase")), a & b)
        self.assertEqual(names(self.e.search("index OR phrase")), a | b)
        self.assertEqual(names(self.e.search("index NOT phrase")), a - b)
        self.assertEqual(names(self.e.search("index phrase")), a & b)       # implicit AND

    def test_lowercase_and_is_a_word(self):
        self.assertIn("boolean_retrieval.txt", names(self.e.search("and")))

    def test_precedence_and_parens(self):
        a, b, c = (names(self.e.search(w)) for w in ("tokenization", "phrase", "index"))
        self.assertNotEqual(a | (b & c), (a | b) & c)           # the words really distinguish the two readings
        self.assertEqual(names(self.e.search("tokenization OR phrase AND index")), a | (b & c))
        self.assertEqual(names(self.e.search("(tokenization OR phrase) AND index")), (a | b) & c)

    def test_phrase(self):
        self.assertEqual(names(self.e.search('"information retrieval"')) ,
                         {"inverted_index.txt", "tokenization.txt"} & names(self.e.search('"information retrieval"')))
        self.assertIn("tokenization.txt", names(self.e.search('"information retrieval"')))
        self.assertEqual(names(self.e.search('"retrieval information"')), set())

    def test_wildcards(self):
        r = self.e.search("retriev*")
        self.assertIn("wildcard_queries.txt", names(r))
        self.assertIn("retrieval", r.expansions["retriev*"])
        self.assertIn("tokenization.txt", names(self.e.search("t?ken*")))
        self.assertIn("python_programming.txt", names(self.e.search("*thon")))
        self.assertIn("python_programming.txt", names(self.e.search("p*n")))
        self.assertEqual(names(self.e.search("zzz*")), set())
        self.assertEqual(names(self.e.search("*")), set())

    def test_wildcard_combined(self):
        a = names(self.e.search("retriev* AND NOT boolean"))
        self.assertNotIn("boolean_retrieval.txt", a)
        self.assertTrue(a)

    def test_highlights_in_range(self):
        for r in self.e.search("index OR wildcard*").results:
            for s, t in r.highlights:
                self.assertTrue(0 <= s < t <= len(r.snippet))

    def test_errors(self):
        for bad in ["", "   ", "(index", "index)", "index AND", "NOT", '"unclosed', "AND index", "x" * 600,
                    "(" * 50 + "a" + ")" * 50, "a ? ? ? ? ? ? ? b*?*?*?*"]:
            with self.assertRaises(QueryError, msg=bad):
                self.e.search(bad)

    def test_hostile_input_is_inert(self):
        for q in ["__import__('os').system('x')", "(a+)+$", "[[[", "a\\", "*" * 5 + "a"]:
            try:
                self.e.search(q)
            except QueryError:
                pass


class Wildcard(unittest.TestCase):
    def test_glob(self):
        self.assertTrue(glob_match("a*b*c", "aXXbYYc"))
        self.assertFalse(glob_match("a*b*c", "aXXbYY"))
        self.assertTrue(glob_match("h?llo", "hello"))
        self.assertFalse(glob_match("h?llo", "hllo"))

    def test_no_backtracking_blowup(self):
        self.assertFalse(glob_match("*a" * 5 + "b", "a" * 5000))

    def test_permuterm_matches_bruteforce(self):
        vocab = ["hello", "help", "hero", "halo", "hell", "world", "word", "a", "ab"]
        p = PermutermIndex(vocab)
        for pat in ["h*", "*lo", "h*o", "he?p", "h?l*", "*o*", "?", "??", "w*r*"]:
            self.assertEqual(p.expand(pat), sorted(t for t in vocab if glob_match(pat, t)), pat)


class GuiWiring(unittest.TestCase):
    """Drives the real GUI code. If Tkinter is missing (headless sandbox) a stub is used."""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter  # noqa
            cls.stubbed = False
        except ModuleNotFoundError:
            from unittest.mock import MagicMock
            class W:
                def __init__(self, *a, **k): self.log = []
                def __getattr__(self, n): return MagicMock()
            tk = types.ModuleType("tkinter")
            for n in ("Tk", "Frame", "Label", "Entry", "Button", "Scrollbar"):
                setattr(tk, n, type(n, (W,), {}))
            class Text(W):
                def __init__(self, *a, **k):
                    super().__init__(); self.state = k.get("state"); self.buf = []
                def configure(self, **k): self.state = k.get("state", self.state)
                config = configure
                def delete(self, *a): self.buf.clear()
                def insert(self, idx, text, tag):
                    assert self.state == "normal", "result area written while read-only"
                    self.buf.append((text, tag))
            class Var:
                def __init__(self): self.v = ""
                def get(self): return self.v
                def set(self, v): self.v = v
            tk.Text, tk.StringVar = Text, Var
            font = types.ModuleType("tkinter.font"); font.families = lambda: ["DejaVu Sans"]
            tk.font = font
            sys.modules["tkinter"], sys.modules["tkinter.font"] = tk, font
            cls.stubbed = True

    def test_render(self):
        from irsearch import gui
        e = SearchEngine(DOCS)
        segs = gui.render_response(e.search("retriev* AND index"))
        self.assertIn("documents matched", "".join(s for s, _ in segs))
        self.assertTrue(any(t == "mark" for _, t in segs))
        self.assertIn("Nothing found", "".join(s for s, _ in gui.render_response(e.search("zzzzqq"))))

    def test_app_flow(self):
        if not self.stubbed:
            self.skipTest("real Tk: needs a display")
        from irsearch import gui
        app = gui.SearchApp(SearchEngine(DOCS))
        app.query_var.set("retriev* AND (index OR phrase)")
        app.run_search()
        self.assertEqual(app.results.state, "disabled")
        self.assertTrue(any(t == "title" for _, t in app.results.buf))
        app.query_var.set("(oops")
        app.run_search()
        self.assertEqual(app.results.state, "disabled")
        self.assertEqual(app.results.buf[0], ("Query problem\n", "error"))


if __name__ == "__main__":
    unittest.main()
