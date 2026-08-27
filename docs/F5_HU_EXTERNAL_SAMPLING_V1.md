# F5 HU external-sampling MCCFR v1

Date: 2026-08-27  
Status: **ARCHITECTURE CANDIDATE — PENDING MULTI-STREET CI/CONVERGENCE GATES**

## Provenance and scope

DeepSix already has a gated external-sampling implementation in the exact river laboratory. That implementation was informed by a useful SpinCore pattern: enumerate the traverser's actions, sample external actions, and collect behavioral average strategy with a separate own-reach traversal.

`deepsix_trainer/hu_multistreet_external_sampling.py` ports that **algorithmic structure only** into the F5 multi-street Short Deck game.

It does not import SpinCore's tournament state, ICM utility, 52-card representation, neural targets, reservoirs, action width or architecture choice.

## One iteration

One iteration is deliberately synchronous:

```text
sample one exact private deal
        |
        +-> regret traversal, traverser 0
        +-> regret traversal, traverser 1
        +-> average-strategy collector, target 0
        +-> average-strategy collector, target 1
        |
commit both regret deltas
```

All four traversals see the same regret table.

### Regret traversal

At a traverser's infoset:

- enumerate every abstract action;
- recursively estimate each action value;
- update sampled counterfactual regret by `v(a) - v(I)`.

At an opponent infoset:

- sample one action from the current behavioral strategy.

At a chance node:

- sample one legal board reveal from the exact `Fraction` distribution.

The private deal is also sampled from the exact rational joint-deal distribution.

### Average strategy

The average collector follows the own-reach construction already used in the river candidate:

- when the target player acts, add the current behavioral strategy unweighted and sample one target action;
- when the opponent acts, enumerate opponent actions;
- sample chance from the true chance distribution.

Target-player action sampling makes infoset visitation proportional to own reach. Enumerating opponent actions prevents opponent reach from incorrectly weighting the target player's behavioral average.

## Numeric sampling contract

Private/chance distributions are sampled directly from exact rational weights.

Behavioral strategies are binary64. For sampling, every probability is converted with `Fraction.from_float()`, the row is rationally renormalized, and the exact integer categorical sampler is used. This is intentionally correctness-first; a future high-throughput alias sampler must prove distribution and convergence parity before promotion.

## Checkpoint identity

The checkpoint binds to a SHA-256 game fingerprint covering:

- F5 microgame version;
- stake;
- Dealer;
- stacks;
- fixed flop;
- BBJ flag;
- rules profile version;
- every private reach hand and exact rational weight.

It stores:

- solver/checkpoint schema versions;
- algorithm seed;
- all stochastic/work counters;
- exact Python PRNG state;
- every visited infoset;
- action support;
- regret and average-strategy accumulators using `float.hex()`.

A restored run must satisfy:

```text
train(a) -> checkpoint -> restore -> train(b)
==
train(a+b)
```

byte-semantically at the state-dictionary/checkpoint level for the same environment.

## Initial gates

The prepared tests require:

- same-seed deterministic state/policy;
- split-training equivalence;
- checkpoint/resume equivalence;
- checkpoint rejection under a changed game fingerprint;
- counter tampering rejection;
- malformed/duplicate action support rejection;
- actual sampling of private deal, public chance, opponent actions and average-target actions;
- finite regrets;
- exact normalization of the frozen average policy;
- invalid seeds/iteration counts fail closed.

## What is still missing before promotion

Determinism is necessary but insufficient. We still need a multi-street quality oracle that can judge convergence. The next high-value item is therefore an exact best-response/exploitability evaluator for the tiny F5 HU reference game.

Once that exists, full-tree CFR, float64 CFR, chance-sampled CFR and external-sampling MCCFR can be compared on the same game by:

- exploitability/error versus iterations;
- exploitability/error versus wall-clock;
- nodes visited;
- memory;
- seed variance;
- checkpoint/resume reproducibility.

Only evidence from those comparisons can promote external sampling toward the Ryzen-scale blueprint.
