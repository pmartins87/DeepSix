# F5 multi-street exact strategic state v1

Date: 2026-08-26  
Status: **FOUNDATION / PARTIAL — correctness boundary implemented; no F5 solver family promoted yet**

## Purpose

F5 must connect preflop, flop, turn and river without letting a lossy bucket,
neural embedding or transport-only identifier become the authoritative poker
state.

`deepsix_trainer.multistreet_state` introduces the exact solver-facing boundary
for that work. It consumes the authoritative offline `SimulatedHand` and emits:

```text
PublicDecisionState
    + acting player's canonical private hand
    = PrivateDecisionState
```

The object is a reference/correctness primitive. It is not a claim that the
final large trainer should store every field verbatim or enumerate every exact
state.

## Public node vs private infoset

A public node contains only information shared by every player at that point:

- versioned simulator/rules/economy identity;
- stake and BBJ switch;
- street and exact public board;
- player count and Dealer-relative positions;
- each player's stack, current-street commitment and total commitment;
- folded/all-in state;
- complete public action history;
- ante, pot, current bet and previous full-raise increment;
- the acting seat;
- exact legal-action/raise geometry.

`hand_id`, transport counters and hidden opponent cards are deliberately absent.

The private infoset adds only the acting player's two hole cards and position.
Therefore changing an actor's private hand cannot change the public-node
fingerprint.

## Board-first suit canonicalization

The critical ordering is:

```text
1. canonicalize the PUBLIC board over all 24 global suit renamings
2. retain every suit permutation that attains that same canonical board
3. canonicalize the actor's hole cards only inside that residual symmetry set
```

This prevents a private card from choosing a different global suit mapping and
thereby splitting one public node into multiple identities.

Exact invariances removed:

- physical chair labels, using Dealer-relative positions;
- internal order of the three simultaneously dealt flop cards;
- global suit names;
- order of the actor's two hole cards.

Strategically meaningful distinctions retained:

- flop vs turn vs river;
- turn/river order;
- stack and commitment sizes;
- current bet and full-raise increment;
- complete action path and raise-to amounts;
- player count;
- rake/economy identity through the version/stake/BBJ contract.

## Why current-street commitment is solver-critical

Total contribution alone is insufficient for a multi-street no-limit solver.
`to_call`, legal raise geometry and SPR depend on the commitment made on the
current street. The new state therefore reads `committed_street` directly from
the authoritative `BettingRoundState`, rather than trying to reverse-engineer it
from CALL events or previous-street totals.

This also documents a future runtime-contract requirement: the stable
seat-local policy observation will need to expose equivalent exact information
before F9 can claim byte-for-byte parity with the solver state. F5 itself
remains solver-facing and does not weaken the simulator's hidden-information
boundary.

## SpinCore transfer used here

The transferable SpinCore lesson is structural:

- authoritative state remains exact;
- only true symmetries are quotiented;
- public reach/history and private information are separated;
- richer representation is not promoted merely because it is richer.

DeepSix does **not** import SpinCore's 52-card encoding, tournament utility,
3-seat assumptions, action width or neural representation.

## Gates in v1

The test suite checks:

- global suit-renaming invariance;
- flop internal-order invariance;
- turn/river order remains distinct;
- physical chair rotation invariance;
- exact current-street commitments and raise geometry survive the boundary;
- private cards do not alter public fingerprint;
- a public action changes public identity;
- preflop -> flop transition uses the canonical public board;
- terminal hands cannot fabricate a decision state;
- malformed card geometry fails closed.

## Relationship to exact range/reach

`PrivateReachVector` / `PublicReachState` remain a separate correctness oracle.
The intended F5 composition is:

```text
exact public decision state
        +
per-seat private range/reach
        +
selected F4 traversal/action abstraction
        +
versioned terminal utility
```

The exact range/reach code is not a mandate to enumerate the full Cartesian
private support in production. Any future sampling/factorization must first be
proved against the exact tractable oracle.

## Next gate

F5 remains blocked from selecting a production trainer until the F4 Ryzen
engineering evidence chooses the solver/action/state family. Once that
evidence exists, the next implementation step is a solver-specific multi-street
transition adapter with chance transitions, terminal utility, deterministic
checkpoint/resume and exact local HU subgame audits.
