# F5 exact HU multi-street CFR/RM+ reference v1

Date: 2026-08-26  
Status: **CORRECTNESS SOLVER / PENDING CI**

## Purpose

`hu_multistreet_cfr.py` is the first tabular solver adapter attached to the real F5 multi-street reference game. It is deliberately a correctness implementation, not a production architecture decision.

The solver traverses the same exact objects already gated separately:

```text
compatible private deal chance
 -> canonical private infoset
 -> Core legal action subset
 -> explicit action branch
 -> exact physical board chance
 -> next-street infoset
 -> exact terminal gross utility
```

## Why exact `Fraction`

All regret values, strategies, reach probabilities, private-deal probabilities and board-chance probabilities are `Fraction` in this implementation. That is intentionally expensive. It gives us an arithmetic oracle against which future float/native/sampled implementations can be compared on tractable games.

Production training will not use unbounded rational arithmetic at scale.

## Solver modes

Two synchronous update rules share the same extensive form:

- `RegretMode.VANILLA` — cumulative vanilla CFR regrets;
- `RegretMode.PLUS` — cumulative regrets clipped at zero after each complete iteration (our existing project convention is named RM+ rather than claiming identity with every CFR+ implementation).

All private deals and chance/action branches in one iteration see the same start-of-iteration regret table. Iteration deltas are committed only after the full traversal.

## Utility boundary

Training uses **gross poker delta only**. For seat 0 the terminal value is `gross_poker_delta_antes`; seat 1 uses the zero-sum opposite sign through the regret update.

This is intentional:

```text
sum gross poker utility = 0
```

Net cash utility includes rake and is negative-sum. A frozen strategy can be evaluated under `NET_CASH_DELTA` by `HuReferenceMicrogame`, but the v1 two-player zero-sum CFR guarantee is never silently applied to net-rake utility.

## Infoset identity

The tabular key is `PrivateDecisionState.fingerprint()`.

That fingerprint contains:

- exact canonical public state/history;
- acting position;
- acting player's own canonical private hand;

and excludes opponent private cards. Multiple physical hidden deals compatible with the same infoset therefore accumulate into the same regret node.

## Reach weighting

The synchronous traversal carries:

```text
reach0
reach1
chance_reach
```

`chance_reach` begins at the exact compatible private-deal probability and is multiplied by each explicit board chance probability. Regret updates use counterfactual reach (`chance × opponent reach`); average-strategy accumulation uses (`chance × own reach`).

This mirrors the already-gated river CFR/RM+ methodology while replacing the river-specific game with the new exact multi-street branch/state/chance contracts.

## Test game

The CI solver gate intentionally uses one compatible private assignment and 51 monetary units per player at the $0.25-reference stake. After the frozen passive preflop completion, each player has exactly one unit behind on the flop.

That fixture preserves real flop/turn/river chance and real short-all-in legality while sharply limiting betting depth, allowing a full exact rational traversal to run as a correctness test rather than a benchmark.

## Gates

Tests require:

- one exact full-tree iteration creates valid infosets;
- every average-policy row is an exact probability distribution;
- same game + same mode + one iteration gives identical semantic snapshot and policy fingerprint;
- RM+ leaves all cumulative regrets nonnegative after commit;
- the average strategy is directly evaluable by the exact HU reference game and retains gross zero-sum identity;
- invalid iteration counts/modes fail closed.

## What comes next

After CI closure, the next useful work is not to scale this exact-rational implementation. We should use it as the oracle for:

1. a float/full-tree implementation parity gate;
2. an external-sampling multi-street candidate with deterministic RNG/checkpoint lineage;
3. equal-compute comparison after the Ryzen F4 evidence narrows the production architecture.

This preserves the project rule: **build the exact small truth first, then optimize against it.**
