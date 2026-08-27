# F5 exact range-weighted chance oracle v1

Date: 2026-08-26  
Status: **REFERENCE ORACLE / PARTIAL F5 FOUNDATION**

## Purpose

The fixed-assignment chance oracle in `multistreet_chance.py` answers the physical question: given every private card in one branch, which public board reveal can occur next and with what probability?

An imperfect-information solver needs a second question: when opponent private cards are uncertain and weighted by the current public reach, what is the marginal probability of each next board reveal?

`deepsix_trainer.multistreet_range_chance.enumerate_range_weighted_board_chance()` is the exact small-support reference for that second layer.

## Exact identity

For a candidate public reveal `R`:

```text
P(R | public history, fixed private cards)
 = compatible_reach_mass(R)
   / total_compatible_reach_mass
   / physical_reveals_per_private_assignment
```

`compatible_reach_mass(R)` is the exact joint private reach mass remaining after the current public board, fixed private cards and candidate reveal are treated as dead cards.

Because every compatible assignment contributes exactly two cards per represented player, every assignment has the same number of physical board reveals remaining. That makes the final physical denominator constant across assignments.

All values use `Fraction`; the returned probabilities must sum to exactly one.

## Why this matters

Public actions change private reach. Private reach changes card-removal probabilities. Therefore future public chance is not generally uniform after marginalizing unknown private cards.

Example with an equal two-hand opponent range on the flop:

```text
50% AcKc
50% AhKh
```

A neutral turn card that appears in neither private branch remains available under 100% of the reach mass. `Ac` is available only under the `AhKh` branch, so its marginal turn probability is exactly half the neutral-card probability.

If an observed public action reweights the two branches, the future chance distribution changes by the same exact blocker-conditioned logic.

This is the missing bridge between:

```text
public action likelihoods
        ↓
private range/reach propagation
        ↓
blocker-conditioned board chance
        ↓
next public strategic state
```

## Relation to the fixed-assignment oracle

A singleton opponent reach plus one fixed Hero hand must collapse exactly to `enumerate_exact_board_chance()`.

The regression suite proves that identity, including the 4,960 HU preflop flop combinations for four fixed hole cards.

## Scope and performance boundary

This implementation calls the exact joint-mass oracle for candidate reveals. Its intended use is:

- tractable HU/small-support solver audits;
- reference distributions for sampled chance traversals;
- regression tests for blocker handling;
- validation of future optimized/native chance code.

It is not the production hot path for full 630-combo multiway ranges. F6 will need sampling, caching, factorization or another scalable representation, and any optimization must prove parity against this oracle on tractable supports.

Zero-probability reveals are omitted from the returned support.

## Gates

The tests prove:

- singleton reach == fixed-assignment chance oracle;
- exact 4,960-flop HU support for a singleton opponent range + fixed Hero hand;
- uncertain blockers change marginal turn probability by the mathematically expected ratio;
- applying a public-action likelihood update changes later chance exactly;
- small multiway supports with card conflicts normalize to exactly one;
- river has no further board chance;
- malformed fixed-private support, public/private overlap and zero compatible reach fail closed.

## F5 foundation after this gate

The solver-independent reference stack is now:

```text
exact public/private strategic identity
exact deterministic action replay/fork
exact fixed-private physical chance
exact public-action private reach propagation
exact range-weighted marginal chance
```

The next useful construction is a very small HU multi-street traversal that combines these contracts end-to-end before the production solver family is frozen from Ryzen evidence.
