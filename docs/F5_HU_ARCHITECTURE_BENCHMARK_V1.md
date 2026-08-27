# F5 HU solver architecture benchmark v1

Date: 2026-08-27  
Status: **ENGINEERING HARNESS — requires exact BR gate before strategic conclusions**

## Question

F5 now has several trainer families that differ on separate axes:

```text
exact Fraction full-tree CFR/RM+
        ↓ numeric approximation only
float64 full-tree CFR/RM+
        ↓ chance sampling only
float64 chance-sampled CFR
        ↓ opponent-action sampling too
float64 external-sampling MCCFR
```

The project must compare them under one game and one independent quality oracle rather than infer strength from speed alone.

`tools/benchmark_hu_multistreet_architectures.py` trains these candidates on the same tiny F5 HU game and freezes each average policy before evaluating it with `exploitability_exact()`.

## Default run

```text
python tools/benchmark_hu_multistreet_architectures.py \
  --exact-iterations 1 \
  --float-iterations 1 \
  --sampled-iterations 50 \
  --external-iterations 50 \
  --seeds 17,29,43 \
  --output f5_architecture.json
```

For a slightly richer imperfect-information fixture, add:

```text
--multi-private
```

That changes each player from one private hand to two and creates multiple compatible joint private worlds. It is more representative but also materially more expensive for the exact full-tree/BR oracles.

## Recorded evidence

Every row records:

- solver family;
- regret mode;
- iteration budget;
- algorithm seed for sampled candidates;
- training wall-clock;
- exact-BR oracle wall-clock;
- visited/allocated infosets;
- policy SHA-256;
- exact exploitability as numerator/denominator plus float view;
- candidate-specific sampling/work counters.

The artifact also records the exact uniform-policy exploitability baseline.

## Interpretation

Different algorithms do different amounts of work per iteration. Therefore iteration count is not the final comparison currency.

The first run answers whether every candidate moves in the expected direction and exposes approximate cost scales. The later Ryzen decision should compare:

```text
exploitability reduction / wall-clock
exploitability reduction / nodes visited
memory / reached infoset
seed variance at fixed CPU budget
checkpoint/resume stability
```

Equal-iteration results are diagnostic; equal-CPU-hour results are the production decision.

## Promotion rule

No candidate wins because it is faster in the tiny game. A production promotion requires:

1. exact BR correctness green;
2. full-tree float parity green;
3. sampled candidate deterministic/restart gates green;
4. exploitability improving across multiple seeds/budgets;
5. advantage surviving wall-clock normalization;
6. evidence on more than one board/range/stack texture;
7. Ryzen measurements before long training.

This harness is the bridge from the source-informed SpinCore sampling hypothesis to a DeepSix-specific empirical architecture choice.
