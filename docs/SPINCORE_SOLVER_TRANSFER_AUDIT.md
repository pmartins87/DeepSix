# SpinCore → DeepSix solver-transfer audit

Date: 2026-08-26  
SpinCore source head audited: `30aab24558750fee1f5da0821ecd6fe8a8c8db2d`  
DeepSix target: autonomous 6+ / Short Deck cash AI inside the offline simulator, with versioned GGPoker-reference economy.

## Executive decision

SpinCore is a high-value engineering source for DeepSix, but not a strategy template.

The two projects share the hard systems problem—large imperfect-information poker trees under a finite Ryzen CPU budget—while differing materially in deck, player count, utility and game geometry.  The correct transfer rule is therefore:

> **reuse solver engineering principles and benchmark methodology; re-prove every poker-semantic assumption inside DeepSix.**

This audit intentionally does not declare Deep CFR, external sampling, any neural representation or any action width to be the DeepSix winner.  SpinCore itself still carries exact-reproducibility debt and its R7.5 representation successor was not admitted; copying its current production candidate would therefore import unresolved evidence rather than knowledge.

## What SpinCore teaches us with strong transfer value

### 1. Exact game state must remain exact

SpinCore R7.5 explicitly separates authoritative cards/chips/actions/rules from lossy neural observation.  DeepSix adopts the same boundary permanently:

- exact 36-card state drives legality, chance, side pots, showdown and settlement;
- exact stack/pot/to-call/raise history remains available to replay/audit;
- state/action compression may occur at the policy/trainer boundary only;
- a bucket or embedding must never become the authoritative poker state.

DeepSix already follows this in the Core/Simulator.  F5/F6 must preserve it.

### 2. Quotient only true invariances

SpinCore found direct evidence that a legacy 184-flop mapping split suit-isomorphic states.  Its replacement work therefore distinguishes exact suit symmetry from heuristic poker similarity.

DeepSix already canonicalizes only exact invariances: hole order, simultaneous flop order, global suit renaming and valid chair relabeling.  Turn/river order, sizing and strategically distinct histories remain distinct.  Any future neural abstraction will be benchmarked against an unabstracted/exact oracle wherever tractable.

### 3. Rich semantic observations are cheaper than a needlessly wide action tree

SpinCore's R7.5 precommit contains a useful asymmetry:

- preserve exact/continuous geometry and useful deterministic poker semantics in the observation;
- make every extra aggressive branch justify its CPU/tree cost.

DeepSix adopts the same principle, adapted to Short Deck.  Exact pot, stack, SPR, amount-to-call, action history, blockers, nutness and board transitions should remain available even if some are also bucketized.  Action widths are promoted only by measured strategic gain per wall-clock/node/memory.

### 4. Full-chance CFR is a reference, not automatically the production traversal

SpinCore's Deep CFR stack uses external sampling because full-tree enumeration becomes too expensive as the game grows.  DeepSix therefore adds external-sampling MCCFR as an F4 candidate under the **same exact river game and exact best-response oracle** as its vanilla CFR and RM+ baselines.

This is a candidate, not a winner.  The benchmark explicitly records that one full-chance iteration and one sampled iteration are different amounts of work.  Promotion requires exploitability versus wall-clock, followed by equal-wall-clock repetition on the target workstation.

### 5. Parallelism must not change stochastic semantics

SpinCore's most transferable production lesson is its treatment of RNG/model lineages:

- one stochastic/model lineage is serial;
- independent lineages/seeds may run concurrently;
- worker completion order must not silently redefine sample/reservoir order;
- a crashed iteration is retried from its durable parent checkpoint instead of being silently advanced.

DeepSix now has solver-agnostic `TrainingStreamScheduler` infrastructure implementing that contract for 2..6-player streams.  It deliberately does not derive solver root seeds or own model RNG state; those semantics remain solver-specific until F4 selects a family.

### 6. Durable checkpoint lineage is part of the algorithm

SpinCore requires fsync/atomic replacement, SHA-256 receipts and parent checkpoint identity before a scheduler advances.  This prevents a long training stream from accidentally splicing iteration N+1 onto the wrong N checkpoint after a crash or manual file mix-up.

DeepSix now carries the same architecture-neutral guarantee in `deepsix_trainer.stream_scheduler`.

### 7. Zero-regret bootstrap matters if Deep CFR is tested

SpinCore's `NeuralAdvantagePolicy` correctly notes that a random untrained neural network is not the initial CFR regret table.  Initial cumulative regret is zero, hence initial behavior must be uniform over legal actions until a fitted advantage model exists.

If Deep CFR enters a later DeepSix architecture tournament, this becomes a mandatory gate.  It is not needed by the current tabular CFR/RM+/MCCFR candidates.

## What does NOT transfer directly

