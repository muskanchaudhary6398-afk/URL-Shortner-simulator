"""
core/hashing.py

Generates a deterministic integer "fingerprint" of a URL, which is then
Base62-encoded into a candidate short code. The same URL (plus the same
salt/attempt number) always produces the same fingerprint -- this is what
lets core/shortener.py detect duplicates and retry deterministically on
collision (see collision-handling logic in shortener.py).
"""

import hashlib

# Truncating to 6 bytes (48 bits) gives ~2.8e14 possible values -- comfortably
# enough keyspace to keep collision probability low across thousands to low
# millions of links (birthday-bound collision risk only becomes meaningful
# around sqrt(2^48) ~ 16.7 million links), while keeping codes short
# (Base62 of a 48-bit number is at most 8 characters).
FINGERPRINT_BYTES = 6


def fingerprint(url: str, attempt: int = 0) -> int:
    """Deterministic integer fingerprint for a URL.

    `attempt` is mixed into the hash input so that, on a collision, the
    caller can request a *different* deterministic fingerprint for the same
    URL (rather than a random one) -- keeping the whole encode pipeline
    reproducible and testable.
    """
    payload = f"{url}|{attempt}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:FINGERPRINT_BYTES], byteorder="big")
