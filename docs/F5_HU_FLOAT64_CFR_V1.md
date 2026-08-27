# F5 float64 CFR/RM+ numeric parity candidate v1

Date: 2026-08-27  
Status: **VALIDATION CANDIDATE — EXACT FRACTION SOLVER REMAINS ORACLE**

## Purpose

The first F5 solver uses exact `Fraction` arithmetic across private-deal reach, chance, regrets and average-strategy mass. That is the right correctness oracle, but it is intentionally too expensive to be a production trainer.

`deepsix_trainer/hu_multistreet_float_cfr.py` mirrors the exact solver with IEEE-754 binary64 arithmetic while preserving the same:

- `HuReferenceMicrogame`;
- canonical infoset fingerprint;
- action support;
- full private-deal enumeration;
- full board-chance enumeration;
- synchronous iteration boundary;
- CFR versus Regret-Matching+ choice;
- gross zero-sum training objective.

No sampling is introduced in this layer. Numeric representation and sampling are separate experimental axes.

## Why this layer exists

We want to answer two different questions independently:

```text
Does float64 reproduce the exact small-game update closely enough?
Does sampling buy enough CPU-hour efficiency for the error it introduces?
```

Combining both changes at once would make a disagreement impossible to diagnose.

## Fail-closed rules

The float solver rejects:

- non-finite cumulative regret;
- non-finite strategy mass;
- malformed action support;
- invalid iteration counts;
- invalid solver mode;
- probability rows outside a tight normalization tolerance.

RM+ still clips cumulative regret at zero.

## Exact-evaluation adapter

`FloatTabularPolicy.to_exact_policy()` converts every binary64 probability using `Fraction.from_float()` and then renormalizes the row in rational arithmetic. The strict `HuReferenceMicrogame.evaluate()` can therefore evaluate the frozen float policy without weakening its exact probability contract.

This adapter does **not** claim the float training process is exact. It only provides an exact representation of the policy that binary64 training produced.

## Parity gate

`exact_float_max_errors()` compares aligned exact/float solver states after the same number of synchronous iterations and refuses mismatched infoset or action supports.

The CI gate checks one full F5 iteration for:

- identical infoset support;
- identical action support;
- max absolute regret error <= `1e-12`;
- max absolute cumulative strategy-mass error <= `1e-12`;
- max absolute average-policy error <= `1e-12`;
- deterministic float snapshots/fingerprints;
- RM+ non-negative regret invariant;
- exact rational re-normalization of the frozen float policy;
- exact gross zero-sum evaluation through the reference game.

## Benchmark tool

Run:

```text
python tools/benchmark_hu_multistreet_numeric.py --iterations 1 --output numeric.json
```

The artifact records exact and float wall-clock time, infoset counts, speedup, three max-error metrics and policy fingerprints.

The result is evidence for numeric representation only. It must not be interpreted as evidence that full-tree float CFR is the final production architecture.

## Next gate

After float64 parity is green, introduce a sampled traversal as a separate implementation and compare its statistical estimates against the exact/full-tree baselines on the same F5 game. Only then should the project promote sampling into larger HU training.
