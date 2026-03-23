# trie.py
from dataclasses import dataclass, field
from sys import prefix
from typing import Dict, List, Optional, Tuple

@dataclass
class TrieNode:
    children: Dict[str, "TrieNode"] = field(default_factory=dict)
    is_end: bool = False
    freq: int = 0   # frequency count for ranked autocomplete
    top: List[str] = field(default_factory=list)

class Trie:
    def __init__(self) -> None:
        self.root = TrieNode()
        self.K = 30  # default top-K size for each node, more to help with ranking later on

    def insert(self, word: str) -> None:
        if word == "":
            raise ValueError("empty string not allowed")
        node = self.root
        path_nodes = [node] # track nodes along the path
        for ch in word:
            # add child if missing
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
            path_nodes.append(node)
        node.is_end = True
        node.freq += 1

        # update top-K lists along the path
        for nd in path_nodes:
            self._update_top(nd, word)
        
    #insert with frequency n
    def insert_n(self, word: str, n: int) -> None:
        if word == "" or n <= 0:
            return
        node = self.root
        path_nodes = [node]
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
            path_nodes.append(node)

        node.is_end = True
        node.freq += n  

        for nd in path_nodes:
            self._update_top(nd, word)


    def search(self, word: str) -> bool:
        if word == "":
            return False
        node = self._walk(word)
        return node is not None and node.is_end

    def starts_with(self, prefix: str) -> bool:
        if prefix == "":
            return True  
        return self._walk(prefix) is not None

    def autocomplete(self, prefix: str, k: Optional[int] = None) -> List[str]:
        """
        Return up to k completions (lexicographic) for the given prefix.
        If k is None -> return all completions.
        """
        if prefix == "":
            return [] 

        start = self._walk(prefix)
        if start is None:
            return []

        results: List[str] = []
        self._dfs_collect(start, prefix, results, k)
        return results

    def autocomplete_ranked(self, prefix: str, k: int = 10) -> List[str]:
        """
        Frequency-based (Google-like) autocomplete.
        Ranking:
        1) higher freq first
        2) lexicographic tie-break
        """
        if prefix == "":
            return []

        start = self._walk(prefix)
        if start is None:
            return []

        pairs: List[Tuple[str, int]] = []
        self._dfs_collect_pairs(start, prefix, pairs)

        pairs.sort(key=lambda x: (-x[1], x[0]))
        return [w for w, _ in pairs[:k]]
    
    def autocomplete_cached(self, prefix: str) -> List[str]:
        """
        Return cached top-10 suggestions for this prefix.
        """
        if prefix == "":
            return []

        node = self._walk(prefix)
        if node is None:
            return []

        return node.top[:]   # copy
    
    # ---------- helpers ----------
    # return TrieNode at end of path if exists, else None
    def _walk(self, s: str) -> Optional[TrieNode]:
        node = self.root
        for ch in s:
            if ch not in node.children:
                return None
            node = node.children[ch]
        return node

    def _dfs_collect(
        self,
        node: TrieNode,
        path: str,
        out: List[str],
        k: Optional[int],
    ) -> None:
        if node.is_end:
            out.append(path)
            if k is not None and len(out) >= k:
                return

        # lexicographic order (important for predictable output)
        for ch in sorted(node.children.keys()):
            if k is not None and len(out) >= k:
                return
            self._dfs_collect(node.children[ch], path + ch, out, k)

    def _dfs_collect_pairs(
        self,
        node: TrieNode,
        path: str,
        out: List[Tuple[str, int]],
    ) -> None:
        if node.is_end:
            out.append((path, node.freq))

        for ch in node.children:
            self._dfs_collect_pairs(node.children[ch], path + ch, out)
    
    def _update_top(self, node: TrieNode, word: str) -> None:
        # ensure the word is present
        if word not in node.top:
            node.top.append(word)

        # sort by (-freq, word) using the word's terminal node freq
        node.top.sort(key=lambda w: (-self._get_freq(w), w))

        # trim to K
        if len(node.top) > self.K:
            node.top = node.top[:self.K]
    
    def _get_freq(self, word: str) -> int:
        n = self._walk(word)
        return 0 if n is None else n.freq
    
    def prefix_search(self, prefix: str) -> List[str]:
        return self.autocomplete(prefix, k=None)





