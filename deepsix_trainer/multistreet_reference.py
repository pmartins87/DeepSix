"""Replay-fork reference transitions for DeepSix F5.

Large imperfect-information solvers eventually need efficient native branching,
but correctness comes first. This module provides a deliberately slower
reference fork: rebuild the same seeded hand from its exact initial stacks and
replay the public action history through the production simulator state
machine. A solver experiment can then branch from the reconstructed decision
without mutating the source hand.

The method is an oracle, not the production traversal. In particular, a
seed-fixed fork follows one already-sampled hidden deal/chance path; it does not
replace chance enumeration or chance sampling in CFR/MCCFR.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from deepsix_core.state import ActionKind, Street
from deepsix_simulator import (
    SimulatedHand,
    SimulatorAction,
    settlement_sha256,
)

from .multistreet_state import (
    MultiStreetStateError,
    decision_state_from_hand,
)


class MultiStreetReferenceError(ValueError):
    """Raised when the deterministic replay-fork oracle detects drift."""


@dataclass(frozen=True)
class ReferenceTransition:
    parent_public_fingerprint: str
    parent_private_fingerprint: str
    action: ActionKind
    amount_to: int | None
    child_terminal: bool
    child_street: Street
    child_public_fingerprint: str | None
    child_private_fingerprint: str | None
    terminal_settlement_sha256: str | None

    def to_dict(self) -> dict:
        return {
            "parent_public_fingerprint": self.parent_public_fingerprint,
            "parent_private_fingerprint": self.parent_private_fingerprint,
            "action": self.action.value,
            "amount_to": self.amount_to,
            "child_terminal": self.child_terminal,
            "child_street": self.child_street.value,
            "child_public_fingerprint": self.child_public_fingerprint,
            "child_private_fingerprint": self.child_private_fingerprint,
            "terminal_settlement_sha256": self.terminal_settlement_sha256,
        }

    def fingerprint(self) -> str:
        raw = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def recovered_initial_stacks(hand: SimulatedHand) -> tuple[tuple[int, int], ...]:
    """Recover exact hand-start stacks before forced contributions."""
    hand.state.validate()
    recovered = tuple(
        (player.seat, player.stack + player.committed_total)
        for player in hand.state.players
    )
    if len(recovered) < 2 or len(recovered) > 6:
        raise MultiStreetReferenceError("recovered stack support is outside 2..6")
    if any(stack <= 0 for _, stack in recovered):
        raise MultiStreetReferenceError("recovered initial stack must be positive")
    if sum(stack for _, stack in recovered) != hand.state.initial_total_chips:
        raise MultiStreetReferenceError("recovered initial stacks violate chip identity")
    return recovered


def replay_fork(hand: SimulatedHand) -> SimulatedHand:
    """Reconstruct the exact current hand by seed + public action replay."""
    try:
        source_decision = decision_state_from_hand(hand)
    except MultiStreetStateError as exc:
        raise MultiStreetReferenceError(str(exc)) from exc

    fork = SimulatedHand.start(
        hand_id=hand.hand_id,
        stake_cents=hand.stake_cents,
        seed=hand.seed,
        dealer_seat=hand.state.dealer_seat,
        stacks=recovered_initial_stacks(hand),
        rules=hand.rules,
        bbj_enabled=hand.bbj_enabled,
    )

    for event in hand.state.actions:
        if fork.terminal:
            raise MultiStreetReferenceError("fork reached terminal before source history ended")
        if fork.actor_seat != event.actor_seat:
            raise MultiStreetReferenceError("actor drift during deterministic replay")
        if fork.state.street != event.street:
            raise MultiStreetReferenceError("street drift during deterministic replay")
        fork.act(
            event.actor_seat,
            SimulatorAction(event.action, event.amount_to),
        )

    if fork.decision_index != hand.decision_index:
        raise MultiStreetReferenceError("decision index drift after replay")
    if fork.hole_cards != hand.hole_cards:
        raise MultiStreetReferenceError("private deal drift after replay")
    if fork.state != hand.state:
        raise MultiStreetReferenceError("authoritative hand state drift after replay")

    fork_decision = decision_state_from_hand(fork)
    if fork_decision.public.fingerprint() != source_decision.public.fingerprint():
        raise MultiStreetReferenceError("public strategic fingerprint drift after replay")
    if fork_decision.fingerprint() != source_decision.fingerprint():
        raise MultiStreetReferenceError("private strategic fingerprint drift after replay")
    return fork


def fork_apply(hand: SimulatedHand, decision: SimulatorAction) -> SimulatedHand:
    """Fork one exact decision and apply a single action to the child."""
    if not isinstance(decision, SimulatorAction):
        raise MultiStreetReferenceError("decision must be SimulatorAction")
    fork = replay_fork(hand)
    actor = fork.actor_seat
    if actor is None:
        raise MultiStreetReferenceError("replayed decision is missing an actor")
    try:
        fork.act(actor, decision)
    except Exception as exc:
        raise MultiStreetReferenceError(f"reference child action rejected: {exc}") from exc
    return fork


def reference_transition(
    hand: SimulatedHand,
    decision: SimulatorAction,
) -> tuple[SimulatedHand, ReferenceTransition]:
    """Create one audited exact transition receipt without mutating ``hand``."""
    parent = decision_state_from_hand(hand)
    child = fork_apply(hand, decision)

    if child.terminal:
        if child.settlement is None:
            raise MultiStreetReferenceError("terminal reference child lacks settlement")
        receipt = ReferenceTransition(
            parent_public_fingerprint=parent.public.fingerprint(),
            parent_private_fingerprint=parent.fingerprint(),
            action=decision.action,
            amount_to=decision.amount_to,
            child_terminal=True,
            child_street=child.state.street,
            child_public_fingerprint=None,
            child_private_fingerprint=None,
            terminal_settlement_sha256=settlement_sha256(child.settlement),
        )
        return child, receipt

    child_state = decision_state_from_hand(child)
    receipt = ReferenceTransition(
        parent_public_fingerprint=parent.public.fingerprint(),
        parent_private_fingerprint=parent.fingerprint(),
        action=decision.action,
        amount_to=decision.amount_to,
        child_terminal=False,
        child_street=child.state.street,
        child_public_fingerprint=child_state.public.fingerprint(),
        child_private_fingerprint=child_state.fingerprint(),
        terminal_settlement_sha256=None,
    )
    return child, receipt
