import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.shortener import URLShortener
from storage.persistence import InMemoryStore
from analytics.tracker import AnalyticsTracker


def make_shortener():
    return URLShortener(store=InMemoryStore())


def test_link_stats_reflect_clicks():
    s = make_shortener()
    code = s.shorten("https://example.com/tracked")
    s.resolve(code)
    s.resolve(code)

    tracker = AnalyticsTracker(s)
    stats = tracker.get_link_stats(code)

    assert stats.click_count == 2
    assert stats.long_url == "https://example.com/tracked"
    assert stats.last_accessed is not None


def test_unknown_code_returns_none():
    s = make_shortener()
    tracker = AnalyticsTracker(s)
    assert tracker.get_link_stats("nope") is None


def test_leaderboard_orders_by_click_count():
    s = make_shortener()
    code_low = s.shorten("https://example.com/low")
    code_high = s.shorten("https://example.com/high")
    code_mid = s.shorten("https://example.com/mid")

    for _ in range(1):
        s.resolve(code_low)
    for _ in range(10):
        s.resolve(code_high)
    for _ in range(5):
        s.resolve(code_mid)

    tracker = AnalyticsTracker(s)
    leaderboard = tracker.leaderboard(3)

    assert [link.short_code for link in leaderboard] == [code_high, code_mid, code_low]


def test_summary_computes_average_clicks():
    s = make_shortener()
    code1 = s.shorten("https://example.com/x")
    code2 = s.shorten("https://example.com/y")
    s.resolve(code1)
    s.resolve(code1)
    s.resolve(code2)

    tracker = AnalyticsTracker(s)
    summary = tracker.summary()

    assert summary["total_urls"] == 2
    assert summary["total_clicks"] == 3
    assert summary["avg_clicks_per_url"] == 1.5