| SpinCore property | DeepSix decision |
|---|---|
| 52-card Hold'em card representation | Reject; DeepSix is 36-card Short Deck |
| 169 preflop classes | Reject; DeepSix has 81 exact Short Deck classes / 630 combos |
| 184/1755 Hold'em flop classes | Do not copy; Short Deck board distribution and blockers differ |
| fixed 3-seat solver state | Reject; DeepSix target is 2..6 players |
| tournament blind ladder | Reject |
| ICM payout-delta utility | Reject; DeepSix uses cash utility with house deductions |
| zero-sum tournament terminal objective | Reject for full cash training; DeepSix net utility sums to `-(rake+BBJ)` |
| SpinCore 6-slot or 10-slot action contract | Candidate ideas only; DeepSix sizes are independently benchmarked |
| exact SpinCore RNG/root formula | Do not copy; DeepSix freezes its own seed semantics |
| SpinCore neural V1 as production representation | Reject as inherited truth; SpinCore itself records representation debt |
| current SpinCore architecture winner | None to copy; current status does not establish a universal winner |

## Important negative evidence from SpinCore

The most valuable transfer is not merely code that passed.  Two unresolved/failing lines should directly shape DeepSix governance:

1. SpinCore records an exact fresh-process reproducibility debt in R7.3.  Therefore DeepSix will require restart/fresh-process equivalence before a long solver lineage is certified.
2. R7.5's V1Plus representation reset closed without admitting the proposed successor; V1 remained a fallback.  Therefore DeepSix will not assume that a more sophisticated representation is better merely because it is richer.

The general lesson is to benchmark architecture hypotheses under frozen evidence before spending weeks of CPU.

## DeepSix solver tournament after this audit

### Tier 0 — exact/reference baselines

- synchronous full-chance vanilla CFR;
- synchronous RM+;
- dynamic exact best response on tractable river games.

These remain mathematical references even if too slow for production.

### Tier 1 — sampling candidate now admitted to F4 testing

- external-sampling MCCFR with deterministic seed;
- same Short Deck evaluator/ranges/action tree as the full-chance baselines;
- exact exploitability measured by the same dynamic BR;
- no neural approximation and no reservoir yet.

This isolates the value of **sampling itself** before introducing neural approximation error.

### Tier 2 — only if Tier 1 justifies it

Potential future candidates:

- Deep CFR / neural external sampling;
- outcome-sampling MCCFR;
- hybrid tabular-neural value/regret approximation;
- subgame/local refinement on top of a blueprint.

Deep CFR will not be imported simply because SpinCore uses it.  It must beat simpler candidates on error per CPU-hour, memory and held-out generalization.

## Promotion gates for a DeepSix solver family

Before F5 multi-street begins, a candidate family must satisfy all of the following:

1. exact-gated correctness on tractable games;
2. deterministic same-seed repetition;
3. split-run/resume equivalence where the algorithm promises exact resumability;
4. held-out board/range/stack evaluation;
5. exploitability/error reported against the same oracle for compared candidates;
6. wall-clock and memory measured on the target workstation;
7. close candidates repeated under equal wall-clock budgets;
8. no architecture chosen solely by iteration count;
9. action/state compression judged independently where possible;
10. checkpoint/restart lineage protected by SHA-256 and parent identity.

## Parallel training rule frozen for DeepSix

The default production rule is now:

```text
within one (experiment, solver family, player count, algorithm seed)
    -> serial stochastic/model lineage

across independent keys
    -> parallel execution allowed
```

If a future solver proves that roots within one lineage can be parallelized without changing its defined stochastic semantics, that is a new algorithm/profile version and must be regression-proven.  Worker count is never allowed to silently change the meaning of a frozen run.

## Implementation landed with this audit

- `deepsix_trainer/stream_scheduler.py`
  - explicit independent stream identity;
  - one active iteration lease per stream;
  - durable checkpoint receipt required before progress;
  - parent SHA-256 lineage;
  - crash retry without silent advance;
  - atomic scheduler checkpoint save/load;
  - 2..6-player-aware stream identity.

- `deepsix_trainer/river_external_sampling.py`
  - deterministic-seed external-sampling MCCFR candidate;
  - one sampled compatible chance deal per iteration;
  - both traversers use one frozen pre-update strategy snapshot;
  - separate own-reach average-strategy sampling;
  - exact DeepSix river policy output.

- `tools/benchmark_river_solver_algorithms.py` v2
  - vanilla CFR vs RM+ vs external-sampling MCCFR;
  - same exact dynamic BR oracle;
  - explicit warning that iteration counts are not equal work;
  - wall-clock-first promotion semantics.

## Next research sequence

1. Gate the newly admitted external-sampling candidate in CI.
2. Run Ryzen Benchmark Suite engineering profile v3 with the new three-way solver comparison.
3. If external sampling is near/at the Pareto frontier, add equal-wall-clock repeated seeds before considering neural approximation.
4. Use the winning traversal family to design F5's first HU multi-street representation.
5. Only then test whether Deep CFR-style reservoirs/networks buy enough quality per CPU-hour to justify their extra approximation and reproducibility surface.

This ordering deliberately extracts the reusable knowledge from SpinCore while preventing tournament-specific or unresolved SpinCore choices from becoming accidental DeepSix dogma.
