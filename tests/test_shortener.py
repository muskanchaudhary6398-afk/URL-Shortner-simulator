import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.shortener import URLShortener
from storage.persistence import InMemoryStore
import core.hashing as hashing_module


def make_shortener():
    return URLShortener(store=InMemoryStore())


def test_shorten_and_resolve_round_trip():
    s = make_shortener()
    code = s.shorten("https://example.com/page1")
    assert s.resolve(code) == "https://example.com/page1"


def test_resolve_unknown_code_returns_none():
    s = make_shortener()
    assert s.resolve("doesnotexist") is None


def test_duplicate_url_returns_same_code():
    s = make_shortener()
    code1 = s.shorten("https://example.com/dup")
    code2 = s.shorten("https://example.com/dup")
    assert code1 == code2
    assert s.store.count() == 1  # no redundant entry was created


def test_different_urls_get_different_codes():
    s = make_shortener()
    code1 = s.shorten("https://example.com/a")
    code2 = s.shorten("https://example.com/b")
    assert code1 != code2


def test_thousands_of_links_all_unique_and_resolvable():
    s = make_shortener()
    n = 5000
    urls = [f"https://example.com/article/{i}" for i in range(n)]
    codes = [s.shorten(u) for u in urls]

    assert len(set(codes)) == n, "all codes must be unique across thousands of links"
    for url, code in zip(urls, codes):
        assert s.resolve(code) == url


def test_collision_is_handled_with_deterministic_retry(monkeypatch):
    """Force a hash collision: make fingerprint() return the SAME value for
    two different URLs on attempt=0, and confirm the shortener detects the
    collision and falls through to attempt=1's fingerprint instead of
    silently overwriting the first URL's mapping."""
    s = make_shortener()

    real_fingerprint = hashing_module.fingerprint

    def colliding_fingerprint(url, attempt=0):
        if attempt == 0 and url in ("https://example.com/collide-a", "https://example.com/collide-b"):
            return 999999  # force identical attempt-0 fingerprint for both URLs
        return real_fingerprint(url, attempt=attempt)

    monkeypatch.setattr("core.shortener.fingerprint", colliding_fingerprint)

    code_a = s.shorten("https://example.com/collide-a")
    code_b = s.shorten("https://example.com/collide-b")

    assert code_a != code_b, "colliding URLs must still end up with distinct codes"
    assert s.resolve(code_a) == "https://example.com/collide-a"
    assert s.resolve(code_b) == "https://example.com/collide-b"


def test_collision_exhaustion_falls_back_to_counter(monkeypatch):
    """If every hash-based attempt collides, the shortener must still
    produce a valid, unique code via the fallback counter rather than
    failing or silently corrupting an existing mapping."""
    s = make_shortener()

    def always_colliding_fingerprint(url, attempt=0):
        return 12345  # every attempt collides, forcing exhaustion

    monkeypatch.setattr("core.shortener.fingerprint", always_colliding_fingerprint)

    # Seed one entry that "owns" the always-colliding code first
    first_code = s.shorten("https://example.com/first")
    second_code = s.shorten("https://example.com/second")

    assert first_code != second_code
    assert s.resolve(first_code) == "https://example.com/first"
    assert s.resolve(second_code) == "https://example.com/second"
    assert second_code.startswith("Z"), "fallback codes use the 'Z' counter prefix"


def test_resolve_increments_click_count():
    s = make_shortener()
    code = s.shorten("https://example.com/clicked")
    s.resolve(code)
    s.resolve(code)
    s.resolve(code)
    stats = s.stats_for(code)
    assert stats["click_count"] == 3


def test_empty_url_raises():
    import pytest
    s = make_shortener()
    with pytest.raises(ValueError):
        s.shorten("")
    with pytest.raises(ValueError):
        s.shorten("   ")
