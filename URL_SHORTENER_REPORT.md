# Project Report: URL Shortener Simulator

**Self Project**
**Duration:** November 2025 – December 2025

---

## 1. Abstract

This project implements a URL shortening system end-to-end: generating short, unique identifiers for long URLs and resolving them back in constant average time, while handling the practical problems a real shortening service has to solve — hash collisions, duplicate submissions of the same URL, surviving a process restart, and basic click analytics. The system uses SHA-256-derived fingerprints encoded in Base62 as short codes, two in-memory hash maps for O(1) average-case creation, lookup, and duplicate detection, a SQLite-backed persistence layer for durability across sessions, and a lightweight analytics layer for usage tracking. A benchmark across dataset sizes from 1,000 to 100,000 links empirically confirms that average insert and lookup time stays flat rather than growing with scale.

## 2. Problem Statement

Services like bit.ly or tinyurl.com need to: (1) take an arbitrarily long URL and produce a short, unique identifier for it; (2) reliably map that identifier back to the original URL, fast, regardless of how many links the system has stored; (3) avoid generating two different codes for the same URL when a user submits it twice; (4) not lose data when the process restarts; and (5) provide basic visibility into how a link is being used. This project builds a self-contained simulator of that system, with an emphasis on the underlying data-structure design (hash-based indexing, collision handling) rather than on production-grade infrastructure (no external database server, load balancer, or distributed cache — by design, to keep the system inspectable and the algorithmic core front-and-center).

## 3. System Architecture

```
long URL
   │
   ▼
core/hashing.py        -- SHA-256 fingerprint(url, attempt) -> int
   │
   ▼
core/base62.py          -- int -> short code (62-symbol alphabet)
   │
   ▼
core/shortener.py        -- in-memory hash maps:
   │                         code_to_url : short_code -> long_url   (lookup)
   │                         url_to_code : long_url   -> short_code (dup detection)
   │                       collision handling + fallback counter
   │
   ├──▶ storage/persistence.py   -- SQLite (durable) or in-memory (tests)
   │
   ├──▶ analytics/tracker.py     -- per-link stats, leaderboard, summary
   │
   ├──▶ api/app.py (Flask)       -- HTTP interface
   └──▶ cli.py                  -- terminal interface
```

The in-memory hash maps in `core/shortener.py` are the hot path and the source of the O(1) average-case guarantee; the SQLite layer underneath is purely for durability and is not on the critical path for a lookup that's already been loaded into memory.

## 4. Methodology

### 4.1 Base62 encoding

Short codes use a 62-character alphabet (`0-9`, `A-Z`, `a-z`). Base62 was chosen over Base64 specifically because Base64's extra two symbols (`+` and `/`) are not URL-safe without escaping, while Base62 needs no escaping at all when used directly in a URL path segment (`core/base62.py`).

### 4.2 Hash-based indexing and collision handling

Rather than a purely sequential counter (which would make short codes predictable and trivially enumerable), each short code is seeded by hashing the long URL itself with SHA-256 and Base62-encoding the first 6 bytes (48 bits) of the digest (`core/hashing.py`). This keeps code generation deterministic and content-derived, while still requiring an explicit collision-resolution strategy, since two different URLs can in principle hash to the same 48-bit fingerprint.

Collision handling works as follows (`core/shortener.py`):

1. Compute `fingerprint(url, attempt=0)`, Base62-encode it as the candidate code.
2. If the candidate is unused, assign it.
3. If the candidate already maps to the *same* URL, this is a duplicate submission — return the existing code without creating a new entry.
4. If the candidate already maps to a *different* URL, this is a genuine collision — retry with `fingerprint(url, attempt=1)`, then `attempt=2`, and so on, up to 5 attempts.
5. If all 5 attempts collide, fall back to a monotonically increasing internal counter (prefixed with `Z` to keep its namespace disjoint from hash-derived codes), which is unique by construction and guarantees the system never fails to produce a code.

*Collision probability estimate:* with a 48-bit fingerprint space (~2.81×10¹⁴ possible values), the birthday-bound estimate puts a 50% chance of at least one collision only after roughly √(2 × 2.81×10¹⁴ × ln 2) ≈ 19.7 million stored links — i.e., the 5-retry hash-based path is expected to resolve essentially every collision in practice at the "thousands of links" scale described in the project goals, with the counter fallback existing purely as a structural safety net rather than something expected to trigger in normal operation.

### 4.3 Duplicate detection

A second hash map, `url_to_code`, is the reverse index of `code_to_url`. Before any hashing or collision logic runs, `shorten()` checks this reverse index first: if the URL has already been shortened, the existing code is returned immediately in O(1), with no redundant database row created. This is verified directly in `tests/test_shortener.py::test_duplicate_url_returns_same_code`.

### 4.4 Persistence and session recovery

