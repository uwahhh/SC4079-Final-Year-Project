from collections import Counter
import csv

INPUT_FILE = "queries_generated.txt"
OUTPUT_FILE = "events_rle.csv"

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        queries = [line.strip() for line in f if line.strip()]

    counts = Counter(queries)

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["query", "count"])
        for query, count in counts.items():
            writer.writerow([query, count])

    print(f"Read {len(queries)} total queries")
    print(f"Wrote {len(counts)} unique queries to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()