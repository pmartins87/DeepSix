# DeepSix Solver Architecture Precommit v1

Date: 2026-08-26  
Status: **FROZEN BEFORE FIRST THREE-FAMILY RYZEN PROMOTION RUN**

This document freezes how DeepSix will choose the solver/traversal family for the
first multi-street blueprint.  It is deliberately written before observing the
first target-workstation comparison that includes external sampling, so later
results cannot silently redefine the success criteria around whichever method
happens to look attractive.

The target is the autonomous **offline 6+ / Short Deck cash simulator** with the
versioned GGPoker-reference economy.  No real-money client integration is part
of this gate.

## 1. No solver family is preselected

The current F4 tournament contains three directly implemented families:

1. synchronous full-chance vanilla CFR;
2. synchronous Regret-Matching+ with linear averaging;
3. deterministic-seed external-sampling MCCFR.

Dynamic Exact Best Response remains an oracle, not a production trainer.

Deep CFR is a **conditional later candidate**, not the default winner.  We will
first isolate whether sampling buys enough wall-clock/memory efficiency without
neural approximation.  Only if that result is promising do we add the extra
approximation, reservoir, optimizer and reproducibility surface of Deep CFR.
Outcome sampling, hybrid tabular/neural methods and local/subgame refinement
remain possible later candidates under the same rule.

## 2. What is allowed to transfer from SpinCore

SpinCore is an engineering reference, not a Short Deck strategy source.  The
following principles are adopted:

- exact authoritative game state remains exact;
- lossy state representation exists only at the trainer/policy boundary;
- only true symmetries may be quotiented without an empirical loss test;
- richer deterministic observations are usually cheaper than unnecessary
  action-tree branches;
- every extra action branch must justify node/memory/CPU cost;
- stochastic/model lineages are explicit;
- one lineage is serial unless a new algorithm proves different semantics;
- independent lineages may execute concurrently;
- durable checkpoint bytes and parent SHA-256 are required before progress;
- stochastic candidates need fresh-process and restart equivalence gates;
- an untrained neural advantage network cannot impersonate zero CFR regret.

The following are explicitly **not inherited**: 52-card representation, 169
preflop classes, Hold'em 184/1755 flop abstractions, tournament blind ladders,
ICM utility, three-seat assumptions, SpinCore's six/ten action slots, or its
current neural architecture.

## 3. Four experiment axes must stay separable

A solver result is meaningful only when its semantic experiment profile binds:

```text
rules/economy/settlement/utility
+ player count / stake / BBJ mode
+ stack/training distribution
+ state representation
+ action abstraction
+ solver family
+ objective (gross poker or net cash)
```

`SolverExperimentProfile` hashes exactly these strategy-relevant axes.  A change
on any one creates a new profile/policy identity.  This prevents a checkpoint
trained under one rake, action space or representation from being compared or
resumed as though it belonged to another game.

## 4. Correctness gates precede performance gates

A candidate cannot enter a long Ryzen run until it has, where applicable:

- deterministic same-seed behavior;
- exact legality and terminal utility from the DeepSix Core/Simulator;
- exact or independently audited best response on tractable games;
- split-run equivalence;
- serialized checkpoint/resume equivalence;
- fresh-process equivalence under changed `PYTHONHASHSEED`;
- checkpoint configuration fingerprinting;
- finite probabilities/regrets/values;
- no hidden-information leakage.

A faster incorrect algorithm is not a candidate.

## 5. Comparison boundaries

### 5.1 Solver-update/traversal comparison

Vanilla CFR, RM+ and external-sampling MCCFR may be compared on the same exact
river fixture because cards, ranges, action tree, utility and exact BR oracle
are fixed.

**Iteration count is not equal work.**  A full-chance iteration visits a very
different amount of tree from a sampled iteration.  Promotion therefore uses:

- exact exploitability / pot;
- measured training wall-clock;
- nodes/infosets and sampled/visited work where available;
- peak memory when the implementation becomes large enough for it to matter.

Checkpoint curves are evidence.  A final iteration number by itself is not.

### 5.2 State abstraction comparison

A compressed private representation is evaluated by expanding its learned
policy back into the **unabstracted exact game** and asking the same exact BR to
exploit it.  Compression only wins if its CPU/memory savings compensate for the
information loss on training and held-out fixtures.

