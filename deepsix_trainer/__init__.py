"""Training and solver experiments for DeepSix.

The package starts with tiny, exactly auditable games.  Large Short Deck
training code must beat these baselines and preserve their invariants before it
is trusted with long Ryzen runs.
"""

from .kuhn import (
    KuhnCFR,
    KuhnPolicy,
    exploitability as kuhn_exploitability,
    expected_value as kuhn_expected_value,
)
from .river_microgame import (
    RangeHand,
    RiverCFR,
    RiverDeal,
    RiverMicrogameConfig,
    RiverMicrogameError,
    RiverPolicy,
    best_response_value_player0 as river_best_response_value_player0,
    best_response_value_player1 as river_best_response_value_player1,
    expected_value as river_expected_value,
    exploitability as river_exploitability,
)
from .river_multisize import (
    MultiSizeDeal,
    RiverMultiSizeCFR,
    RiverMultiSizeConfig,
    RiverMultiSizeError,
    RiverMultiSizePolicy,
    best_response_value_player0 as multisize_best_response_value_player0,
    best_response_value_player1 as multisize_best_response_value_player1,
    expected_value as multisize_expected_value,
    exploitability as multisize_exploitability,
    uniform_policy as multisize_uniform_policy,
)

__all__ = [
    "KuhnCFR",
    "KuhnPolicy",
    "kuhn_exploitability",
    "kuhn_expected_value",
    "RangeHand",
    "RiverCFR",
    "RiverDeal",
    "RiverMicrogameConfig",
    "RiverMicrogameError",
    "RiverPolicy",
    "river_best_response_value_player0",
    "river_best_response_value_player1",
    "river_expected_value",
    "river_exploitability",
    "MultiSizeDeal",
    "RiverMultiSizeCFR",
    "RiverMultiSizeConfig",
    "RiverMultiSizeError",
    "RiverMultiSizePolicy",
    "multisize_best_response_value_player0",
    "multisize_best_response_value_player1",
    "multisize_expected_value",
    "multisize_exploitability",
    "multisize_uniform_policy",
]
