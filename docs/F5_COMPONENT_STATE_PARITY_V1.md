# F5 component strategic-state parity v1

Date: 2026-08-26  
Status: **REFERENCE CONTRACT / PARTIAL F5 FOUNDATION**

## Problem closed

The first F5 strategic-state constructor accepted only `SimulatedHand`. That was safe for the seeded simulator, but it coupled canonical solver identity to one runtime container. The explicit solver branch engine intentionally owns a plain authoritative `HandState` plus a fixed private assignment and therefore could not prove strategic fingerprint parity without pretending to be a simulator hand.

`deepsix_trainer.multistreet_state.decision_state_from_components()` is now the authoritative constructor.

It accepts:

```text
HandState
+ acting player's two physical hole cards
+ stake profile
+ SimulatorRulesProfile
+ BBJ flag
```

and derives the same exact `PublicDecisionState` / `PrivateDecisionState` previously produced by the simulator wrapper.

`decision_state_from_hand()` remains available and delegates to the component constructor.

## Why only the actor's private cards are required

A strategic infoset must not require opponent hole cards. The exact branch engine may know a complete private assignment because it is a physical correctness oracle, but canonical decision identity uses only:

- public state;
- public action history;
- exact public board;
- acting player's own two private cards.

Opponent uncertainty remains in the range/reach layer.

## Profile binding

The constructor validates the authoritative `HandState`, the stake and the `SimulatorRulesProfile`, and requires:

```text
state.config == rules.hand_config(stake_cents)
```

A state generated under one rules/stake contract cannot silently receive the strategic identity of another profile.

## Regression gate

A seeded HU simulator hand and an explicit `ExactBranchState` are advanced together through preflop, flop, turn and river. At every decision node the test requires:

```text
raw HandState equality
actor equality
PublicDecisionState equality
public SHA-256 fingerprint equality
PrivateDecisionState equality
private SHA-256 fingerprint equality
```

The explicit branch receives the exact board reveal emitted by the simulator at each chance transition. This connects three independent F5 boundaries in one end-to-end test:

```text
explicit action/chance branching
        ↓
authoritative Core HandState
        ↓
canonical public/private strategic identity
```

Profile drift and malformed actor-private input fail closed.

## Resulting F5 reference stack

After this contract the same canonical state representation can be consumed by:

- seeded simulator/replay;
- exact explicit action/chance branches;
- future small-support HU traversal;
- later production traversal after solver architecture selection.

The next strategic gate is the first end-to-end HU multi-street microgame that combines action branching, chance, private reach and terminal utility on deliberately tiny supports.
