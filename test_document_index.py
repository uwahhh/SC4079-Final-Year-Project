from trie import Trie
from document_index import DocumentIndex

trie = Trie()
doc_index = DocumentIndex(trie)

text1 = """
Prefix matching is useful for autocomplete systems.
A trie can quickly find words like prefix, prepare, and prevent.
"""

text2 = """
Patricia tries compress paths.
Prefix search can also be used over uploaded documents.
"""

doc_index.add_document("doc1", text1)
doc_index.add_document("doc2", text2)

result = doc_index.search_prefix("pre")

print("Matched words:")
print(result["matched_words"])
print()

print("Results:")
for row in result["results"]:
    print(row["doc_id"], row["word"], row["char_start"], row["snippet"])