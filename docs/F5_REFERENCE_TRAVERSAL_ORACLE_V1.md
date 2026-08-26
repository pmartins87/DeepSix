# F5 exact replay-fork traversal oracle v1

Date: 2026-08-26  
Status: **REFERENCE ORACLE / PASS when CI is green — not production traversal**

## Why this exists

The first F5 strategic-state boundary gives us an exact public node and acting
player infoset. A solver also needs a trustworthy way to ask:

> "What exact simulator state results if this action is taken from this node?"

Production CFR/MCCFR will eventually require much faster native branching and
explicit chance traversal. Implementing that first would create a large new
correctness surface. `deepsix_trainer.multistreet_reference` therefore provides
a deliberately slower reference oracle based entirely on already-gated
simulator semantics.

## Replay-fork construction

For an open decision:

1. recover every player's exact hand-start stack as
   `stack_behind + committed_total`;
2. recreate the hand from the same stake, Dealer, rules, BBJ setting and seed;
3. replay every public action through `SimulatedHand.act`;
4. require exact identity of hidden deal, authoritative `HandState`,
   decision index and strategic fingerprints;
5. only then apply the candidate action to the fork.

The source hand is never mutated.

This gives F5 an independent child-state construction path without reaching
into `_deck`, `_deck_cursor` or other simulator-private fields.

## What is proven

The oracle detects:

- actor drift;
- street drift;
- illegal replay actions;
- hidden-deal drift;
- authoritative state drift;
- public/private strategic fingerprint drift;
- chip-identity failure while recovering initial stacks.

`ReferenceTransition` binds by SHA-256:

- parent public fingerprint;
- parent private fingerprint;
- chosen action and `RAISE_TO` amount;
- child public/private fingerprints when another decision exists; or
- exact terminal settlement digest when the action ends the hand.

This makes exact transition receipts usable in future regression fixtures.

## Important scope boundary

A replay fork follows **one already-sampled seeded deal**. It is not the
production chance model and must not be confused with enumerating or sampling
the correct board/opponent distribution inside CFR.

Its role is analogous to the slow Python evaluator and exact range/reach code:

```text
slow exact/reference path
        ↓ proves
future optimized traversal path
```

Any native or sampled multi-street transition engine must reproduce this oracle
on tractable fixed-deal paths before it can be trusted with long training.

## Initial gates

Tests cover:

- exact stack recovery before and after actions;
- exact fork at an initial preflop decision;
- exact fork after a preflop -> flop transition;
- two independent action branches from one parent without source mutation;
- nonterminal transition receipt identity;
- terminal HU fold + settlement digest identity;
- illegal branch rejection.

## Next use

Once F4 selects the traversal/action family on Ryzen evidence, this oracle is
the reference for the first HU multi-street solver adapter. The production
adapter will then add explicit chance handling, selected action abstraction,
terminal utility and deterministic checkpoint/resume while being regression
checked against fixed-deal replay forks.
