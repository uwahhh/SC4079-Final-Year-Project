from trie import Trie
from engine import AutocompleteEngine
from patricia import PatriciaTrie

def run_case(title, got, expected):
    status = "PASS" if got == expected else "FAIL"
    print(f"{status} | {title}\n  got:      {got}\n  expected: {expected}\n")
    assert got == expected


def build_trie(words):
    t = Trie()
    for w in words:
        t.insert(w)
    return t

def build_patricia(words):
    t = PatriciaTrie()
    for w in words:
        t.insert(w)
    return t


# --------------------------------------------------
# TRIE TESTS
# --------------------------------------------------

def test_trie_search():
    t = build_trie(["car", "cart", "cat", "dog"])

    run_case("search finds inserted word", t.search("car"), True)

    # edge cases for search
    run_case("search rejects prefix that is not a full word", t.search("ca"), False)
    run_case("search rejects missing word", t.search("cow"), False)
    run_case("search on empty trie returns False", Trie().search("a"), False)
    run_case("search empty string returns False", t.search(""), False)


def test_trie_prefix_check():
    t = build_trie(["car", "cart", "cat", "dog"])

    run_case("starts_with finds valid prefix", t.starts_with("ca"), True)

    # edge cases for prefix checking
    run_case("starts_with rejects missing prefix", t.starts_with("z"), False)
    run_case("starts_with empty string returns True", t.starts_with(""), True)


def test_trie_autocomplete_baseline():
    t = build_trie(["car", "cart", "cat", "dog"])

    run_case(
        "autocomplete returns all completions in lexicographic order",
        t.autocomplete("ca"),
        ["car", "cart", "cat"]
    )
    run_case(
        "autocomplete works when prefix is a full word",
        t.autocomplete("car"),
        ["car", "cart"]
    )

    # edge cases for autocomplete
    run_case("autocomplete missing prefix returns empty list", t.autocomplete("z"), [])
    run_case("autocomplete empty string returns empty list", t.autocomplete(""), [])



def test_trie_autocomplete_limit():
    t = build_trie(["car", "cart", "cat", "dog"])

    run_case("autocomplete k=2 limits output", t.autocomplete("ca", k=2), ["car", "cart"])


def test_trie_prefix_as_word():
    t = build_trie(["a", "an", "and", "ant"])

    run_case("search finds stored prefix-word", t.search("an"), True)
    run_case("autocomplete includes prefix-word itself", t.autocomplete("a"), ["a", "an", "and", "ant"])



def test_trie_ranking_and_cache():
    t = Trie()
    for _ in range(5):
        t.insert("car")
    for _ in range(2):
        t.insert("cat")
    t.insert("cart")

    run_case(
        "baseline autocomplete remains lexicographic",
        t.autocomplete("ca"),
        ["car", "cart", "cat"]
    )
    run_case(
        "ranked autocomplete orders by frequency",
        t.autocomplete_ranked("ca", 3),
        ["car", "cat", "cart"]
    )
    run_case(
        "cached autocomplete returns top suggestions",
        t.autocomplete_cached("ca")[:3],
        ["car", "cat", "cart"]
    )

    # edge case: duplicates should not duplicate words in output
    run_case(
        "duplicate inserts do not duplicate autocomplete results",
        t.autocomplete("ca"),
        ["car", "cart", "cat"]
    )


def test_trie_invalid_insert():
    t = Trie()
    try:
        t.insert("")
        assert False, "Expected ValueError for empty string insert"
    except ValueError:
        print("PASS | insert empty string raises ValueError\n")


# --------------------------------------------------
# ENGINE TESTS
# --------------------------------------------------

def test_engine_normalize():
    e = AutocompleteEngine()

    run_case("normalize lowercases", e.normalize("Car"), "car")
    run_case("normalize removes punctuation", e.normalize("car!!!"), "car")
    run_case("normalize trims spaces", e.normalize("  car  "), "car")
    run_case("normalize empty spaces to empty string", e.normalize("   "), "")
    run_case("normalize None to empty string", e.normalize(None), "")


def test_engine_add_query_and_baseline_suggest():
    e = AutocompleteEngine()
    for q in ["Car", "car!!!", "car ", "cat", "cat!", "cart"]:
        e.add_query(q)

    run_case(
        "baseline suggest returns expected results",
        e.suggest("ca", mode="baseline"),
        ["car", "cart", "cat"]
    )

    # edge case
    run_case(
        "suggest with empty normalized prefix returns empty list",
        e.suggest("   ", mode="baseline"),
        []
    )


