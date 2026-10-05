"""Look up the few facts a customer message needs.

Knowledge files are split at Markdown headings and ranked with BM25. That is
enough for a pack-sized knowledge base and keeps the harness free of an
embedding service; swap in a vector index behind `KnowledgeBase.search` when a
pack outgrows it.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from hamilton_harness.pack.schema import KnowledgeDoc

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are as at be but by can do for from has have how i if in is it me my of on or "
    "so that the their there they this to was we what when where which who will with you "
    "your".split()
)


@dataclass(frozen=True)
class Chunk:
    source: str
    heading: str
    text: str

    def render(self) -> str:
        return f"[{self.source} > {self.heading}]\n{self.text}"


def tokenize(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS]


def split_markdown(doc: KnowledgeDoc) -> list[Chunk]:
    """One chunk per heading, carrying its parent headings as a trail."""
    chunks: list[Chunk] = []
    # (depth, title) of each open heading. Depths are kept, not assumed, because a
    # file may start at "##" or skip a level.
    trail: list[tuple[int, str]] = []
    body: list[str] = []

    def flush() -> None:
        text = "\n".join(body).strip()
        if text:
            heading = " > ".join(title for _, title in trail)
            chunks.append(Chunk(doc.source, heading or doc.source, text))
        body.clear()

    for line in doc.text.splitlines():
        match = _HEADING.match(line)
        if match:
            flush()
            depth = len(match.group(1))
            while trail and trail[-1][0] >= depth:
                trail.pop()
            trail.append((depth, match.group(2).strip()))
        else:
            body.append(line)
    flush()
    return chunks


class KnowledgeBase:
    def __init__(self, docs: list[KnowledgeDoc], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = [chunk for doc in docs for chunk in split_markdown(doc)]
        self._k1 = k1
        self._b = b
        # Headings count as content: "Refund timing" should match "refund".
        self._terms = [Counter(tokenize(f"{c.heading} {c.text}")) for c in self.chunks]
        self._lengths = [sum(t.values()) for t in self._terms]
        self._avg_length = sum(self._lengths) / len(self._lengths) if self._lengths else 0.0
        self._doc_freq: Counter[str] = Counter()
        for terms in self._terms:
            self._doc_freq.update(terms.keys())

    def _idf(self, term: str) -> float:
        n = len(self.chunks)
        df = self._doc_freq.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def search(self, query: str, *, top_k: int = 3) -> list[Chunk]:
        """Best matching chunks, best first. Chunks that share no word are left out."""
        terms = tokenize(query)
        scored: list[tuple[float, int]] = []
        for index, counts in enumerate(self._terms):
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if not tf:
                    continue
                norm = 1 - self._b + self._b * self._lengths[index] / self._avg_length
                score += self._idf(term) * tf * (self._k1 + 1) / (tf + self._k1 * norm)
            if score > 0:
                scored.append((score, index))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [self.chunks[index] for _, index in scored[:top_k]]
