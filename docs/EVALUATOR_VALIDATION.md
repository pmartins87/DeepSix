# Evaluator validation status

## Current status

The DeepSix 36-card evaluator has passed three different kinds of checks, but is not yet declared the final performance evaluator used by the trainer.

## 1. Rule-specific unit vectors

Tests cover:

- removed ranks 2..5 rejected;
- A-6-7-8-9 recognized as a 9-high straight;
- Flush > Full House;
- Four of a Kind > Flush;
- Straight Flush > Four of a Kind;
- best-five selection from 5/6/7 cards;
- duplicate-card rejection.

## 2. Exhaustive 5-card distribution

Every `C(36,5) = 376,992` possible five-card set is evaluated in CI. The resulting category counts must exactly equal the analytical Short Deck counts:

| Category | Count |
|---|---:|
| High Card | 122,400 |
| One Pair | 193,536 |
| Two Pair | 36,288 |
| Three of a Kind | 16,128 |
| Straight | 6,120 |
| Full House | 1,728 |
| Flush | 480 |
| Four of a Kind | 288 |
| Straight Flush | 24 |
| **Total** | **376,992** |

This catches broad classes of deck/rank/straight/flush/multiplicity errors independently of particular hand examples.

## 3. Independent primary-source reference vectors

Reference vectors are also transcribed from PokerKit's `ShortDeckHoldemHand` and `ShortDeckHoldemLookup` doctests at the pinned source snapshot:

`uoftcprg/pokerkit@5841c0afe4d6eb71ae5db0f8a6a376ee3e329afb`

Relevant primary-source files:

- `pokerkit/hands.py`
- `pokerkit/lookups.py`

The vectors independently confirm, among other cases:

- A6789 is a valid Short Deck straight;
- Straight > Three of a Kind in the targeted ranking;
- Full House > Straight;
- Flush > Full House;
- ranks 2..5 are invalid in a Short Deck hand.

## What remains before final evaluator certification

- larger cross-engine randomized comparison against an independently implemented Short Deck evaluator;
- native/high-performance implementation for trainer/runtime hot paths;
- bit-for-bit regression vectors proving the optimized implementation matches this correctness-first reference implementation.

The pure-Python exact HU equity oracle is a validation tool, not the intended production hot path. A preflop exact query requires 201,376 legal five-card board runouts for two fixed hole-card pairs and should eventually be backed by a much faster native evaluator/table implementation.
