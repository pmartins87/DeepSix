"""DeepSix reference core.

This package starts as a correctness-first reference implementation. Performance-
critical trainer/runtime code may later use another implementation, but it must
match this package's versioned semantics and regression vectors.
"""

from .cards import (
    RANKS,
    SUITS,
    ShortDeckCardError,
    decode_card,
    encode_card,
    format_card,
    legacy_rank_suit_to_core,
    parse_card,
)

__all__ = [
    "RANKS",
    "SUITS",
    "ShortDeckCardError",
    "decode_card",
    "encode_card",
    "format_card",
    "legacy_rank_suit_to_core",
    "parse_card",
]
