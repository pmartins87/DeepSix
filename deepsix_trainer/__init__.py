"""Training and solver experiments for DeepSix.

The package starts with tiny, exactly auditable games.  Large Short Deck
training code must beat these baselines and preserve their invariants before it
is trusted with long Ryzen runs.
"""

from .kuhn import (
    KuhnCFR,
    KuhnPolicy,
    exploitability,
    expected_value,
)

__all__ = [
    "KuhnCFR",
    "KuhnPolicy",
    "exploitability",
    "expected_value",
]
