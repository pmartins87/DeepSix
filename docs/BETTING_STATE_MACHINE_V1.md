# DeepSix betting-round state machine v1

Status: **reference implementation active in Core**  
Purpose: exact, replayable No-Limit betting transitions without guessing unresolved KKPoker client rules.

## Why this exists before the solver

The trainer and the future OpenHoldem6Plus runtime must agree on more than
`fold/call/raise`. They must agree on the exact price faced, the current
raise-to, whether a raise is full or short, which players still owe action,
whose raise rights are open, when a round closes and when the hand terminates.

A solver trained over the wrong betting machine would learn a different game.
For that reason this layer is deterministic, integer-valued and separately
tested before action abstraction or long training begins.

## State represented

A `BettingRoundState` contains:

- street;
- clockwise action order;
- exact stack behind and street commitment for each player;
- folded/all-in flags;
- current highest street commitment (`current_bet`);
- last full-raise increment;
- players that still owe action;
- next actor;
- per-seat marker of the price last faced in the current full-raise epoch;
- ordered `ActionEvent` history;
- round-closed and hand-ended flags;
- a versionable short-all-in reopen policy.

All monetary values here are integers. Raw OpenHoldem scraped doubles must be
converted to the configured exact table unit before entering this layer.

## Full raise

A `RAISE_TO` is a full raise when:

`new_raise_to - previous_current_bet >= last_full_raise_increment`

A full raise:

- updates `current_bet`;
- replaces `last_full_raise_increment` with the actual increment;
- reopens action for every other live player with chips behind;
- resets their full-raise-epoch markers.

The initial full-raise increment is supplied by the caller. This deliberately
avoids baking an unverified KKPoker preflop interpretation into the engine.

## Short all-in raise

If a player cannot reach the full minimum but can move the price upward, the
reference machine can allow only that player's **exact all-in raise-to**. An
arbitrary sub-minimum non-all-in sizing is illegal.

A short all-in:

- changes the price;
- does not itself reset the last full-raise increment;
- forces any still-live player below the new price to respond;
- does not automatically reset prior raise rights.

## Reopen policy is deliberately parameterized

The KKPoker client behavior after one or more short all-ins is still an item for
real-client evidence. Rather than guess, v1 supports three explicit policies:

- `NEVER`: once a player has acted in the current full-raise epoch, short
  increases do not restore raise rights;
- `ANY_INCREASE`: any later price increase restores raise rights;
- `CUMULATIVE_FULL_RAISE`: prior raise rights return only when the cumulative
  price increase faced since that player's last action reaches at least the
  previous full-raise increment.

The correct target policy must be frozen from KKPoker evidence before long
training. Until then tests exercise all branches so the unresolved rule is a
configuration choice rather than hidden control flow.

## Dry side-pot behavior

If all opponents of a player are folded or all-in, that player cannot make a
further raise: nobody can respond and no contestable side pot can be created.

If exactly one player has chips behind:

- and is below the current price, that player still owes call/fold action;
- and has already matched the current price, the betting round closes without a
  redundant check.

This prevents impossible betting branches from entering the solver tree.

## Terminality

The current layer marks the **hand** ended when at most one non-folded player
remains. Otherwise it marks the **betting round** closed when nobody still owes
an action after dry-side-pot normalization.

Full hand/street progression — flop/turn/river dealing, showdown, rake and
payout — is the next layer and will consume these closed-round states.

## Regression coverage

The current suite checks:

- KKPoker-style forced-contribution preflop examples represented as supplied
  commitments;
- limp/call/check closure;
- full-raise reopening;
- short-all-in calls and raises;
- all three reopen policies;
- cumulative short-all-in thresholds;
- exact-only sub-minimum all-in sizing;
- dry-side-pot closure;
- fold terminality;
- out-of-turn and illegal sizing rejection;
- chip conservation through transitions.

No result from this module should be treated as proof of the still-unverified
client-specific reopen policy. It proves that once the rule is frozen, the
engine can represent and test it explicitly.
