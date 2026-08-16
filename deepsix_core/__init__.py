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
from .canonical import (
    CanonicalAction,
    CanonicalSeat,
    CanonicalState,
    CanonicalizationError,
    canonicalize_observation,
)
from .equity import EquityResult, exact_heads_up_equity
from .evaluator import HandCategory, HandValue, evaluate_best, evaluate_five
from .handclasses import ALL_HAND_CLASSES, combo_count, hand_class_from_cards
from .pots import PotAccountingError, PotLayer, build_pot_layers
from .state import (
    ActionEvent,
    ActionKind,
    ObservationError,
    SCHEMA_VERSION,
    SeatObservation,
    Street,
    TableObservation,
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
    "CanonicalAction",
    "CanonicalSeat",
    "CanonicalState",
    "CanonicalizationError",
    "canonicalize_observation",
    "EquityResult",
    "exact_heads_up_equity",
    "HandCategory",
    "HandValue",
    "evaluate_best",
    "evaluate_five",
    "ALL_HAND_CLASSES",
    "combo_count",
    "hand_class_from_cards",
    "PotAccountingError",
    "PotLayer",
    "build_pot_layers",
    "ActionEvent",
    "ActionKind",
    "ObservationError",
    "SCHEMA_VERSION",
    "SeatObservation",
    "Street",
    "TableObservation",
]