def test_engine_ranked_and_cached_suggest():
    e = AutocompleteEngine()
    for q in ["Car", "car!!!", "car ", "cat", "cat!", "cart"]:
        e.add_query(q)

    run_case(
        "ranked suggest orders by frequency/trending score",
        e.suggest("ca", mode="ranked"),
        ["car", "cat", "cart"]
    )
    run_case(
        "cached suggest orders by frequency/trending score",
        e.suggest("ca", mode="cached"),
        ["car", "cat", "cart"]
    )


def test_engine_add_query_n():
    e = AutocompleteEngine()
    e.add_query_n("car", 5)
    e.add_query_n("cat", 2)
    e.add_query_n("cart", 1)

    run_case(
        "add_query_n affects ranked suggest",
        e.suggest("ca", mode="ranked"),
        ["car", "cat", "cart"]
    )

    # edge cases
    e.add_query_n("   ", 10)
    e.add_query_n("dog", 0)
    run_case(
        "invalid add_query_n inputs do not affect results",
        e.suggest("d", mode="ranked"),
        []
    )


def test_engine_invalid_mode():
    e = AutocompleteEngine()
    e.add_query("car")

    try:
        e.suggest("ca", mode="wrong")
        assert False, "Expected ValueError for invalid mode"
    except ValueError:
        print("PASS | invalid mode raises ValueError\n")

# --------------------------------------------------
# PATRICIA TRIE TESTS
# --------------------------------------------------

def test_patricia_search():
    t = build_patricia(["car", "cart", "cat", "dog"])

    run_case("patricia search finds inserted word", t.search("car"), True)
    run_case("patricia search rejects prefix that is not full word", t.search("ca"), False)
    run_case("patricia search rejects missing word", t.search("cow"), False)
    run_case("patricia search empty string returns False", t.search(""), False)

def test_patricia_edge_split_shorter_word():
    t = PatriciaTrie()
    t.insert("cart")
    t.insert("car")

    run_case("patricia shorter word inserted after longer word", t.search("car"), True)
    run_case("patricia longer word still exists after split", t.search("cart"), True)
    run_case("patricia autocomplete after shorter-word split", t.autocomplete("car"), ["car", "cart"])

def test_patricia_edge_split_mid_mismatch():
    t = PatriciaTrie()
    t.insert("cat")
    t.insert("car")

    run_case("patricia split stores first word", t.search("cat"), True)
    run_case("patricia split stores second word", t.search("car"), True)
    run_case("patricia autocomplete after mid-label split", t.autocomplete("ca"), ["car", "cat"])


def test_patricia_prefix_inside_edge():
    t = PatriciaTrie()
    t.insert("cart")

    run_case("patricia autocomplete works when prefix ends mid-edge", t.autocomplete("ca"), ["cart"])
    run_case("patricia cached autocomplete works when prefix ends mid-edge", t.autocomplete_cached("ca"), ["cart"])
    run_case("patricia search mid-edge prefix is not a full word", t.search("ca"), False)

def test_patricia_ranking_and_cache():
    t = PatriciaTrie()
    for _ in range(5):
        t.insert("car")
    for _ in range(2):
        t.insert("cat")
    t.insert("cart")

    run_case("patricia baseline autocomplete remains lexicographic", t.autocomplete("ca"), ["car", "cart", "cat"])
    run_case("patricia ranked autocomplete orders by frequency", t.autocomplete_ranked("ca", 3), ["car", "cat", "cart"])
    run_case("patricia cached autocomplete returns top suggestions", t.autocomplete_cached("ca")[:3], ["car", "cat", "cart"])

def test_patricia_invalid_insert():
    t = PatriciaTrie()
    try:
        t.insert("")
        assert False, "Expected ValueError for empty string insert"
    except ValueError:
        print("PASS | patricia insert empty string raises ValueError\n")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    # trie
    test_trie_search()
    test_trie_prefix_check()
    test_trie_autocomplete_baseline()
    test_trie_autocomplete_limit()
    test_trie_prefix_as_word()
    test_trie_ranking_and_cache()
    test_trie_invalid_insert()

    # engine
    test_engine_normalize()
    test_engine_add_query_and_baseline_suggest()
    test_engine_ranked_and_cached_suggest()
    test_engine_add_query_n()
    test_engine_invalid_mode()

    # patricia trie
    test_patricia_search()
    test_patricia_edge_split_shorter_word()
    test_patricia_edge_split_mid_mismatch()
    test_patricia_prefix_inside_edge()
    test_patricia_ranking_and_cache()
    test_patricia_invalid_insert()

    print("ALL TESTS PASSED!")


if __name__ == "__main__":
    main()