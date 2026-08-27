# F5 chance-sampled HU CFR foundation v1

Date: 2026-08-27  
Status: **PREPARED / NOT YET PROMOTED**

## Purpose

This layer isolates the cost/variance effect of sampling chance while leaving player actions fully enumerated.

Relative to the full-tree float64 CFR baseline:

- one private deal is sampled at the root from its exact rational distribution;
- one public chance outcome is sampled at each chance node;
- all player actions at every visited decision node are still enumerated;
- infoset identity, action abstraction, Core betting transitions, board transitions and gross utility are unchanged;
- the trainer is seeded and split-training deterministic.

This is deliberately **not yet external-sampling MCCFR**. Opponent-action sampling is the next axis. Keeping the axes separate lets us tell whether error came from binary64 arithmetic, chance sampling or opponent sampling.

## Exact categorical sampling

`sample_fraction_index()` accepts an exact `Fraction` distribution, converts it to integer weights using denominator LCM and samples with Python integer `randrange()`.

That implementation is correctness-first. A large production trainer may replace it with a faster cumulative/alias sampler only after distribution parity and wall-clock benchmarks.

## Why the chance-reach multiplier disappears

The full-tree solver explicitly sums each regret/average-strategy update over private-deal and board-chance probability.

When those outcomes are sampled from their true distributions, the update on the sampled path is already an unbiased estimator of that weighted sum. Therefore the sampled traversal uses player reach only:

```text
full tree:
  delta_regret = chance_reach * opponent_reach * (action_value - node_value)

chance sampled:
  E[delta_regret_sample] = full-tree delta_regret
  delta_regret_sample = opponent_reach * (action_value_sample - node_value_sample)
```

The same reasoning applies to average-strategy mass with own reach.

## Determinism contract

The semantic snapshot includes:

- algorithm seed;
- iteration count;
- private-deal sample count;
- public chance sample count;
- terminal visit count;
- SHA-256 digest of the PRNG state;
- all node regrets and strategy masses encoded with `float.hex()`.

Thus:

```text
train(6)
```

must be identical to:

```text
train(2)
train(4)
```

for the same initial algorithm seed and unchanged game semantics.

## CI gates prepared

- exact rational categorical sampler respects weighted support;
- same seed gives identical state and policy fingerprint;
- split training preserves PRNG/solver identity;
- exactly one root private deal is sampled per iteration;
- public chance and terminal visit counters are non-zero;
- frozen sampled policy can be exact-normalized and evaluated by the strict gross zero-sum reference game;
- bad seeds/iteration counts fail closed.

## Promotion rule

This layer is not promoted as the production traversal merely because it is faster. We still need:

1. float64 full-tree parity green;
2. statistical error/convergence comparison against full-tree CFR on controlled F5 games;
3. wall-clock gain measurement;
4. then external opponent-action sampling as a separate candidate;
5. eventually equal-CPU-hour comparisons on the Ryzen.
