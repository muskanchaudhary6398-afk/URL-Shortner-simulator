"""
storage/persistence.py

SQLite-backed persistence for the URL shortener. The in-memory hash maps
in core/shortener.py are the hot path for O(1) lookups/inserts; this module
is the durability layer underneath them -- on startup, URLShortener loads
every row here back into memory ("link recovery across sessions"), and on
every create/click it writes the change through to disk.

Schema:
    urls(
        short_code   TEXT PRIMARY KEY,
        long_url     TEXT NOT NULL,
        created_at   REAL NOT NULL,      -- unix timestamp
        click_count  INTEGER NOT NULL DEFAULT 0,
        last_accessed REAL               -- unix timestamp, NULL until first click
    )

    An index on long_url supports fast duplicate-detection rehydration on load.
"""

import sqlite3
import time
from pathlib import Path
from typing import Optional, List, Dict


class SQLiteStore:
    def __init__(self, db_path: str = "url_shortener.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: Flask's dev server (and most WSGI servers)
        # may handle requests on a different thread than the one that
        # created this connection. We accept cross-thread use here since
        # all access in this project goes through the single global
        # `shortener` instance and SQLite itself serializes writes; for a
        # high-concurrency production deployment you'd use a connection
        # pool or a per-request connection instead.
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                short_code    TEXT PRIMARY KEY,
                long_url      TEXT NOT NULL,
                created_at    REAL NOT NULL,
                click_count   INTEGER NOT NULL DEFAULT 0,
                last_accessed REAL
            )
            """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_long_url ON urls(long_url)")
        self.conn.commit()

    # ---------------------------------------------------------------- writes

    def insert(self, short_code: str, long_url: str, created_at: Optional[float] = None):
        self.conn.execute(
            "INSERT INTO urls (short_code, long_url, created_at, click_count, last_accessed) "
            "VALUES (?, ?, ?, 0, NULL)",
            (short_code, long_url, created_at or time.time()),
        )
        self.conn.commit()

    def record_click(self, short_code: str, accessed_at: Optional[float] = None):
        self.conn.execute(
            "UPDATE urls SET click_count = click_count + 1, last_accessed = ? "
            "WHERE short_code = ?",
            (accessed_at or time.time(), short_code),
        )
        self.conn.commit()

    def delete(self, short_code: str):
        self.conn.execute("DELETE FROM urls WHERE short_code = ?", (short_code,))
        self.conn.commit()

    # ----------------------------------------------------------------- reads

    def load_all(self) -> List[Dict]:
        """Used on startup to rehydrate the in-memory hash maps."""
        rows = self.conn.execute("SELECT * FROM urls").fetchall()
        return [dict(row) for row in rows]

    def get(self, short_code: str) -> Optional[Dict]:
        row = self.conn.execute(
            "SELECT * FROM urls WHERE short_code = ?", (short_code,)
        ).fetchone()
        return dict(row) if row else None

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS c FROM urls").fetchone()["c"]

    def total_clicks(self) -> int:
        result = self.conn.execute("SELECT SUM(click_count) AS s FROM urls").fetchone()["s"]
        return result or 0

    def top_urls(self, n: int = 10) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM urls ORDER BY click_count DESC LIMIT ?", (n,)
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self):
        self.conn.close()


class InMemoryStore:
    """A no-disk stand-in implementing the same interface as SQLiteStore, for
    fast unit tests / non-persistent dev usage. URLShortener works against
    either store transparently."""

    def __init__(self):
        self._rows: Dict[str, Dict] = {}

    def insert(self, short_code: str, long_url: str, created_at: Optional[float] = None):
        self._rows[short_code] = {
            "short_code": short_code, "long_url": long_url,
            "created_at": created_at or time.time(),
            "click_count": 0, "last_accessed": None,
        }

    def record_click(self, short_code: str, accessed_at: Optional[float] = None):
        if short_code in self._rows:
            self._rows[short_code]["click_count"] += 1
            self._rows[short_code]["last_accessed"] = accessed_at or time.time()

    def delete(self, short_code: str):
        self._rows.pop(short_code, None)

    def load_all(self) -> List[Dict]:
        return list(self._rows.values())

    def get(self, short_code: str) -> Optional[Dict]:
        return self._rows.get(short_code)

    def count(self) -> int:
        return len(self._rows)

    def total_clicks(self) -> int:
        return sum(r["click_count"] for r in self._rows.values())

    def top_urls(self, n: int = 10) -> List[Dict]:
        return sorted(self._rows.values(), key=lambda r: r["click_count"], reverse=True)[:n]

    def close(self):
        pass
