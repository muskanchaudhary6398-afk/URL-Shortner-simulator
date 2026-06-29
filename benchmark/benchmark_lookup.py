"""
benchmark/benchmark_lookup.py

Empirically demonstrates the "O(1) average lookup and insertion time" claim:
times batches of inserts and lookups at increasing scale (1k, 5k, 10k, 50k,
100k links) and reports average time per operation at each scale. For a
real hash-map-backed implementation, average per-operation time should stay
roughly flat as N grows (occasional resize/rehash amortizes out) -- NOT grow
linearly or logarithmically with N. That flatness is the empirical signature
of O(1) average-case behavior we're checking for here.

Usage:
    python benchmark/benchmark_lookup.py
"""

import random
import string
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.shortener import URLShortener
from storage.persistence import InMemoryStore


def random_url(i: int) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"https://example.com/article/{i}/{suffix}"


def benchmark_scale(n: int) -> dict:
    shortener = URLShortener(store=InMemoryStore())
    urls = [random_url(i) for i in range(n)]

    # --- insertion timing ---
    start = time.perf_counter()
    codes = [shortener.shorten(u) for u in urls]
    insert_elapsed = time.perf_counter() - start

    # --- lookup timing (random access pattern, not sequential) ---
    shuffled_codes = codes[:]
    random.shuffle(shuffled_codes)
    start = time.perf_counter()
    for code in shuffled_codes:
        shortener.resolve(code)
    lookup_elapsed = time.perf_counter() - start

    shortener.close()
    return {
        "n": n,
        "insert_total_ms": round(insert_elapsed * 1000, 2),
        "insert_avg_us": round(insert_elapsed / n * 1_000_000, 3),
        "lookup_total_ms": round(lookup_elapsed * 1000, 2),
        "lookup_avg_us": round(lookup_elapsed / n * 1_000_000, 3),
        "unique_codes": len(set(codes)) == n,
    }


def main():
    scales = [1_000, 5_000, 10_000, 50_000, 100_000]
    print(f"{'N':>8} | {'insert avg (us)':>16} | {'lookup avg (us)':>16} | {'all codes unique':>17}")
    print("-" * 70)
    results = []
    for n in scales:
        r = benchmark_scale(n)
        results.append(r)
        print(f"{r['n']:>8} | {r['insert_avg_us']:>16} | {r['lookup_avg_us']:>16} | {str(r['unique_codes']):>17}")

    print("\nIf per-operation average time stays roughly flat as N grows "
          "(rather than climbing proportionally with N), that's the "
          "empirical signature of O(1) average-case hash-map behavior.")
    return results


if __name__ == "__main__":
    main()
