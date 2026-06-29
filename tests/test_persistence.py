import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.shortener import URLShortener
from storage.persistence import SQLiteStore


def test_links_survive_across_shortener_instances(tmp_path):
    """Simulates 'recovery across sessions': create links with one
    URLShortener+SQLiteStore instance, close it, then open a brand-new
    instance pointed at the same DB file and confirm the links resolve."""
    db_path = str(tmp_path / "test.db")

    session1 = URLShortener(store=SQLiteStore(db_path))
    code = session1.shorten("https://example.com/persisted-page")
    session1.close()

    session2 = URLShortener(store=SQLiteStore(db_path))
    try:
        assert session2.resolve(code) == "https://example.com/persisted-page"
    finally:
        session2.close()


def test_duplicate_detection_persists_across_sessions(tmp_path):
    db_path = str(tmp_path / "test_dup.db")

    session1 = URLShortener(store=SQLiteStore(db_path))
    code1 = session1.shorten("https://example.com/dup-across-sessions")
    session1.close()

    session2 = URLShortener(store=SQLiteStore(db_path))
    try:
        code2 = session2.shorten("https://example.com/dup-across-sessions")
        assert code1 == code2
        assert session2.store.count() == 1
    finally:
        session2.close()


def test_click_counts_persist_across_sessions(tmp_path):
    db_path = str(tmp_path / "test_clicks.db")

    session1 = URLShortener(store=SQLiteStore(db_path))
    code = session1.shorten("https://example.com/click-tracked")
    session1.resolve(code)
    session1.resolve(code)
    session1.close()

    session2 = URLShortener(store=SQLiteStore(db_path))
    try:
        stats = session2.stats_for(code)
        assert stats["click_count"] == 2
        session2.resolve(code)
        assert session2.stats_for(code)["click_count"] == 3
    finally:
        session2.close()
