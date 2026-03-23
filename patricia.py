# patricia.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Edge = Tuple[str, "PatriciaNode"]  # (label, child)


def lcp(a: str, b: str) -> int:
    i = 0
    m = min(len(a), len(b))
    while i < m and a[i] == b[i]:
        i += 1
    return i


@dataclass
class PatriciaNode:
    children: Dict[str, Edge] = field(default_factory=dict)  # key = first char of edge label
    is_end: bool = False
    freq: int = 0
    top: List[str] = field(default_factory=list)  # cached top-K words


class PatriciaTrie:
    def __init__(self) -> None:
        self.root = PatriciaNode()
        self.K = 30
        self.word_freq: Dict[str, int] = {}  # global freq cache

    def insert(self, word: str) -> None:
        if word == "":
            raise ValueError("empty string not allowed")

        # update global frequency first
        self.word_freq[word] = self.word_freq.get(word, 0) + 1

        node = self.root
        path_nodes = [node]  # nodes along the insertion path (node boundaries)

        rest = word
        while True:
            first = rest[0]
            if first not in node.children:
                # Case A: no matching edge -> add leaf edge
                leaf = PatriciaNode(is_end=True, freq=self.word_freq[word])
                node.children[first] = (rest, leaf)
                path_nodes.append(leaf)
                break

            label, child = node.children[first]
            k = lcp(rest, label)

            if k == len(label):
                # Case B: full label match -> move down
                node = child
                path_nodes.append(node)
                rest = rest[k:]
                if rest == "":
                    # word ends exactly at this node boundary
                    node.is_end = True
                    node.freq = self.word_freq[word]
                    break
                continue

            if k == len(rest):
                # Case C: rest ends inside label -> split edge; mid becomes terminal
                # node --label--> child  becomes:
                # node --rest--> mid --label[k:]--> child
                mid = PatriciaNode(is_end=True, freq=self.word_freq[word])

                # old remainder edge
                rem_label = label[k:]
                mid.children[rem_label[0]] = (rem_label, child)

                # inherit cached suggestions from old subtree
                mid.top = child.top[:]

                # replace edge from node to mid
                node.children[first] = (label[:k], mid)

                path_nodes.append(mid)
                break

            # Case D: mismatch in middle -> split into 2 children
            # node --label--> child  becomes:
            # node --common--> mid
            # mid --label[k:]--> child
            # mid --rest[k:]--> new_leaf
            common = label[:k]
            mid = PatriciaNode()

            old_rem = label[k:]
            mid.children[old_rem[0]] = (old_rem, child)

            new_rem = rest[k:]
            new_leaf = PatriciaNode(is_end=True, freq=self.word_freq[word])
            mid.children[new_rem[0]] = (new_rem, new_leaf)

            # inherit cached suggestions from old subtree
            mid.top = child.top[:]
            node.children[first] = (common, mid)

            path_nodes.append(mid)
            path_nodes.append(new_leaf)
            break

        # update cached top-K on all nodes touched
        for nd in path_nodes:
            self._update_top(nd, word)

    def search(self, word: str) -> bool:
        if word == "":
            return False

        node, _, ok, ended_at_boundary = self._locate(word)
        if not ok:
            return False

        # if the word ends in the middle of an edge, it cannot be a stored key in this Patricia representation
        if not ended_at_boundary:
            return False

        return node.is_end

    def autocomplete(self, prefix: str, k: Optional[int] = None) -> List[str]:
        if prefix == "":
            return []

        node, path_to_node, ok, _ = self._locate(prefix)
        if not ok:
            return []

        out: List[str] = []
        self._dfs_collect(node, path_to_node, out, k)
        return out

    def autocomplete_ranked(self, prefix: str, k: int = 10) -> List[str]:
        if prefix == "":
            return []

        node, path_to_node, ok, _ = self._locate(prefix)
        if not ok:
            return []

        pairs: List[Tuple[str, int]] = []
        self._dfs_collect_pairs(node, path_to_node, pairs)
        pairs.sort(key=lambda x: (-x[1], x[0]))
        return [w for w, _ in pairs[:k]]

    def autocomplete_cached(self, prefix: str) -> List[str]:
        """
        Returns cached top-10 suggestions for the prefix.
        Works even if prefix ends mid-edge: we return the child-node's cached top list.
        """
        if prefix == "":
            return []

        node, _, ok, _ = self._locate(prefix)
        if not ok:
            return []

        return node.top[:]

    # ---------- helpers ----------
    def _update_top(self, node: PatriciaNode, word: str) -> None:
        if word not in node.top:
            node.top.append(word)

        node.top.sort(key=lambda w: (-self.word_freq.get(w, 0), w))

        if len(node.top) > self.K:
            node.top = node.top[: self.K]

    def _locate(self, s: str) -> Tuple[PatriciaNode, str, bool, bool]:
        """
        Locate s as a prefix in the tree.

        Returns:
          (subtree_node, path_to_subtree_node, ok, ended_at_node_boundary)

        - ok=False if s doesn't match any path.
        - ended_at_node_boundary=True if s ends exactly on a node boundary.
          False if s ends in the middle of an edge label.
        """
        node = self.root
        path = ""

        rest = s
        while rest:
            first = rest[0]
            if first not in node.children:
                return self.root, "", False, False

            label, child = node.children[first]
            k = lcp(rest, label)

            if k == 0:
                return self.root, "", False, False

            if k == len(rest):
                # s ends here (maybe mid-edge)
                path += label  # go to the child boundary (full label)
                ended_at_boundary = (k == len(label))
                return child, path, True, ended_at_boundary

            if k == len(label):
                # consume label and continue
                path += label
                node = child
                rest = rest[k:]
                continue

            # mismatch in the middle
            return self.root, "", False, False

        # s was empty => boundary at current node
        return node, path, True, True

    def _dfs_collect(self, node: PatriciaNode, path: str, out: List[str], k: Optional[int]) -> None:
        if node.is_end:
            out.append(path)
            if k is not None and len(out) >= k:
                return

        # deterministic ordering for baseline
        for first_ch in sorted(node.children.keys()):
            if k is not None and len(out) >= k:
                return
            label, child = node.children[first_ch]
            self._dfs_collect(child, path + label, out, k)

    def _dfs_collect_pairs(self, node: PatriciaNode, path: str, out: List[Tuple[str, int]]) -> None:
        if node.is_end:
            out.append((path, node.freq))

        for first_ch in node.children:
            label, child = node.children[first_ch]
            self._dfs_collect_pairs(child, path + label, out)