### 5.3 Action abstraction comparison

Different action spaces define different games.  Their raw exploitability
numbers are therefore not directly ranked as if they shared one oracle target.
We first measure structural cost (nodes/actions/throughput), then use richer-game
cross-evaluation or held-out action-refinement experiments when needed.

## 6. Stochastic-candidate evidence

External-sampling MCCFR introduces seed variance.  One lucky seed cannot promote
it.  After the first engineering run establishes approximate cost, any sampled
candidate near the frontier must be repeated across multiple independent
algorithm seeds.

For close candidates, the follow-up is an **equal-wall-clock** experiment on the
target workstation.  The run records actual iteration/work counts achieved by
each method rather than pretending equal iterations imply equal cost.

The deterministic stream contract is:

```text
(experiment profile, solver family, player count, algorithm seed)
    -> one serial RNG/checkpoint lineage

independent keys
    -> parallel execution allowed
```

Worker count must not silently change a frozen lineage's semantics.

## 7. Utility boundary: where SpinCore diverges most from DeepSix

SpinCore can use tournament chip/ICM terminal utilities.  DeepSix cash has a
separate economic problem:

```text
sum(gross_poker_delta) = 0
sum(net_cash_delta)    = -(rake + BBJ)
```

Therefore:

- `GROSS_POKER_DELTA` is valuable for exact two-player zero-sum solver/oracle
  research;
- `NET_CASH_DELTA` is the actual economic objective of the final cash agent;
- a gross-zero-sum result may validate an algorithm but cannot by itself certify
  a rake-aware production strategy;
- the experiment profile must state the objective explicitly.

We will not silently subtract a constant rake after solving if rake depends on
pot/action path and caps.  The economic incentives must be evaluated in the
actual simulator utility.

## 8. HU proof does not become a 6-way proof

Standard exploitability/minimax guarantees used in the current river lab are
for tractable two-player zero-sum subgames.  DeepSix ultimately has:

- 3–6 strategic players;
- asymmetric stacks;
- folds and side pots;
- negative-sum player utility after house deductions.

F6 therefore needs a multiplayer evaluation protocol of its own.  Candidates
include unilateral best-response/NashConv-style diagnostics where tractable,
frozen-policy leagues, population/self-play evaluation and local exact audits.
We will not label a 6-way policy “unexploitable” using a HU metric that does not
mathematically apply.

## 9. Representation precommit for F5

The first HU multi-street representation will keep exact authoritative state and
benchmark policy-boundary encodings that preserve at minimum:

- exact/normalized stack, pot, amount-to-call, commitments and SPR;
- street and position/action order;
- exact action sizes/history or a lossless normalized equivalent;
- 81-class Short Deck preflop identity plus exact residual cards where needed;
- made-hand, draw, blocker, nutness and board-transition semantics;
- exact suit-isomorphic canonicalization rather than absolute suit names;
- explicit preflop lineage/aggression/raise depth.

Human semantic features may be redundant helpers.  They do not replace exact
facts unless ablation proves the loss harmless.

## 10. F5 entry rule

F5 (HU multi-street blueprint) may start after:

1. the three-family F4 benchmark executes on the target workstation;
2. sampled candidates near the frontier are repeated across seeds;
3. state/action candidates have enough evidence to freeze a first version;
4. checkpoint/restart semantics are proven for the selected family;
5. the chosen experiment profile is frozen and hashable;
6. the training objective is explicit.

F5 may still begin with a deliberately small tree/range/stack curriculum.  The
requirement is that its architecture is selected from evidence rather than from
SpinCore inheritance or solver fashion.

## 11. Current implication

SpinCore materially improves DeepSix by supplying mature engineering ideas and
negative lessons.  Its strongest contribution at this stage is **how to avoid
invalid long runs**, not a claim that “Deep CFR is the correct Short Deck
solver.”

The immediate DeepSix evidence question is now narrower and better:

> Does external sampling, without neural approximation, buy enough exact-error
> reduction per wall-clock/memory to displace or complement full-chance CFR/RM+
> as the traversal foundation for F5?

The Ryzen F4 tournament answers that question before we spend weeks or months on
a multi-street blueprint.
