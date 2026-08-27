# F5 exact explicit branch state v1

Date: 2026-08-26  
Status: **REFERENCE BRANCH ENGINE / PARTIAL F5 FOUNDATION**

## Purpose

The production simulator intentionally owns a seeded shuffled deck and advances forced board chance automatically. That is the correct behavior for sessions, replay and soak, but it is not sufficient as a solver traversal primitive: a solver must be able to stop at a chance node, enumerate or sample a legal public reveal, fork multiple children from the same parent and continue each branch independently.

`deepsix_trainer.multistreet_branch.ExactBranchState` provides that boundary while keeping one authoritative rules implementation.

It does not reimplement betting, board or settlement logic:

```text
betting action  -> deepsix_core.hand.apply_hand_action
board chance    -> deepsix_core.hand.deal_next_board
terminal cash   -> deepsix_simulator.settlement.settle_terminal_hand
```

## Node types

An exact branch is always one of:

```text
DECISION  HandPhase.BETTING
CHANCE    WAITING_FLOP / WAITING_TURN / WAITING_RIVER
TERMINAL  SHOWDOWN / TERMINAL_FOLD
```

Node-type misuse fails closed. Betting actions are rejected at chance/terminal nodes; board reveals are rejected at decision/terminal nodes; settlement is rejected before terminality.

## Fixed-private scope

The branch stores one complete two-card private assignment for every dealt seat. It therefore represents a perfect-information physical branch used as a correctness oracle.

This is deliberately separate from the imperfect-information layer:

```text
private ranges / public reach
        ↓
range-weighted chance
        ↓
fixed private assignment branch
        ↓
exact action/chance transition
        ↓
terminal settlement
```

Full-range production traversal will integrate or sample private assignments above this boundary.

## Explicit chance

`chance_outcomes()` uses `enumerate_exact_board_chance()` and therefore exposes the complete exact next-board support for the fixed private assignment.

For HU preflop with four fixed hole cards this is exactly:

```text
C(32,3) = 4,960 flop outcomes
```

`apply_chance()` additionally checks the private assignment before calling the Core board transition, so a private card cannot be revealed publicly even though the generic `HandState` itself intentionally does not know hole cards.

## Immutability and branching

`ExactBranchState` is frozen. `apply_action()` and `apply_chance()` return children rather than mutating the parent. Therefore two different flop reveals can fork from the same `WAITING_FLOP` parent without contaminating each other or the source state.

## Simulator parity gate

The main regression is stronger than an isolated unit test. A seeded HU `SimulatedHand` provides one real physical private deal and one real seeded board path. An `ExactBranchState` is initialized from the same private assignment and starting stacks. Both then receive the same passive actions.

Whenever the explicit branch reaches a chance node, the regression takes the exact reveal produced by the simulator's seeded deck and feeds it into `apply_chance()`.

After every action/chance transition the authoritative raw `HandState` objects must be exactly equal. The test continues preflop -> flop -> turn -> river -> terminal and finally requires exact `SimulatorSettlement` equality.

This proves that the solver branch boundary is a different traversal mechanism over the same game semantics rather than a second game implementation.

## Gates

Tests cover:

- initial branch/raw simulator state equality;
- action parity across every street;
- explicit chance parity across flop/turn/river;
- exact terminal settlement parity;
- all 4,960 HU preflop flop outcomes and exact probability sum 1;
- two distinct chance children from one immutable parent;
- private/public card collision rejection;
- decision/chance/terminal node guards;
- `from_simulated_hand()` exact state/private-assignment preservation.

## Next step

The strategic-state canonicalizer currently accepts `SimulatedHand`. The next F5 bridge should factor it into a component-based constructor that accepts authoritative `HandState` + private assignment + versioned profile metadata. Then seeded simulator decisions and explicit solver branches can be required to produce identical canonical public/private fingerprints at every matched state.
