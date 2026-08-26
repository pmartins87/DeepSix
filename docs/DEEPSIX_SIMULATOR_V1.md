# DeepSix Simulator v1

Status: **critical-path implementation / F2 PARTIAL+**  
Rules profile: `deepsix_shortdeck_sim_rules_2026-08-25_v1`  
Economy profile: `ggpoker_shortdeck_cash_2026-08-16_v1`  
Settlement profile: `deepsix_sim_settlement_2026-08-25_v1`  
Utility profile: `deepsix_sim_utility_2026-08-25_v1`  
Soak/checkpoint schema: `SIMULATOR_SOAK_SCHEMA_VERSION = 1`

## Purpose

The primary DeepSix product is an autonomous Short Deck cash-game AI running inside our own simulator. `deepsix_simulator` is the first execution boundary on the critical path and has no dependency on OpenHoldem, scraping, tablemaps or a live poker client.

```text
seeded 36-card deck
 -> versioned rules profile
 -> Core hand/betting semantics
 -> seat-local observation
 -> legal action only
 -> chance transitions
 -> side-pot/showdown
 -> GGPoker-reference rake + optional BBJ
 -> deterministic integer settlement
 -> exact per-seat utility
 -> persistent session stacks
 -> transcript/snapshot replay
 -> deterministic sharded soak evidence
```

## Rules v1

The following are explicit, versioned simulator conventions rather than claims about undocumented client behavior:

- published stake denomination maps to one ante unit;
- every dealt player posts one ante;
- Button posts two antes total;
- action order is clockwise from first dealt seat left of Dealer through Dealer;
- preflop full-raise increment starts at two antes;
- postflop minimum bet starts at two antes;
- short all-ins are allowed;
- prior raise rights reopen when cumulative short increases reach one full-raise increment;
- odd chips in a tied layer go clockwise beginning with first tied winner left of Dealer.

## Economy and settlement

GGPoker is the economic reference, not the execution platform. The frozen profile uses 5% rake, the published player-count caps/default buy-ins, no invented preflop/small-pot exemption, and an optional Short Deck BBJ contribution of one ante at the 100-ante threshold.

The generic Core keeps exact `Fraction` rake. Settlement v1 floors that value to the integer simulator money unit. Aggregate rake+BBJ is allocated pro-rata across gross winners with deterministic largest remainder. This intentionally avoids inventing operator-specific side-pot rake attribution.

The accounting invariant is:

```text
sum(post_hand_stacks)
= sum(pre_hand_stacks) - rounded_rake - BBJ
```

## Utility boundary

`deepsix_simulator.utility` deliberately exports both:

```text
gross_poker_delta = gross_award - contribution
net_cash_delta    = net_award   - contribution
```

Therefore:

```text
sum(gross_poker_delta) = 0
sum(net_cash_delta)    = -(rake + BBJ)
```

The trainer cannot silently treat the raked cash game as zero-sum. Gross utility remains useful for mathematical subgame/oracle work; net utility is the actual simulator cash result. Both are exact integers plus `Fraction` normalization in antes.

## Environment API

`SimulatedHand.start(...)` creates one seeded hand with 2..6 players and arbitrary positive starting stacks. Each `SimulatorObservation` contains only the acting seat's private cards plus public information. Opponent hole cards never appear in the agent observation contract.

`SimulatedHand.act()` rejects out-of-turn/illegal actions through the Core. Board transitions are automatic. All-in/dry betting automatically runs out the remaining board. `play_to_terminal()` runs a complete closed-loop hand from a map of seat-local policy callables.

`DeepSixEnv` provides the stable trainer-worker boundary:

- `reset(seed)`;
- `observe(seat)`;
- `current_observation()`;
- `legal_actions(seat)`;
- `step(action)` for exactly one decision.

Observation schema v1 has canonical JSON and SHA-256 fingerprints.

## Replay and crash recovery

`SimulatorHandTranscript` schema v1 stores post-hand audit evidence:

- seed;
- starting stacks;
- Dealer;
- public action sequence;
- final board;
- private-deal SHA-256;
- settlement SHA-256.

`replay_transcript()` regenerates the hidden deal from the seed and requires actor, board, hidden-deal digest and settlement digest to agree.

`SimulatorTableSnapshot` schema v1 captures between-hand session state:

- stake;
- seats;
- stacks including busted zero stacks;
- Dealer;
- hand index;
- rules/economy versions;
- BBJ mode.

A restored table must round-trip to the same canonical snapshot before it is accepted. The continuation gate compares future transcript fingerprints/final stacks against an uninterrupted session.

## Session runner

`DeepSixTable` persists bankrolls and Dealer across hands. `run_seeded_session()` executes an explicit deterministic seed schedule and records per-hand transcript fingerprints, decisions, gross pot, rake and BBJ plus final stacks and a canonical session fingerprint.

