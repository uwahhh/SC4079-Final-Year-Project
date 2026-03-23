# engine.py
import re
from typing import List, Optional
from trie import Trie
from collections import deque, defaultdict
from typing import Dict

class AutocompleteEngine:
    def __init__(self, trie=None) -> None:
        self.trie = trie if trie is not None else Trie()
        # --- popularity + trending (no timestamps) ---
        self.freq: Dict[str, int] = defaultdict(int)          # all-time
        self.recent: Dict[str, int] = defaultdict(int)        # within window
        self.recent_q = deque()                               # holds last N queries

        self.RECENT_N = 10000   # start with 5k~20k
        self.BETA = 5           # start with 3~10



    # -------- public API --------
    def add_query(self, text: str) -> None:
        q = self.normalize(text)
        if q:  # ignore empty after normalization
            self.trie.insert(q)
            # update scores
            self.freq[q] += 1
            self.recent[q] += 1
            self.recent_q.append(q)

            if len(self.recent_q) > self.RECENT_N:
                old = self.recent_q.popleft()
                self.recent[old] -= 1
                if self.recent[old] <= 0:
                    del self.recent[old]

    def add_query_n(self, text: str, n: int) -> None:
        q = self.normalize(text)
        if not q or n <= 0:
            return

        # update trie frequency properly
        if hasattr(self.trie, "insert_n"):
            self.trie.insert_n(q, n)
        else:
            for _ in range(n):
                self.trie.insert(q)

        # update engine popularity
        self.freq[q] += n

        # update recency window (only last RECENT_N matters)
        m = min(n, self.RECENT_N)
        for _ in range(m):
            self.recent[q] += 1
            self.recent_q.append(q)

            if len(self.recent_q) > self.RECENT_N:
                old = self.recent_q.popleft()
                self.recent[old] -= 1
                if self.recent[old] <= 0:
                    del self.recent[old]



    def suggest(self, prefix: str, k: int = 10, mode: str = "cached") -> List[str]:
        p = self.normalize(prefix)

        if not p:
            return []

        if mode == "cached":
            items = self.trie.autocomplete_cached(p)

            def score(w: str) -> int:
                return self.freq.get(w, 0) + self.BETA * self.recent.get(w, 0)

            items.sort(key=lambda w: (-score(w), w))
            return items[:k]

        elif mode == "ranked":
            items = self.trie.autocomplete_ranked(p, k)

            def score(w: str) -> int:
                return self.freq.get(w, 0) + self.BETA * self.recent.get(w, 0)

            items.sort(key=lambda w: (-score(w), w))
            return items[:k]

        elif mode == "baseline":
            return self.trie.autocomplete(p, k)

        else:
            raise ValueError("mode must be one of: cached, ranked, baseline")


    # -------- normalization --------
    def normalize(self, text: str) -> str:
        """
        Simple normalization (keep it explainable in report):
        - strip ends
        - lowercase
        - collapse whitespace
        - remove punctuation except spaces
        """
        if text is None:
            return ""

        s = text.strip().lower()
        if not s:
            return ""

        # replace punctuation with space (keeps word boundaries)
        # keeps letters/digits/underscore; converts everything else to space
        s = re.sub(r"[^\w\s]", " ", s)

        # collapse multiple spaces
        s = re.sub(r"\s+", " ", s).strip()

        return s
