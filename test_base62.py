import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from core import base62


def test_round_trip_small_numbers():
    for n in [0, 1, 5, 61, 62, 63, 1000, 999999]:
        encoded = base62.encode(n)
        assert base62.decode(encoded) == n


def test_round_trip_large_number():
    n = 2**48 - 1
    encoded = base62.encode(n)
    assert base62.decode(encoded) == n


def test_encode_zero_is_single_char():
    assert base62.encode(0) == "0"


def test_encode_negative_raises():
    with pytest.raises(ValueError):
        base62.encode(-1)


def test_decode_empty_raises():
    with pytest.raises(ValueError):
        base62.decode("")


def test_decode_invalid_char_raises():
    with pytest.raises(ValueError):
        base62.decode("abc!")


def test_pad_adds_leading_chars():
    assert base62.pad("a", 6) == "00000a"
    assert base62.pad("abcdef", 6) == "abcdef"
    assert base62.pad("abcdefg", 6) == "abcdefg"  # already longer than min


def test_encoding_is_monotonically_non_decreasing_in_length():
    # sanity check: larger numbers should never produce *shorter* codes
    prev_len = 0
    for n in [0, 61, 62, 3843, 3844, 238327, 238328]:
        length = len(base62.encode(n))
        assert length >= prev_len
        prev_len = length