The persistent session runner remains intentionally single-process. Process-level parallelism is a separate throughput decision, not part of the poker semantics.

## Long-soak harness

`tools/run_simulator_soak.py` is the crash-safe correctness harness for very long simulator validation. Soak hands are independent by design, so a million-hand correctness run cannot terminate merely because a persistent cash bankroll has been depleted by rake or because only one funded seat remains.

`SimulatorSoakPlan` freezes:

- global hand count and base seed;
- stake;
- 2..6-player mix;
- asymmetric stack range in antes;
- BBJ mode;
- replay sampling cadence;
- shard count/index.

Global hand `g` has deterministic seed `seed_base + g`. Shard `s` of `N` owns `s, s+N, s+2N, ...`. The hand id is derived from the **global hand index only**, so repartitioning the same schedule across another worker topology leaves deal, actions, settlement and transcript fingerprint unchanged.

`SimulatorSoakCheckpoint` stores only deterministic semantic counters: completed ordinal, decisions, gross pot, rake, BBJ, replay count, zero-decision hands and terminal-board histogram. It has canonical JSON and SHA-256 identity.

Checkpoint writes are atomic (`temp -> flush -> fsync -> os.replace`). On an exception the harness persists the last fully completed checkpoint plus `failure.json` containing the exact global index, seed and error. `--resume` refuses a checkpoint whose frozen plan differs from the requested run.

Every soak hand independently verifies:

```text
sum(gross_awards) = gross_pot
sum(net_awards)   = gross_pot - house_deductions
sum(final_stacks) = sum(starting_stacks) - house_deductions
```

It also checks terminal board cardinality, card uniqueness and periodically performs full transcript replay. The random stress policy samples only legal `CHECK/CALL/FOLD/min-raise/max-raise` candidates.

Example one-million-hand single-shard run:

```text
python tools/run_simulator_soak.py \
  --hands 1000000 \
  --players 2,3,4,5,6 \
  --replay-every 1000 \
  --checkpoint-every 1000 \
  --run-dir soak_runs/one_million
```

The command above is a run recipe, not evidence that the one-million-hand soak has already completed.

## Validation already implemented

Current simulator gates include:

- deterministic equal-seed deal;
- private-information isolation;
- out-of-turn fail-closed;
- passive checkdown through all streets;
- all-in auto-runout;
- exact rake/cap/BBJ accounting;
- odd-chip split;
- main/side-pot winner separation;
- canonical transcript roundtrip and exact replay;
- seed/actor tamper rejection;
- reset/observe/step API;
- randomized 2..6-player trajectories with asymmetric stacks and legal random actions;
- session-level bankroll conservation;
- exact gross-vs-net utility identities;
- between-hand snapshot/restart equivalence;
- deterministic disjoint soak sharding;
- shard-topology-invariant global hand identity;
- crash-safe soak checkpoint/failure artifacts;
- CI smoke execution of the soak harness;
- simulator throughput benchmark wiring.

Two important fixture errors were exposed by earlier gates and corrected instead of weakening the engine:

1. folds can legitimately terminate on flop/turn, so a terminal board can contain 3 or 4 cards;
2. `67` on `AKQ98` forms the special Short Deck `A6789` straight, so that fixture legitimately beat trips.

## Performance benchmark and Ryzen suite

`tools/benchmark_simulator_throughput.py` measures the pure single-process environment at 2/4/6 players using independent deterministic check/call hands. It reports hands/s, decisions/s, mean decisions/hand, gross pot and rake.

The benchmark is now part of **Ryzen Benchmark Suite v3**, alongside action abstraction, scalable multi-size raise, state-abstraction battery/convergence and CFR-vs-RM+ solver comparisons. The analyzer verifies every JSON/log SHA-256 before using the evidence and keeps environment throughput separate from strategy-quality metrics.

Primary engineering command:

```text
python tools/run_ryzen_benchmark_suite.py --profile engineering
```

Then:

```text
python tools/analyze_ryzen_benchmark_suite.py benchmark_runs/<RUN> --output analysis.json
```

CI proves wiring only. Actual target-machine throughput and strategy promotion decisions require the real engineering run.

## Still required before F2 PASS

- larger fuzz beyond the short CI battery;
- adversarial generated short-all-in/reopen sequences;
- long soak with zero state/accounting/replay divergence;
- real hands/s, decisions/s and peak-memory measurements on the target workstation;
- multiprocess runner only if profiling shows useful scaling;
- optional rebuy/top-up/join/leave semantics if long fixed-player-count sessions require them;
- transcript retention policy that samples normal hands and preserves all errors/outliers without excessive I/O.

F2 becomes `PASS` only after those stability/performance gates close.
