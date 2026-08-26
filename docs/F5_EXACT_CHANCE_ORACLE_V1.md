# F5 exact board-chance oracle v1

Date: 2026-08-26  
Status: **REFERENCE ORACLE / PARTIAL F5 FOUNDATION**

## Purpose

A multi-street poker solver needs an explicit chance contract. The production
trainer may eventually use external sampling, outcome sampling or another
variance/cost trade-off, but those methods need an exact support to be checked
against on tractable states.

`deepsix_trainer.multistreet_chance.enumerate_exact_board_chance()` enumerates
the next public reveal for one **complete fixed private-card assignment**.

## Exact supports in 36-card Short Deck

For a HU branch with four fixed hole cards:

```text
preflop -> flop : C(32, 3) = 4,960 equally likely flop reveals
flop    -> turn : 29 equally likely turn cards
turn    -> river: 28 equally likely river cards
river           : no further board chance
```

For a six-way branch with twelve fixed private cards:

```text
preflop -> flop : C(24, 3) = 2,024
flop    -> turn : 21
turn    -> river: 20
```

Probabilities are stored as exact `Fraction` values and are required to sum to
one.

The flop reveal is represented as an unordered three-card combination because
those cards arrive simultaneously. Turn and river remain ordered transitions.

## Scope boundary

This oracle does **not** pretend that unknown opponent cards are dead cards.
The caller must supply the complete private assignment fixed in that traversal
branch. When opponents are uncertain, their range/reach distribution is
integrated one layer above this function.

That separation matters:

```text
private assignment / range-reach layer
                 ↓
exact physical board chance oracle
                 ↓
public strategic state
```

It prevents us from accidentally calculating chance probabilities from the
hero's visible cards alone while ignoring card removal by sampled/enumerated
opponent hands.

## Why physical outcomes are not prematurely merged

The v1 oracle keeps every physical chance outcome distinct. Public-board suit
canonicalization exists in `multistreet_state`, but collapsing chance outcomes
by public board alone can be wrong when fixed private cards/ranges break the
same suit symmetry.

A future optimized chance grouper may quotient outcomes only after proving that
the full public+private/range state admits that exact symmetry.

## Gates

Tests prove:

- HU support counts `4960 / 29 / 28`;
- six-way support counts `2024 / 21 / 20`;
- exact probability sum = 1;
- flop unordered / later streets ordered;
- card uniqueness for every generated outcome;
- duplicate cards, public/private overlap and invalid board shapes fail closed.

## Role in F5

Together with `multistreet_state`, `multistreet_reference` and exact
`reach.py`, this gives F5 four solver-independent correctness primitives before
the Ryzen architecture choice:

```text
exact strategic identity
exact fixed-deal action transition
exact fixed-assignment board chance
exact private range/reach propagation
```

The production solver remains unselected until F4 evidence chooses the
traversal/action/state family.
