"""Module 7 - Frontend GUI (Tkinter, standard library only).

Required widgets: a search input box, a Search button and a read-only result area.
The GUI holds no search logic - it only calls ``SearchEngine.search`` and renders the answer.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from .engine import SearchEngine
from .query_processor import QueryError, SearchResponse

# --- palette: warm paper + ink + teal accent --------------------------------
BG, PANEL, INK, MUTED = "#f4efe6", "#fffdf8", "#1f2a2e", "#7a8487"
ACCENT, ACCENT_DK, MARK, RULE = "#0f766e", "#0b5a54", "#ffe08a", "#ddd5c4"
ERROR = "#b42318"

HINT = 'Operators: AND  OR  NOT  ( )   ·   "exact phrase"   ·   wildcards: * and ?'
Segment = tuple[str, str]   # (text, tag)


def render_response(resp: SearchResponse) -> list[Segment]:
    """Turn a SearchResponse into (text, tag) segments. Pure function - easy to unit test."""
    segs: list[Segment] = []
    n = len(resp.results)
    segs.append((f"{n} document{'s' if n != 1 else ''} matched  ", "count"))
    segs.append((f"for  {resp.query}\n", "muted"))
    for pattern, terms in resp.expansions.items():
        shown = ", ".join(terms[:12]) + (" …" if len(terms) > 12 else "") if terms else "no matching terms"
        segs.append((f"  {pattern}  →  {shown}\n", "muted"))
    segs.append(("\n", "plain"))
    if not n:
        segs.append(("Nothing found. Try fewer terms, OR, or a wildcard such as retriev*.\n", "plain"))
        return segs
    for i, r in enumerate(resp.results, 1):
        segs.append((f"{i:02d}  ", "rank"))
        segs.append((f"{r.title}\n", "title"))
        segs.append((f"     {r.name}  ·  {r.hit_count} hit{'s' if r.hit_count != 1 else ''}\n", "muted"))
        pad = "     "
        segs.append((pad, "plain"))
        last = 0
        for s, e in r.highlights:
            if s < last:
                continue
            segs.append((r.snippet[last:s], "plain"))
            segs.append((r.snippet[s:e], "mark"))
            last = e
        segs.append((r.snippet[last:] + "\n\n", "plain"))
    return segs


class SearchApp(tk.Tk):
    def __init__(self, engine: SearchEngine) -> None:
        super().__init__()
        self.engine = engine
        self.title("Lexicon · Boolean Search")
        self.geometry("920x660")
        self.minsize(640, 460)
        self.configure(bg=BG)
        fams = set(tkfont.families())
        self.f_ui = next((f for f in ("Segoe UI", "Helvetica Neue", "Inter", "DejaVu Sans") if f in fams), "TkDefaultFont")
        self.f_serif = next((f for f in ("Georgia", "Palatino", "DejaVu Serif") if f in fams), self.f_ui)
        self._build()
        self.entry.focus_set()

    # ------------------------------------------------------------ layout
    def _build(self) -> None:
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", padx=28, pady=(24, 6))
        tk.Label(head, text="Lexicon", bg=BG, fg=INK, font=(self.f_serif, 26, "bold")).pack(side="left")
        docs, terms = self.engine.stats
        tk.Label(head, text=f"{docs} documents  ·  {terms} indexed terms", bg=BG, fg=MUTED,
                 font=(self.f_ui, 10)).pack(side="right", pady=(12, 0))

        bar = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground=RULE)
        bar.pack(fill="x", padx=28, pady=(8, 4))
        self.query_var = tk.StringVar()
        self.entry = tk.Entry(bar, textvariable=self.query_var, font=(self.f_ui, 14), bd=0, bg=PANEL, fg=INK,
                              insertbackground=ACCENT, relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, ipady=11, padx=(14, 6))
        self.button = tk.Button(bar, text="Search", command=self.run_search, font=(self.f_ui, 11, "bold"),
                                bg=ACCENT, fg="white", activebackground=ACCENT_DK, activeforeground="white",
                                bd=0, relief="flat", padx=26, cursor="hand2")
        self.button.pack(side="right", fill="y")
        self.entry.bind("<Return>", lambda _e: self.run_search())

        tk.Label(self, text=HINT, bg=BG, fg=MUTED, font=(self.f_ui, 9), anchor="w").pack(fill="x", padx=30, pady=(0, 10))

        wrap = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground=RULE)
        wrap.pack(fill="both", expand=True, padx=28)
        scroll = tk.Scrollbar(wrap, orient="vertical", bd=0)
        scroll.pack(side="right", fill="y")
        self.results = tk.Text(wrap, wrap="word", state="disabled", bd=0, bg=PANEL, fg=INK, padx=18, pady=14,
                               font=(self.f_serif, 12), spacing1=2, spacing3=2, cursor="arrow",
                               yscrollcommand=scroll.set, selectbackground="#b8e0da", takefocus=0)
        self.results.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.results.yview)
        t = self.results.tag_configure
        t("plain", foreground=INK)
        t("count", foreground=ACCENT, font=(self.f_ui, 11, "bold"))
        t("muted", foreground=MUTED, font=(self.f_ui, 10))
        t("rank", foreground=ACCENT, font=(self.f_ui, 11, "bold"))
        t("title", foreground=INK, font=(self.f_serif, 14, "bold"))
        t("mark", background=MARK, foreground=INK)
        t("error", foreground=ERROR, font=(self.f_ui, 11, "bold"))

        self.status = tk.Label(self, text="Ready.", bg=BG, fg=MUTED, font=(self.f_ui, 9), anchor="w")
        self.status.pack(fill="x", padx=30, pady=(6, 10))
        self._show([("Type a query above and press Search.\n\n", "muted"),
                    ("Examples:\n", "muted"),
                    ('   index AND (boolean OR phrase)\n   "inverted index" NOT wildcard\n   retriev*   ·   t?ken*\n', "plain")])

    # ------------------------------------------------------------ actions
    def _show(self, segments: list[Segment]) -> None:
        self.results.configure(state="normal")
        self.results.delete("1.0", "end")
        for text, tag in segments:
            self.results.insert("end", text, tag)
        self.results.configure(state="disabled")      # read-only again
        self.results.yview_moveto(0)

    def run_search(self) -> None:
        query = self.query_var.get()
        try:
            resp = self.engine.search(query)
        except QueryError as exc:
            self._show([("Query problem\n", "error"), (f"{exc}\n", "plain")])
            self.status.config(text="Invalid query.")
            return
        except Exception:                                   # never let a bug close the window
            self._show([("Something went wrong while searching.\n", "error")])
            self.status.config(text="Unexpected error.")
            return
        self._show(render_response(resp))
        self.status.config(text=f"{len(resp.results)} result(s).")