`storage/persistence.py` defines two interchangeable backends behind the same interface: `SQLiteStore` (a single-file database, schema in the module docstring) and `InMemoryStore` (a no-disk dict, used for fast unit tests). On startup, `URLShortener.__init__` calls `load_all()` on whichever store it's given and rehydrates both in-memory hash maps from the persisted rows — this is what allows a brand-new process to recover every previously-created link. `tests/test_persistence.py` verifies this directly: it creates links with one `URLShortener` instance, closes it, opens a second instance against the same database file, and confirms both link resolution and click counts carried over correctly.

### 4.5 Analytics

Each click against a short code increments a `click_count` column and updates `last_accessed` in the persistence layer (recorded automatically inside `URLShortener.resolve()`, so analytics tracking can't be bypassed by going through a different code path). `analytics/tracker.py` exposes this as per-link stats, a most-clicked leaderboard, and an overall summary (total URLs, total clicks, average clicks per URL).

## 5. Experimental Setup

- **Hash function:** SHA-256, truncated to the first 6 bytes (48 bits) of the digest
- **Code alphabet:** Base62, codes padded to a minimum of 6 characters
- **Collision retry budget:** 5 hash-based attempts before falling back to a counter
- **Persistence:** SQLite, single file, no external database server
- **Benchmark methodology:** for each scale N ∈ {1,000; 5,000; 10,000; 50,000; 100,000}, insert N freshly-generated random URLs, time the batch, then shuffle the resulting codes and time N random-order lookups — shuffling avoids any artificial advantage from sequential/cache-friendly access patterns

## 6. Results

| N (links) | Insert avg (µs) | Lookup avg (µs) | All codes unique |
|---|---|---|---|
| 1,000 | 6.74 | 0.61 | Yes |
| 5,000 | 3.88 | 0.45 | Yes |
| 10,000 | 3.87 | 0.50 | Yes |
| 50,000 | 4.49 | 0.91 | Yes |
| 100,000 | 5.55 | 0.90 | Yes |

Across a 100x increase in the number of stored links, both average insertion time and average lookup time stay within roughly a 2x band in the low-single-digit-microsecond range, rather than scaling proportionally (or worse) with N. This is the expected empirical signature of an O(1) average-case hash table: the underlying Python `dict` occasionally resizes/rehashes internally, but that cost amortizes to a constant per operation over many insertions, which is exactly what the flat timing curve shows. All 100,000 generated codes were also confirmed unique at every scale tested, validating that the hash-based generation + collision-retry scheme does not produce duplicate codes for distinct URLs even at scale.

Separately, the full test suite (24 tests) validates correctness of the underlying logic that the benchmark's timing numbers depend on: Base62 round-trip correctness, duplicate-URL detection returning the same code, a *forced* collision scenario (via monkeypatching the hash function so two different URLs deliberately collide) resolving to two distinct, independently-correct codes, the counter-fallback path triggering correctly when collisions are forced to exhaust all retry attempts, and cross-session persistence of both link data and click counts.

## 7. Discussion and Limitations

- **In-memory hash maps, not a distributed cache:** this is a single-process simulator. A production system handling real traffic at scale would need the equivalent of `code_to_url`/`url_to_code` to live in a shared cache (e.g. Redis) rather than per-process Python dicts, with the SQLite layer replaced by a proper database with replication.
- **48-bit fingerprint space:** chosen as a practical balance between short code length and collision probability at the "thousands of links" scale described in the project goals; a service expecting tens of millions of links would want a larger fingerprint (or an explicitly counter-based scheme) to keep collision retries rare at that scale.
- **SQLite concurrency:** SQLite serializes writes at the file level; the `check_same_thread=False` flag used for Flask compatibility is appropriate for this demo's request volume but is not a substitute for connection pooling under real concurrent load.
- **No custom aliases or expiration:** the system always derives codes from the URL's hash; it doesn't yet support user-chosen vanity codes or link expiration, both natural extensions.

## 8. Conclusion and Future Work

This project demonstrates a complete, tested implementation of the core data-structure problem behind URL shortening — deterministic hash-based code generation with explicit, verifiable collision handling, O(1) average-case duplicate detection via a reverse index, and durable cross-session storage — backed by an empirical benchmark confirming the claimed O(1) average behavior rather than asserting it. Natural extensions include: custom/vanity short codes, link expiration and TTLs, rate limiting on the API, and swapping the single-file SQLite store for a networked database to support multi-process/multi-host deployment.

## 9. References

- Base62 encoding: general-purpose URL-safe identifier encoding scheme (no single canonical spec; widely used by short-link services)
- SHA-256: NIST FIPS 180-4, Secure Hash Standard
- Python `sqlite3` module documentation: https://docs.python.org/3/library/sqlite3.html
- Flask documentation: https://flask.palletsprojects.com/
