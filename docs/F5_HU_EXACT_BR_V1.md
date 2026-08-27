# F5 exact HU multi-street dynamic best response v1

Date: 2026-08-27  
Status: **CORRECTNESS ORACLE — PENDING CI**

## Purpose

A sampled trainer can be deterministic and still converge to a poor policy. F5 therefore needs a strategy-quality oracle independent of the trainer implementation.

`deepsix_trainer/hu_multistreet_best_response.py` computes exact two-player zero-sum best responses for the tractable HU multi-street reference game and exposes exact `Fraction` exploitability in ante units.

The oracle is deliberately slow. Its job is to judge full-tree CFR, float64 CFR and sampling candidates on small games before the project spends large CPU budgets.

## Information-set constraint

A best responder knows:

- its own two hole cards;
- all public actions;
- the public board and chance history;
- public stacks/commitments/rules.

It does not know the opponent's hidden hand.

The recursion therefore carries a weighted set of compatible fixed-private worlds. At a BR decision, all worlds that share the responder's infoset must choose one common action. The implementation verifies this by requiring one common `PrivateDecisionState.fingerprint()` before maximizing/minimizing.

This avoids the classic invalid shortcut of choosing a different response after looking at the opponent's hidden cards.

## Weighted-world recursion

For one responder private hand:

```text
root compatible hidden worlds
        |
        +-- BR node: one common action across all worlds in infoset
        |
        +-- opponent node: split each world by opponent mixed strategy
        |
        +-- chance node: group worlds by same observable reveal
        |                and multiply by exact physical chance
        |
        +-- terminal: exact gross P0 utility × world weight
```

Deal probabilities remain unconditional. They are not renormalized by the responder's private hand, so summing all responder-hand groups returns the unconditional best-response value.

At chance nodes, a reveal blocked by a hidden opponent card is simply absent from that hidden world. Grouping surviving worlds by public reveal therefore performs the correct card-removal marginalization without leaking which private world occurred.

## APIs

```text
best_response_value_player0_exact(game, opponent_policy)
best_response_value_player1_exact(game, opponent_policy)
exploitability_exact(game, policy)
```

Player 0 BR returns the maximum gross P0 utility. Player 1 BR returns the minimum gross P0 utility achievable by player 1.

For a two-player zero-sum profile:

```text
exploitability = (BR0_max_P0 - BR1_min_P0) / 2
```

The result is an exact `Fraction` and must be non-negative.

## Exact-policy boundary

The oracle accepts opponent probabilities only as `int` or `Fraction` and requires every row to sum exactly to one.

A float trainer must freeze its policy through `FloatTabularPolicy.to_exact_policy()` before exact BR evaluation. This keeps numerical approximation outside the quality oracle rather than weakening the oracle's contract.

## Initial gates

Tests require:

- the fixed-policy value lies between the two exact BR bounds;
- exploitability equals the exact BR-gap formula;
- exploitability is non-negative;
- repeated evaluation is deterministic;
- multiple hidden opponent worlds are handled under one responder infoset;
- raw float probabilities are rejected.

## Role in architecture selection

Once this gate is green, the same tiny F5 game can compare:

- exact Fraction full-tree CFR/RM+;
- float64 full-tree CFR/RM+;
- chance-sampled CFR;
- external-sampling MCCFR.

The relevant production metric becomes **exploitability/error reduction per wall-clock CPU and memory**, not solver sophistication by itself.
