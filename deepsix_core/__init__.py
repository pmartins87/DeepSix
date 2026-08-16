"""DeepSix reference core.

This package starts as a correctness-first reference implementation. Performance-
critical trainer/runtime code may later use another implementation, but it must
match this package's versioned semantics and regression vectors.
"""

from .betting import (
    BettingConfig,
    BettingPlayer,
    BettingRoundState,
    BettingStateError,
    RoundLegalActions,
    ShortAllInReopenPolicy,
    apply_action,
    legal_actions,
    round_chip_total,
    start_betting_round,
)
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
from .legal import LegalActionError, LegalActionSet, legal_actions_for_hero
from .pots import PotAccountingError, PotLayer, build_pot_layers
from .replay import (
    DecisionToken,
    REPLAY_SCHEMA_VERSION,
    ReplayFrame,
    ReplayIntegrityError,
    observation_from_dict,
    observation_to_dict,
)
from .rules import (
    GameRuleError,
    action_order_from_dealer,
    initial_ante_contributions,
    validate_player_count,
)
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
    "BettingConfig",
    "BettingPlayer",
    "BettingRoundState",
    "BettingStateError",
    "RoundLegalActions",
    "ShortAllInReopenPolicy",
    "apply_action",
    "legal_actions",
    "round_chip_total",
    "start_betting_round",
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
    "LegalActionError",
    "LegalActionSet",
    "legal_actions_for_hero",
    "PotAccountingError",
    "PotLayer",
    "build_pot_layers",
    "DecisionToken",
    "REPLAY_SCHEMA_VERSION",
    "ReplayFrame",
    "ReplayIntegrityError",
    "observation_from_dict",
    "observation_to_dict",
    "GameRuleError",
    "action_order_from_dealer",
    "initial_ante_contributions",
    "validate_player_count",
    "ActionEvent",
    "ActionKind",
    "ObservationError",
    "SCHEMA_VERSION",
    "SeatObservation",
    "Street",
    "TableObservation",
]
