# run_testcases.py
import time, random, gc, csv, tracemalloc, statistics, math
from pathlib import Path

from trie import Trie
from patricia import PatriciaTrie
from engine import AutocompleteEngine

# reuse the same generators
import string

def random_word(min_len=3, max_len=12) -> str:
    L = random.randint(min_len, max_len)
    return "".join(random.choice(string.ascii_lowercase) for _ in range(L))

def make_vocab(vocab_size: int, min_len=3, max_len=12):
    vocab = set()
    while len(vocab) < vocab_size:
        vocab.add(random_word(min_len, max_len))
    return list(vocab)

def make_query_log(vocab, total_queries: int, skew: float = 1.2):
    n = len(vocab)
    ranks = list(range(1, n + 1))
    weights = [1.0 / (r ** skew) for r in ranks]
    s = sum(weights)
    weights = [w / s for w in weights]
    vocab_sorted = sorted(vocab)
    return random.choices(vocab_sorted, weights=weights, k=total_queries)

def make_prefixes(words, num_prefixes: int, min_p=1, max_p=4):
    prefixes = []
    for _ in range(num_prefixes):
        w = random.choice(words)
        p_len = random.randint(min_p, min(max_p, len(w)))
        prefixes.append(w[:p_len])
    return prefixes

def count_nodes_edges(root):
    nodes = 0
    edges = 0
    stack = [root]
    while stack:
        node = stack.pop()
        nodes += 1
        for val in node.children.values():
            edges += 1
            child = val[1] if isinstance(val, tuple) else val
            stack.append(child)
    return nodes, edges

def count_top_entries(root):
    total = 0
    stack = [root]
    while stack:
        node = stack.pop()
        if hasattr(node, "top"):
            total += len(getattr(node, "top"))
        for val in node.children.values():
            child = val[1] if isinstance(val, tuple) else val
            stack.append(child)
    return total

def build_engine(ds, query_log):
    e = AutocompleteEngine(ds)
    t0 = time.perf_counter()
    for q in query_log:
        e.add_query(q)
    t1 = time.perf_counter()
    return e, (t1 - t0)

def warmup(engine, prefixes, k, mode, n=200):
    for p in prefixes[: min(n, len(prefixes))]:
        engine.suggest(p, k=k, mode=mode)

def one_sample_us(engine, prefixes, k, mode):
    # measure avg microseconds per suggest for ONE pass over prefixes
    t0 = time.perf_counter_ns()
    for p in prefixes:
        engine.suggest(p, k=k, mode=mode)
    t1 = time.perf_counter_ns()
    avg_ns = (t1 - t0) / max(1, len(prefixes))
    return avg_ns / 1000.0

def ci95(mean, sd, n):
    # CLT-based 95% CI
    if n <= 1:
        return (mean, mean)
    se = sd / math.sqrt(n)
    z = 1.96
    return (mean - z * se, mean + z * se)

def main():
    # ---------- knobs ----------
    random.seed(42)

    VOCAB_SIZE    = 50_000
    TOTAL_QUERIES = 200_000
    NUM_PREFIXES  = 10_000
    SKEW          = 1.2

    K_VALUES = [1, 5, 10, 20]                 # 4 k values
    MODES    = ["baseline", "ranked", "cached"]  # 3 modes

    # 3 word-length buckets, edit if needed
    BUCKETS = {
        "short": (3, 5),     # len 3-5
        "mid":   (6, 8),     # len 6-8
        "long":  (9, 12),    # len 9-12
    }

    SAMPLES = 30             # CLT repeats per test case
    WARMUP_N = 200

    OUT = Path("results_testcases.csv")

    print("Generating synthetic data...")
    vocab = make_vocab(VOCAB_SIZE, 3, 12)
    query_log = make_query_log(vocab, TOTAL_QUERIES, skew=SKEW)

    # pre-split vocab into buckets, then generate prefixes per bucket
    bucket_prefixes = {}
    for bname, (lo, hi) in BUCKETS.items():
        words = [w for w in vocab if lo <= len(w) <= hi]
        if not words:
            raise RuntimeError(f"Bucket {bname} has no words. Adjust BUCKETS.")
        bucket_prefixes[bname] = make_prefixes(words, NUM_PREFIXES)

    # CSV header
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "ds", "mode", "k", "bucket",
            "samples", "mean_us", "sd_us", "ci95_low_us", "ci95_high_us",
            "build_time_s", "mem_peak_mb", "nodes", "edges", "top_entries_total",
            "engine_freq_keys", "recent_window", "recent_keys",
        ])

    for ds_name, ds in [("Trie", Trie()), ("Patricia", PatriciaTrie())]:
        print(f"\n===== {ds_name} =====")
        gc.collect()
        tracemalloc.start()
        engine, build_s = build_engine(ds, query_log)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        nodes, edges = count_nodes_edges(engine.trie.root)
        top_entries = count_top_entries(engine.trie.root)

        meta = {
            "build_time_s": build_s,
            "mem_peak_mb": peak / 1024 / 1024,
            "nodes": nodes,
            "edges": edges,
            "top_entries_total": top_entries,
            "engine_freq_keys": len(engine.freq),
            "recent_window": len(engine.recent_q),
            "recent_keys": len(engine.recent),
        }

        print(f"Build: {build_s:.3f}s | peak_mem={meta['mem_peak_mb']:.2f}MB | nodes={nodes:,}")

        for mode in MODES:
            for k in K_VALUES:
                for bucket_name, prefixes in bucket_prefixes.items():
                    warmup(engine, prefixes, k=k, mode=mode, n=WARMUP_N)

                    samples = [one_sample_us(engine, prefixes, k=k, mode=mode) for _ in range(SAMPLES)]
                    mean = statistics.mean(samples)
                    sd = statistics.stdev(samples) if len(samples) > 1 else 0.0
                    lo, hi = ci95(mean, sd, len(samples))

                    print(f"{ds_name:8s} {mode:8s} k={k:<2d} bucket={bucket_name:5s} "
                          f"mean={mean:,.2f}us sd={sd:,.2f} 95%CI=[{lo:,.2f},{hi:,.2f}]")

                    with OUT.open("a", newline="", encoding="utf-8") as f:
                        w = csv.writer(f)
                        w.writerow([
                            ds_name, mode, k, bucket_name,
                            SAMPLES, f"{mean:.6f}", f"{sd:.6f}", f"{lo:.6f}", f"{hi:.6f}",
                            f"{meta['build_time_s']:.6f}", f"{meta['mem_peak_mb']:.6f}",
                            meta["nodes"], meta["edges"], meta["top_entries_total"],
                            meta["engine_freq_keys"], meta["recent_window"], meta["recent_keys"],
                        ])

    print(f"\nDone. Wrote: {OUT.resolve()}")
    

if __name__ == "__main__":
    main()
