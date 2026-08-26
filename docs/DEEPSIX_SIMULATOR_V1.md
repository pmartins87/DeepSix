# DeepSix Simulator v1

Status: **critical-path implementation**  
Rules profile: `deepsix_shortdeck_sim_rules_2026-08-25_v1`  
Economy profile: `ggpoker_shortdeck_cash_2026-08-16_v1`  
Settlement profile: `deepsix_sim_settlement_2026-08-25_v1`

## Purpose

The DeepSix target is an autonomous Short Deck cash-game AI running inside our own simulator. `deepsix_simulator` is therefore the first execution boundary on the critical path that does not depend on OpenHoldem, scraping, tablemaps or a live poker client.

The simulator reuses the gated Core instead of reimplementing poker semantics:

```text
seeded 36-card deck
 -> versioned rules profile
 -> deepsix_core.hand / betting
 -> seat-local observation
 -> legal action only
 -> board chance transitions
 -> side-pot/showdown resolution
 -> GGPoker-reference rake + BBJ
 -> deterministic integer settlement
 -> post-hand stacks
```

## v1 simulator rules

The following are explicit simulation conventions. They are versioned so later evidence can produce v2 without rewriting historical runs.

- the published stake denomination is mapped to one ante unit;
- every dealt player posts one ante;
- the Button posts two antes total;
- action order is clockwise from the first dealt seat left of the Dealer through the Dealer;
- preflop full-raise increment starts at two antes;
- postflop minimum bet starts at two antes;
- short all-ins are allowed;
- prior raise rights reopen after cumulative short increases reach one full-raise increment;
- odd chips in a tied pot layer go clockwise beginning with the first winner left of the Dealer.

These choices make the simulator complete and deterministic. They are not presented as proof of undocumented live-client edge cases.

## Economy boundary

GGPoker is the economic reference, not the execution platform.

The current profile uses:

- 5% rake;
- published player-count caps for each frozen stake;
- published default buy-in per stake;
- no invented preflop/small-pot exemption;
- optional Short Deck BBJ contribution of one ante at the 100-ante threshold.

The generic Core keeps exact `Fraction` rake before rounding. Simulator settlement v1 rounds rake **down to the integer monetary unit**. This is a simulator accounting choice, not a claim about client-side rounding.

House deductions are calculated on the aggregate gross pot. Because operator-specific side-pot rake attribution is not part of the target, v1 allocates the final integer house deduction pro-rata across gross winners using a deterministic largest-remainder rule. This preserves exactly:

```text
sum(post_hand_player_stacks)
= sum(pre_hand_player_stacks) - rake - BBJ
```

## Environment API

`SimulatedHand.start(...)` creates one seeded hand with 2..6 dealt players and arbitrary positive stacks.

Each player receives a `SimulatorObservation` containing only:

- its own two hole cards;
- public board;
- public stacks/contributions/fold/all-in state;
- public action history;
- current actor;
- legal actions only when that seat is actually to act.

Opponent hole cards are not exposed by the observation contract.

`SimulatedHand.act(seat, SimulatorAction(...))` delegates legality to the Core and rejects out-of-turn or illegal actions.

When a betting round closes, chance transitions are automatic. If everybody remaining is all-in, the environment runs flop/turn/river automatically until showdown.

`play_to_terminal()` accepts one policy callable per seat and runs a full closed-loop hand.

## Session shell

`DeepSixTable` carries:

- fixed physical seats;
- bankroll stacks;
- Dealer rotation;
- current stake/economy profile;
- hand index.

It starts each hand from the surviving funded seats, commits the terminal settlement back into session stacks and rotates the Dealer clockwise.

This is deliberately smaller than the final simulator. Rebuy/top-up, join/leave, batch workers and long-session logging remain later F2 gates.

## Baseline policies

Two deterministic policies exist only for validation/integration:

- `check_call_policy`;
- `min_raise_else_check_call_policy`.

They are not poker strategy candidates. Their purpose is to force the environment through legal passive/aggressive trajectories while testing conservation and replay.

## Current gates

The v1 test suite covers:

- versioned rule conversion from stake to ante/min-raise units;
- deterministic deal identity for equal seeds;
- seat-local hidden-information boundary;
- out-of-turn rejection;
- full preflop/flop/turn/river passive checkdown;
- exact 5% rake before rounding and integer simulator rounding;
- automatic all-in runout;
- player-count rake cap;
- BBJ deduction on/off;
- post-hand chip conservation after house deductions;
- published default buy-in use;
- Dealer rotation.

## Still required before F2 PASS

- canonical simulator hand/event history format;
- replay from `seed + starting stacks + actions` with hash equality;
- explicit reset/step boundary suitable for trainer workers;
- join/leave/rebuy/top-up session semantics;
- split/side-pot adversarial fixtures, including odd-chip cases;
- randomized property/fuzz testing across 2..6 players and asymmetric stacks;
- batch/multiprocess API after profiling;
- long self-play soak with millions of hands and zero accounting/state divergence;
- stable observation schema/version and serializer.

Only after those gates should F2 move from `PARTIAL` to `PASS`.
