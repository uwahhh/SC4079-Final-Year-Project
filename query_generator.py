import random

INPUT_FILE = "queries.txt"
PHRASES_FILE = "phrases.txt"
OUTPUT_FILE = "queries_generated.txt"
NUM_GENERATED = 20000
RANDOM_SEED = 42   # optional, for reproducible output


def load_queries(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def generate_prefix_phrases(queries):
    phrases = []
    seen = set()

    for query in queries:
        words = query.split()
        for i in range(1, len(words) + 1):
            prefix = " ".join(words[:i])
            if prefix not in seen:
                seen.add(prefix)
                phrases.append(prefix)

    return phrases


def save_lines(filename, lines):
    with open(filename, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def generate_synthetic_queries(phrases, n):
    return [random.choice(phrases) for _ in range(n)]


def main():
    random.seed(RANDOM_SEED)

    queries = load_queries(INPUT_FILE)

    # Step 1: generate all unique prefix phrases
    phrases = generate_prefix_phrases(queries)
    save_lines(PHRASES_FILE, phrases)

    # Step 2: sample synthetic query stream from the prefix pool
    generated_queries = generate_synthetic_queries(phrases, NUM_GENERATED)
    save_lines(OUTPUT_FILE, generated_queries)

    print(f"Loaded {len(queries)} base queries from {INPUT_FILE}")
    print(f"Generated {len(phrases)} unique prefixes into {PHRASES_FILE}")
    print(f"Generated {len(generated_queries)} synthetic queries into {OUTPUT_FILE}")


if __name__ == "__main__":
    main()