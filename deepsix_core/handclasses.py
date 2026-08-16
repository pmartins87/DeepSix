"""Preflop hand-class helpers for a 36-card Short Deck."""

from __future__ import annotations

from .cards import RANKS, decode_card

RANKS_DESC = "AKQJT9876"


def all_hand_classes() -> tuple[str, ...]:
    """Return the 81 canonical Short Deck preflop hand classes."""
    out: list[str] = []
    for rank in RANKS_DESC:
        out.append(rank + rank)
    for i, high in enumerate(RANKS_DESC):
        for low in RANKS_DESC[i + 1 :]:
            out.append(high + low + "s")
            out.append(high + low + "o")
    return tuple(out)


ALL_HAND_CLASSES = all_hand_classes()


def combo_count(hand_class: str) -> int:
    if hand_class not in ALL_HAND_CLASSES:
        raise ValueError(f"invalid Short Deck hand class: {hand_class!r}")
    if len(hand_class) == 2:
        return 6
    return 4 if hand_class.endswith("s") else 12


def hand_class_from_cards(card_a: int, card_b: int) -> str:
    if card_a == card_b:
        raise ValueError("hole cards must be distinct")
    a = decode_card(card_a)
    b = decode_card(card_b)
    if a.rank == b.rank:
        return a.rank + a.rank

    rank_index = {rank: index for index, rank in enumerate(RANKS)}
    if rank_index[a.rank] > rank_index[b.rank]:
        high, low = a, b
    else:
        high, low = b, a
    suffix = "s" if high.suit == low.suit else "o"
    return high.rank + low.rank + suffix
