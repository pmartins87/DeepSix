# OpenHoldem6Plus — provenance and import policy

## Purpose

`OpenHoldem6Plus/` is an exclusive Short Deck runtime for DeepSix. It is not
intended to remain a general-purpose Texas Hold'em build.

## Upstream lineage

The historical OpenHoldem source referenced by the current project points to:

- repository: `OpenHoldem/openholdembot`
- upstream default branch: `master`
- pinned reference commit for the clean upstream baseline:
  `5d2bb3afec7922aab1b72aef1b23265ff6ea1b13`
- commit date: 2021-12-25
- release-note lineage around OpenHoldem 14.0.2.x

The working OpenHoldem used by the existing AOF project contains later/local
adaptations. Those adaptations must **not** be silently treated as pristine
upstream. When we import the actual working tree used on the user's machine,
we will record its own snapshot/hash separately.

## License preservation

OpenHoldem source files already carry GPL v3 notices. Any imported source must
retain its original copyright/license headers. DeepSix-specific files must not
remove or obscure those notices.

## Import policy

Before a large source import:

1. identify the exact working tree/snapshot that is operationally authoritative;
2. archive or hash that snapshot;
3. record upstream base and local modifications separately;
4. import into `OpenHoldem6Plus/`;
5. rename binary, logs/config namespaces and build outputs so they cannot collide
   with existing OpenHoldem installations;
6. keep the first build observation/replay-only;
7. do not enable automatic actions until the replay-equivalence gate passes.

## Architectural boundary

Legacy OpenHoldem may keep its native card representation while scraping.
At the strategic boundary it must decode to rank/suit, reject ranks 2..5 and
map valid 6..A cards to compact DeepSix ids 0..35.

Legacy `Hand_EVAL_N`, `prwin`, 1326/2652 tables and Texas-Hold'em blind
semantics are not authoritative for DeepSix.
