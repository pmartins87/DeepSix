"""Short Deck card representation for DeepSix.

The DeepSix Core uses a compact 0..35 card space.  OpenHoldem6Plus is allowed
to keep its legacy 52-card representation at the scraper/UI boundary, but it
must decode that representation to rank/suit and pass through
``legacy_rank_suit_to_core`` before a card enters the strategic core.

No rank below six is valid in DeepSix.
"""

from __future__ import annotations

from dataclasses import dataclass

RANKS = "6789TJQKA"
SUITS = "cdhs"

RANK_TO_INDEX = {rank: index for index, rank in enumerate(RANKS)}
SUIT_TO_INDEX = {suit: index for index, suit in enumerate(SUITS)}
INDEX_TO_RANK = {index: rank for rank, index in RANK_TO_INDEX.items()}
INDEX_TO_SUIT = {index: suit for suit, index in SUIT_TO_INDEX.items()}

MIN_LEGACY_RANK = 6
MAX_LEGACY_RANK = 14
NUM_RANKS = 9
NUM_SUITS = 4
NUM_CARDS = NUM_RANKS * NUM_SUITS


class ShortDeckCardError(ValueError):
    """Raised when a card is not valid under DeepSix Short Deck rules."""


@dataclass(frozen=True, order=True)
class DecodedCard:
    rank: str
    suit: str


def encode_card(rank: str, suit: str) -> int:
    """Encode a Short Deck rank/suit to the compact DeepSix card id 0..35."""
    rank = str(rank).upper()
    suit = str(suit).lower()
    if rank not in RANK_TO_INDEX:
        raise ShortDeckCardError(f"invalid Short Deck rank: {rank!r}")
    if suit not in SUIT_TO_INDEX:
        raise ShortDeckCardError(f"invalid suit: {suit!r}")
    return SUIT_TO_INDEX[suit] * NUM_RANKS + RANK_TO_INDEX[rank]


def decode_card(card: int) -> DecodedCard:
    """Decode compact DeepSix card id 0..35."""
    if isinstance(card, bool) or not isinstance(card, int):
        raise ShortDeckCardError(f"card id must be int, got {type(card).__name__}")
    if card < 0 or card >= NUM_CARDS:
        raise ShortDeckCardError(f"card id out of range: {card}")
    suit_index, rank_index = divmod(card, NUM_RANKS)
    return DecodedCard(INDEX_TO_RANK[rank_index], INDEX_TO_SUIT[suit_index])


def parse_card(text: str) -> int:
    """Parse cards such as ``Ac``, ``Th`` or ``6s`` into compact ids."""
    text = str(text).strip()
    if len(text) != 2:
        raise ShortDeckCardError(f"card must have exactly two characters: {text!r}")
    return encode_card(text[0], text[1])


def format_card(card: int) -> str:
    """Return canonical two-character representation, e.g. ``Ac``."""
    decoded = decode_card(card)
    return f"{decoded.rank}{decoded.suit}"


def legacy_rank_suit_to_core(openholdem_rank: int, suit: int) -> int:
    """Convert decoded OpenHoldem rank/suit values to compact DeepSix card id.

    OpenHoldem exposes ranks 2..14, where 14 is Ace, and suits 0..3.  We do
    not assume anything about the raw StdDeck integer layout here: the OH fork
    must first decode the legacy card to rank/suit, then call this function.

    Ranks 2..5 are deliberately rejected instead of being silently mapped.
    """
    if isinstance(openholdem_rank, bool) or not isinstance(openholdem_rank, int):
        raise ShortDeckCardError("OpenHoldem rank must be an integer")
    if openholdem_rank < MIN_LEGACY_RANK or openholdem_rank > MAX_LEGACY_RANK:
        raise ShortDeckCardError(
            f"INVALID_SHORTDECK_CARD rank={openholdem_rank}; valid ranks are 6..14"
        )
    if isinstance(suit, bool) or not isinstance(suit, int) or suit < 0 or suit >= NUM_SUITS:
        raise ShortDeckCardError(f"invalid OpenHoldem suit index: {suit!r}")

    rank_char = RANKS[openholdem_rank - MIN_LEGACY_RANK]
    suit_char = SUITS[suit]
    return encode_card(rank_char, suit_char)
