"""Module 5 - Query processing.

Grammar (precedence: NOT > AND > OR; adjacent terms mean AND):

    query   := or_expr
    or_expr := and_expr ( "OR" and_expr )*
    and_expr:= not_expr ( ["AND"] not_expr )*
    not_expr:= "NOT" not_expr | atom
    atom    := WORD | WILDCARD_WORD | "quoted phrase" | "(" or_expr ")"

Safety: the query is only ever *parsed* (recursive descent) - never eval()'d, never
turned into a regex. Query length, token count and nesting depth are all capped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .inverted_index import InvertedIndex
from .normalizer import normalize
from .tokenizer import tokenize
from .wildcard import PermutermIndex, has_wildcard

MAX_QUERY_CHARS = 500
MAX_QUERY_TOKENS = 60
MAX_DEPTH = 20
OPERATORS = {"AND", "OR", "NOT"}


class QueryError(ValueError):
    """User-facing problem with the query text."""


# ---------------------------------------------------------------- lexer
_LEX = re.compile(r'\s*(?:(?P<phrase>"[^"]*")|(?P<paren>[()])|(?P<word>[^\s()"]+))')


def lex(query: str) -> list[tuple[str, str]]:
    if len(query) > MAX_QUERY_CHARS:
        raise QueryError(f"Query too long (max {MAX_QUERY_CHARS} characters).")
    out: list[tuple[str, str]] = []
    pos = 0
    query = query.strip()
    while pos < len(query):
        m = _LEX.match(query, pos)
        if not m:
            raise QueryError("Unbalanced quotation mark.")
        pos = m.end()
        if m.group("phrase") is not None:
            out.append(("PHRASE", m.group("phrase")[1:-1]))
        elif m.group("paren"):
            out.append((m.group("paren"), m.group("paren")))
        else:
            w = m.group("word")
            out.append((w, w) if w in OPERATORS else ("WORD", w))   # operators are UPPERCASE only
        if len(out) > MAX_QUERY_TOKENS:
            raise QueryError(f"Query too complex (max {MAX_QUERY_TOKENS} tokens).")
    return out


# ---------------------------------------------------------------- parser -> AST
# AST nodes are tuples: ("WORD", str) ("PHRASE", str) ("NOT", n) ("AND", a, b) ("OR", a, b)
class _Parser:
    def __init__(self, tokens):
        self.t, self.i = tokens, 0

    def peek(self):
        return self.t[self.i][0] if self.i < len(self.t) else None

    def take(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def parse(self):
        if not self.t:
            raise QueryError("Please enter a search query.")
        node = self.or_expr(0)
        if self.i < len(self.t):
            raise QueryError("Unexpected ')' in query.")
        return node

    def or_expr(self, depth):
        node = self.and_expr(depth)
        while self.peek() == "OR":
            self.take()
            node = ("OR", node, self.and_expr(depth))
        return node

    def and_expr(self, depth):
        node = self.not_expr(depth)
        while True:
            if self.peek() == "AND":
                self.take()
            elif self.peek() not in ("WORD", "PHRASE", "NOT", "("):
                return node
            node = ("AND", node, self.not_expr(depth))

    def not_expr(self, depth):
        if depth > MAX_DEPTH:
            raise QueryError("Query nested too deeply.")
        if self.peek() == "NOT":
            self.take()
            return ("NOT", self.not_expr(depth + 1))
        return self.atom(depth)

    def atom(self, depth):
        kind = self.peek()
        if kind in ("WORD", "PHRASE"):
            return self.take()
        if kind == "(":
            self.take()
            node = self.or_expr(depth + 1)
            if self.peek() != ")":
                raise QueryError("Missing closing ')'.")
            self.take()
            return node
        raise QueryError("Query is incomplete - an operator is missing a term.")


def parse_query(query: str):
    return _Parser(lex(query)).parse()


# ---------------------------------------------------------------- results
@dataclass
class SearchResult:
    doc_id: int
    name: str
    title: str
    snippet: str
    highlights: list[tuple[int, int]]   # (start, end) offsets inside ``snippet``
    hit_count: int


@dataclass
class SearchResponse:
    query: str
    results: list[SearchResult] = field(default_factory=list)
    expansions: dict[str, list[str]] = field(default_factory=dict)  # wildcard -> matched terms


# ---------------------------------------------------------------- evaluator
class QueryProcessor:
    def __init__(self, index: InvertedIndex) -> None:
        self.index = index
        self.permuterm = PermutermIndex(index.vocabulary)

    def search(self, query: str) -> SearchResponse:
        ast = parse_query(query)
        resp = SearchResponse(query=query)
        terms: set[str] = set()                       # positive terms, for highlighting
        doc_ids = self._eval(ast, resp, terms, negated=False)
        for doc_id in sorted(doc_ids):
            resp.results.append(self._make_result(doc_id, terms))
        resp.results.sort(key=lambda r: (-r.hit_count, r.doc_id))
        return resp

    def _eval(self, node, resp, terms, negated) -> set[int]:
        kind = node[0]
        if kind == "WORD":
            return self._word(node[1], resp, terms, negated)
        if kind == "PHRASE":
            return self._phrase(node[1], terms, negated)
        if kind == "NOT":
            return self.index.all_doc_ids - self._eval(node[1], resp, terms, not negated)
        a = self._eval(node[1], resp, terms, negated)
        b = self._eval(node[2], resp, terms, negated)
        return a & b if kind == "AND" else a | b

    def _word(self, raw, resp, terms, negated) -> set[int]:
        norm = normalize(raw)
        if has_wildcard(norm):
            try:
                matches = self.permuterm.expand(norm)
            except ValueError as exc:
                raise QueryError(str(exc)) from None
            resp.expansions[raw] = matches
            hits: set[int] = set()
            for term in matches:
                hits |= self.index.docs_for(term)
            if not negated:
                terms.update(matches)
            return hits
        # a plain word may itself tokenise into several terms (e.g. "e-mail") -> treat as phrase
        words = [normalize(t.text) for t in tokenize(norm)]
        if not words:
            return set()
        if len(words) == 1:
            if not negated:
                terms.add(words[0])
            return self.index.docs_for(words[0])
        return self._phrase_terms(words, terms, negated)

    def _phrase(self, text, terms, negated) -> set[int]:
        words = [normalize(t.text) for t in tokenize(text)]
        return self._phrase_terms(words, terms, negated) if words else set()

    def _phrase_terms(self, words, terms, negated) -> set[int]:
        candidates = self.index.docs_for(words[0])
        for w in words[1:]:
            candidates &= self.index.docs_for(w)
        hits = set()
        for doc_id in candidates:
            starts = set(self.index.positions(words[0], doc_id))
            for offset, w in enumerate(words[1:], 1):
                starts &= {p - offset for p in self.index.positions(w, doc_id)}
                if not starts:
                    break
            if starts:
                hits.add(doc_id)
        if not negated:
            terms.update(words)
        return hits

    # ------------------------------------------------------------ snippet
    def _make_result(self, doc_id, terms, radius=14) -> SearchResult:
        doc = self.index.documents[doc_id]
        toks = self.index.doc_tokens[doc_id]
        hit_idx = [i for i, t in enumerate(toks) if normalize(t.text) in terms]
        if not toks or not hit_idx:
            snippet = " ".join(doc.text.split())[:200]
            return SearchResult(doc_id, doc.name, doc.title, snippet, [], len(hit_idx))
        lo = max(0, hit_idx[0] - radius)
        hi = min(len(toks), hit_idx[0] + radius + 1)
        start, end = toks[lo].start, toks[hi - 1].end
        raw = doc.text[start:end]
        # collapse whitespace while keeping highlight offsets correct
        snippet_chars: list[str] = []
        mapping: dict[int, int] = {}
        prev_space = False
        for off, ch in enumerate(raw):
            if ch.isspace():
                if prev_space:
                    continue
                ch, prev_space = " ", True
            else:
                prev_space = False
            mapping[off] = len(snippet_chars)
            snippet_chars.append(ch)
        spans = []
        for i in hit_idx:
            if lo <= i < hi:
                s, e = toks[i].start - start, toks[i].end - start
                spans.append((mapping[s], mapping[e - 1] + 1))
        prefix = "… " if lo > 0 else ""
        suffix = " …" if hi < len(toks) else ""
        shift = len(prefix)
        return SearchResult(
            doc_id, doc.name, doc.title,
            prefix + "".join(snippet_chars) + suffix,
            [(s + shift, e + shift) for s, e in spans],
            len(hit_idx),
        )
