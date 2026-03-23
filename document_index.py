from __future__ import annotations

from dataclasses import dataclass
import html
import re
from typing import Dict, List, Optional


@dataclass
class Occurrence:
    doc_id: str
    token_index: int
    char_start: int
    char_end: int


class DocumentIndex:
    def __init__(self, trie) -> None:
        self.trie = trie
        self.documents: Dict[str, str] = {}
        self.postings: Dict[str, List[Occurrence]] = {}
        self._vocab_seen = set()

    def _normalize(self, text: str) -> str:
        return text.lower().strip()

    def _tokenize_with_positions(self, text: str):
        pattern = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")
        for match in pattern.finditer(text):
            word = self._normalize(match.group(0))
            yield word, match.start(), match.end()

    def add_document(self, doc_id: str, text: str) -> None:
        if not doc_id:
            raise ValueError("doc_id cannot be empty")
        if doc_id in self.documents:
            raise ValueError(f"document '{doc_id}' already exists")

        self.documents[doc_id] = text

        token_index = 0
        for word, char_start, char_end in self._tokenize_with_positions(text):
            if word not in self.postings:
                self.postings[word] = []

            self.postings[word].append(
                Occurrence(
                    doc_id=doc_id,
                    token_index=token_index,
                    char_start=char_start,
                    char_end=char_end,
                )
            )

            if word not in self._vocab_seen:
                self.trie.insert(word)
                self._vocab_seen.add(word)

            token_index += 1

    def get_occurrences(self, word: str) -> List[Occurrence]:
        word = self._normalize(word)
        return self.postings.get(word, [])

    def get_document_text(self, doc_id: str) -> Optional[str]:
        return self.documents.get(doc_id)

    def _make_snippet(self, text: str, start: int, end: int, window: int = 40) -> str:
        left = max(0, start - window)
        right = min(len(text), end + window)

        snippet = text[left:right]
        rel_start = start - left
        rel_end = rel_start + (end - start)

        safe = html.escape(snippet)
        # to preserve exact positions, build from raw slices instead of escaped index math
        before = html.escape(snippet[:rel_start])
        hit = html.escape(snippet[rel_start:rel_end])
        after = html.escape(snippet[rel_end:])

        snippet_html = before + "<mark>" + hit + "</mark>" + after

        if left > 0:
            snippet_html = "..." + snippet_html
        if right < len(text):
            snippet_html += "..."

        return snippet_html

    def _render_document_with_highlights(self, text: str, spans: List[tuple[int, int]]) -> str:
        """
        Render full text HTML with <mark id='hit-N'>...</mark> inserted.
        spans must be sorted and non-overlapping.
        """
        if not spans:
            return "<pre class='doc-pre'>" + html.escape(text) + "</pre>"

        parts = []
        last = 0

        for i, (start, end) in enumerate(spans):
            if start < last:
                continue

            parts.append(html.escape(text[last:start]))
            parts.append(f"<mark id='hit-{i}'>{html.escape(text[start:end])}</mark>")
            last = end

        parts.append(html.escape(text[last:]))

        return "<pre class='doc-pre'>" + "".join(parts) + "</pre>"

    def search_prefix(
        self,
        prefix: str,
        doc_id: str | None = None,
        max_words: int = 20,
        max_occurrences: int = 200,
        snippet_window: int = 40,
    ) -> dict:
        prefix = self._normalize(prefix)
        selected_doc = doc_id or "all"

        if not prefix:
            return {
                "prefix": prefix,
                "selected_doc": selected_doc,
                "matched_words": [],
                "results": [],
                "document_html": "",
                "document_doc_id": None,
            }

        matched_words = self.trie.autocomplete(prefix, k=None)
        matched_words = matched_words[:max_words]

        results = []
        for word in matched_words:
            for occ in self.postings.get(word, []):
                if doc_id and doc_id != "all" and occ.doc_id != doc_id:
                    continue

                text = self.documents[occ.doc_id]
                results.append(
                    {
                        "word": word,
                        "doc_id": occ.doc_id,
                        "token_index": occ.token_index,
                        "char_start": occ.char_start,
                        "char_end": occ.char_end,
                        "snippet": self._make_snippet(
                            text,
                            occ.char_start,
                            occ.char_end,
                            window=snippet_window,
                        ),
                    }
                )

        results.sort(key=lambda x: (x["doc_id"], x["char_start"]))
        results = results[:max_occurrences]

        # decide which document to render on the right panel
        if doc_id and doc_id != "all":
            document_doc_id = doc_id if doc_id in self.documents else None
        else:
            document_doc_id = results[0]["doc_id"] if results else None

        document_html = ""
        if document_doc_id is not None:
            text = self.documents[document_doc_id]
            spans = [
                (r["char_start"], r["char_end"])
                for r in results
                if r["doc_id"] == document_doc_id
            ]
            spans.sort()
            document_html = self._render_document_with_highlights(text, spans)

        return {
            "prefix": prefix,
            "selected_doc": selected_doc,
            "matched_words": matched_words,
            "results": results,
            "document_html": document_html,
            "document_doc_id": document_doc_id,
        }