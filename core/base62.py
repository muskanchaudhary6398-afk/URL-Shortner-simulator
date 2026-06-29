"""
core/base62.py

Base62 encoding using [0-9 A-Z a-z] (62 symbols). Used to turn integer IDs /
hash values into short, URL-safe, case-sensitive alphanumeric strings —
e.g. 125 -> "21", 3521614606208 -> "3kV9Cz".

Why Base62 over Base64: Base64 includes '+' and '/', which need
URL-encoding to be safely used in a path segment. Base62 is already
URL-safe with no escaping needed.
"""

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE = len(ALPHABET)  # 62
_CHAR_TO_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}


def encode(number: int) -> str:
    """Encode a non-negative integer into a Base62 string."""
    if number < 0:
        raise ValueError("Base62 encoding only supports non-negative integers")
    if number == 0:
        return ALPHABET[0]

    digits = []
    n = number
    while n > 0:
        n, remainder = divmod(n, BASE)
        digits.append(ALPHABET[remainder])
    return "".join(reversed(digits))


def decode(code: str) -> int:
    """Decode a Base62 string back into its integer value."""
    if not code:
        raise ValueError("Cannot decode an empty string")

    number = 0
    for ch in code:
        if ch not in _CHAR_TO_INDEX:
            raise ValueError(f"Invalid Base62 character: {ch!r}")
        number = number * BASE + _CHAR_TO_INDEX[ch]
    return number


def pad(code: str, min_length: int, pad_char: str = ALPHABET[0]) -> str:
    """Left-pad a Base62 string to a minimum length (cosmetic — keeps short
    codes a consistent visual width, e.g. always >= 6 chars)."""
    if len(code) >= min_length:
        return code
    return pad_char * (min_length - len(code)) + code
