# F5 HU multi-street reference microgame v1

Date: 2026-08-26  
Status: **EXACT POSTFLOP REFERENCE GAME / F5 FOUNDATION**

## What this closes

The earlier F5 gates existed as separate correctness components: strategic-state identity, explicit action/chance branching, fixed-private chance, private reach and range-weighted chance. This microgame is the first object that connects those contracts into one exact imperfect-information evaluation tree spanning multiple betting streets.

It is intentionally small enough to audit in CI and intentionally solver-neutral.

## Game boundary

The v1 reference game uses the real simulator/Core semantics with:

- exactly two players;
- real Short Deck 36-card evaluator/rules;
- real stacks, antes and action order;
- a deterministic passive preflop line;
- one configured physical flop;
- strategic play on flop, turn and river;
- exact physical turn/river chance;
- exact terminal settlement and gross/net utility.

The fixed preflop line is part of the test-game definition. It is not a claim about optimal preflop strategy. A future full HU blueprint will make preflop strategic as well.

## Tiny action abstraction

At a decision node:

```text
if checked to:
    CHECK
    BET_MIN  (Core legal min raise-to)

if facing a bet:
    FOLD
    CALL
```

There is no re-raise in v1. This keeps the extensive form small while still connecting betting decisions across flop -> turn -> river. Every abstract action is translated back through the authoritative Core legal-action/betting state machine.

## Imperfect-information private distribution

The constructor receives one `PrivateReachVector` for each HU seat. Compatible joint private assignments are enumerated exactly after conditioning on the configured flop.

For each assignment:

```text
joint weight = reach_0(hand_0) * reach_1(hand_1)
```

Assignments colliding with the flop or each other are removed. The total is cross-checked against `compatible_joint_mass()` and normalized exactly with `Fraction`.

This means a board-blocked 90%-weight private branch can disappear completely and the remaining compatible 10% branch correctly becomes probability 1 after conditioning.

## Exact traversal

For each compatible private deal:

```text
start_hand
 -> deterministic passive preflop actions
 -> explicit configured flop
 -> decision policy
 -> exact turn chance
 -> decision policy
 -> exact river chance
 -> decision policy
 -> terminal settlement
```

At every decision the policy sees `PrivateDecisionState`, which contains one canonical public state plus only the acting player's private hand. Opponent hole cards are not part of the infoset even though the physical reference branch stores them to resolve exact chance/showdown.

Future chance for each physical branch uses the exact fixed-private oracle. Across the initial range distribution, expectation is weighted by the exact compatible private-deal probabilities.

## Utility boundary

Evaluation requires an explicit objective:

```text
GROSS_POKER_DELTA
NET_CASH_DELTA
```

Gross utility must sum exactly to zero. Net cash utility must sum exactly to the negative expected house deduction. The microgame never hides rake/BBJ by renormalizing net cash back to zero-sum.

Results are exact `Fraction` values in antes.

## Reference policies

Three solver-free policy callables exist for validation:

- `check_call_micro_policy`;
- `min_bet_call_micro_policy`;
- `uniform_micro_policy`.

They are baselines and test instruments, not strategic recommendations.

## Main regression fixture

The CI fixture uses two weighted private hands for one seat, one fixed hand for the other, a fixed flop and BBJ disabled.

The gates prove:

- joint private-deal probabilities normalize exactly;
- private assignments do not change the public flop-root fingerprint;
- the acting player's infoset remains correctly private;
- root actions are exactly Core CHECK/BET_MIN;
- passive gross expected utility is exactly zero-sum;
- passive net expected utility retains exactly the known 5% rake deduction on the fixed 4-ante pot;
- aggressive deterministic reference traversal reproduces byte/semantic equality across repeated evaluations and increases expected rake relative to the passive tree;
- malformed policy distributions fail closed;
- board-blocked private support is removed and renormalized exactly.

## What it is not

This is not the final HU solver and does not select CFR, RM+, external-sampling MCCFR or Deep CFR. It is the exact small game on which a solver implementation can now be tested before we trust larger trees.

It also does not make preflop strategic yet. The next two useful gates are:

1. add a tabular solver adapter to this exact game and compare solver families under the F4 evidence rules;
2. extend the reference game backwards to a tiny strategic preflop support after the postflop solver loop is gated.
