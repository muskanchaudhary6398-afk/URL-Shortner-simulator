# URL Shortener Simulator

> Self Project — Nov 2025 to Dec 2025

A from-scratch URL shortening system: generates compact, unique short links and resolves them back to the original URL using hash-based indexing, with collision handling, duplicate detection, persistent storage, and basic usage analytics.

```
                 ┌─────────────────────────────┐
   long URL ────▶│  core/hashing.py            │  fingerprint(url) -> int
                 │  core/base62.py             │  int -> short code (Base62)
                 │  core/shortener.py          │  collision handling, dup detection
                 └──────────────┬──────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
     storage/persistence.py  analytics/tracker.py   api/app.py (Flask) / cli.py
        (SQLite, durable)      (usage stats)         (HTTP / terminal interface)
```

## What this repo contains

| Area | Path | Description |
|---|---|---|
| Encoding | `core/base62.py` | Base62 encode/decode (62-symbol alphabet, URL-safe) |
| Hashing | `core/hashing.py` | Deterministic SHA-256-based fingerprint used to seed each short code |
| Core engine | `core/shortener.py` | In-memory hash maps for O(1) create/lookup/duplicate-detection, with deterministic collision retry + counter fallback |
| Persistence | `storage/persistence.py` | `SQLiteStore` (durable) and `InMemoryStore` (fast, for tests) — same interface, swappable |
| Analytics | `analytics/tracker.py` | Per-link stats, leaderboard, summary report |
| HTTP API | `api/app.py` | Flask REST API: shorten, redirect, analytics, stats |
| CLI | `cli.py` | Terminal interface (shorten / resolve / stats / summary / REPL) |
| Benchmark | `benchmark/benchmark_lookup.py` | Empirically measures average insert/lookup time from 1K to 100K links |
| Tests | `tests/` | 24 passing tests: Base62 round-trips, collision handling, duplicate detection, cross-session persistence, analytics |

## Results

Benchmark output (`python benchmark/benchmark_lookup.py`), timing average per-operation cost as the number of stored links grows 100x:

| N (links) | Insert avg (µs) | Lookup avg (µs) | All codes unique |
|---|---|---|---|
| 1,000 | 6.74 | 0.61 | ✅ |
| 5,000 | 3.88 | 0.45 | ✅ |
| 10,000 | 3.87 | 0.50 | ✅ |
| 50,000 | 4.49 | 0.91 | ✅ |
| 100,000 | 5.55 | 0.90 | ✅ |

Per-operation time stays flat (microsecond range) across a 100x increase in stored links, rather than growing proportionally with N — the empirical signature of **O(1) average-case** hash-map behavior. Full methodology in `REPORT.md`.

## Quick start

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### Run the tests

```bash
pytest tests/ -v
```

### Run the benchmark

```bash
python benchmark/benchmark_lookup.py
```

### Use the CLI (persists across runs via SQLite)

```bash
python cli.py shorten "https://example.com/some/very/long/path"
python cli.py resolve <code>
python cli.py stats <code>
python cli.py summary
python cli.py repl       # interactive mode
```

### Run the HTTP API

```bash
python api/app.py
# in another terminal:
curl -X POST localhost:5000/api/shorten -H "Content-Type: application/json" \
     -d '{"url": "https://example.com/some/long/path"}'
# -> {"short_code": "...", "short_url": "http://localhost:5000/...", "long_url": "..."}

curl -L localhost:5000/<short_code>          # follows the redirect
curl localhost:5000/api/analytics/<short_code>
curl localhost:5000/api/stats
```

## How short codes are generated (hash-based indexing + collision handling)

1. Hash the long URL (SHA-256) and take the first 6 bytes as an integer "fingerprint."
2. Base62-encode that integer into a short code (`core/base62.py`).
3. Look up the code in the in-memory `code_to_url` map:
   - **Unused** → assign it.
   - **Used by the same URL** → duplicate detected; the existing code is reused (no redundant entry, no recomputation needed — this is the reverse `url_to_code` index doing an O(1) check).
   - **Used by a different URL** → genuine collision; re-hash with a different deterministic salt (`attempt` counter) and retry, up to 5 attempts.
4. If all 5 hash-based attempts collide (astronomically unlikely at realistic scale — see `REPORT.md` for the probability estimate), fall back to a monotonically increasing counter, Base62-encoded, which is unique by construction.

This is tested directly in `tests/test_shortener.py` by **forcing** a fake collision (monkeypatching the hash function to return identical fingerprints for two different URLs) and confirming the system still produces two distinct, independently-resolvable codes.

## Persistence and analytics

- Every short code, its long URL, creation timestamp, click count, and last-accessed time live in a SQLite table (`storage/persistence.py`). On startup, `URLShortener` reads every row back into its in-memory maps — so links survive process restarts ("recovery across sessions"), verified in `tests/test_persistence.py` by literally closing one `URLShortener` instance and opening a brand-new one against the same database file.
- `analytics/tracker.py` builds on top of those click counts to produce a leaderboard of most-clicked links and an overall usage summary (`cli.py summary` or `GET /api/stats`).

## Tech stack

- **Language:** Python 3 (standard library `sqlite3`, `hashlib`)
- **Web framework:** Flask (REST API)
- **Testing:** `pytest`
- No external database server required — SQLite is a single file, making the whole project runnable with zero infrastructure setup.

## License

MIT — see `LICENSE`.
