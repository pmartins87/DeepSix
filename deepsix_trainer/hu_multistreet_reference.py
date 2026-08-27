"""Tiny exact HU multi-street reference game for DeepSix F5.

This is the first end-to-end imperfect-information *evaluation* harness that
connects real Core betting transitions, private ranges, exact future board
chance, canonical infosets and terminal gross/net utility across more than one
street.  It deliberately starts from a fixed flop after a deterministic passive
preflop line so the exact turn/river tree remains small enough for CI audits.

The action abstraction is intentionally tiny and solver-neutral:

* when checked to: CHECK or BET_MIN (the Core's exact min raise-to);
* when facing a bet: FOLD or CALL;
* no re-raise in this v1 reference game.

A future CFR/RM+/MCCFR implementation can optimize policies on this game.  This
module only supplies exact deal/chance/action/utility evaluation and therefore
does not preselect the production solver family.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Callable, Mapping, Sequence

from deepsix_core.cards import decode_card
from deepsix_core.state import ActionKind, Street
from deepsix_simulator.rules import DEFAULT_SIMULATOR_RULES, SimulatorRulesProfile
from deepsix_simulator.utility import utility_from_settlement

from .multistreet_branch import BranchNodeKind, ExactBranchState
from .multistreet_state import PrivateDecisionState, decision_state_from_components
from .reach import PrivateReachVector, compatible_joint_mass


HU_REFERENCE_MICROGAME_VERSION = "deepsix_f5_hu_reference_microgame_2026-08-26_v1"
GROSS_POKER_DELTA = "GROSS_POKER_DELTA"
NET_CASH_DELTA = "NET_CASH_DELTA"


class HuReferenceMicrogameError(ValueError):
    pass


class MicroAction(str, Enum):
    CHECK = "check"
    BET_MIN = "bet_min"
    FOLD = "fold"
    CALL = "call"


@dataclass(frozen=True)
class HuMicrogameConfig:
    stake_cents: int
    dealer_seat: int
    stacks: tuple[tuple[int, int], tuple[int, int]]
    flop: tuple[int, int, int]
    bbj_enabled: bool = False
    rules: SimulatorRulesProfile = DEFAULT_SIMULATOR_RULES

    def validate(self) -> None:
        self.rules.validate()
        seats = tuple(seat for seat, _ in self.stacks)
        if len(set(seats)) != 2:
            raise HuReferenceMicrogameError("HU microgame requires two unique seats")
        if any(
            isinstance(seat, bool)
            or not isinstance(seat, int)
            or seat < 0
            or seat > 5
            for seat in seats
        ):
            raise HuReferenceMicrogameError("HU seats must be physical integers 0..5")
        if self.dealer_seat not in seats:
            raise HuReferenceMicrogameError("Dealer must be one of the HU seats")
        if any(
            isinstance(stack, bool) or not isinstance(stack, int) or stack <= 0
            for _, stack in self.stacks
        ):
            raise HuReferenceMicrogameError("HU stacks must be positive integers")
        if not isinstance(self.bbj_enabled, bool):
            raise HuReferenceMicrogameError("bbj_enabled must be bool")
        if len(self.flop) != 3 or len(set(self.flop)) != 3:
            raise HuReferenceMicrogameError("flop must contain three distinct cards")
        try:
            for card in self.flop:
                decode_card(card)
        except (TypeError, ValueError) as exc:
            raise HuReferenceMicrogameError("flop contains invalid Short Deck card") from exc
        # Also binds the configured stake to the rules profile.
        self.rules.hand_config(self.stake_cents)


@dataclass(frozen=True)
class HuPrivateDeal:
    hole_cards: tuple[tuple[int, tuple[int, int]], tuple[int, tuple[int, int]]]
    probability: Fraction

    def mapping(self) -> dict[int, tuple[int, int]]:
        return dict(self.hole_cards)


@dataclass(frozen=True)
class ExactMicrogameEvaluation:
    version: str
    objective_id: str
    seat_values_antes: tuple[tuple[int, Fraction], tuple[int, Fraction]]
    expected_house_deduction_antes: Fraction
    private_deal_count: int
    root_public_fingerprint: str

    def value_for(self, seat: int) -> Fraction:
        for known, value in self.seat_values_antes:
            if known == seat:
                return value
        raise HuReferenceMicrogameError(f"unknown result seat {seat}")

    @property
    def seat_sum_antes(self) -> Fraction:
        return sum((value for _, value in self.seat_values_antes), Fraction(0, 1))

    def validate(self) -> None:
        if self.version != HU_REFERENCE_MICROGAME_VERSION:
            raise HuReferenceMicrogameError("wrong HU reference microgame version")
        if self.objective_id not in (GROSS_POKER_DELTA, NET_CASH_DELTA):
            raise HuReferenceMicrogameError("unsupported microgame utility objective")
        if self.private_deal_count <= 0:
            raise HuReferenceMicrogameError("microgame must contain a private deal")
        if len(self.root_public_fingerprint) != 64:
            raise HuReferenceMicrogameError("root public fingerprint must be SHA-256")
        if self.expected_house_deduction_antes < 0:
            raise HuReferenceMicrogameError("expected house deduction cannot be negative")
        if self.objective_id == GROSS_POKER_DELTA and self.seat_sum_antes != 0:
            raise HuReferenceMicrogameError("gross HU utility must be exactly zero-sum")
        if (
            self.objective_id == NET_CASH_DELTA
            and self.seat_sum_antes != -self.expected_house_deduction_antes
        ):
            raise HuReferenceMicrogameError(
                "net HU utility must sum to negative expected house deduction"
            )


MicroPolicy = Callable[
    [PrivateDecisionState, tuple[MicroAction, ...]],
    Mapping[MicroAction, int | Fraction],
]


def _exact_probability(value: int | Fraction) -> Fraction:
    if isinstance(value, bool):
        raise HuReferenceMicrogameError("boolean is not a policy probability")
    if isinstance(value, Fraction):
        result = value
    elif isinstance(value, int):
        result = Fraction(value, 1)
    else:
        raise HuReferenceMicrogameError("policy probabilities must be int or Fraction")
    if result < 0:
        raise HuReferenceMicrogameError("policy probability cannot be negative")
    return result


def _validated_policy_distribution(
    policy: MicroPolicy,
    state: PrivateDecisionState,
    actions: tuple[MicroAction, ...],
) -> tuple[tuple[MicroAction, Fraction], ...]:
    raw = policy(state, actions)
    if not isinstance(raw, Mapping):
        raise HuReferenceMicrogameError("policy must return a mapping")
    if set(raw) != set(actions):
        raise HuReferenceMicrogameError("policy distribution must cover exact action support")
    rows = tuple((action, _exact_probability(raw[action])) for action in actions)
    if sum((probability for _, probability in rows), Fraction(0, 1)) != 1:
        raise HuReferenceMicrogameError("policy probabilities must sum exactly to one")
    return rows


def check_call_micro_policy(
    state: PrivateDecisionState,
    actions: tuple[MicroAction, ...],
) -> Mapping[MicroAction, Fraction]:
    del state
    chosen = (
        MicroAction.CHECK
        if MicroAction.CHECK in actions
        else MicroAction.CALL
        if MicroAction.CALL in actions
        else MicroAction.FOLD
    )
    return {action: Fraction(int(action == chosen), 1) for action in actions}


def min_bet_call_micro_policy(
    state: PrivateDecisionState,
    actions: tuple[MicroAction, ...],
) -> Mapping[MicroAction, Fraction]:
    del state
    if MicroAction.BET_MIN in actions:
        chosen = MicroAction.BET_MIN
    elif MicroAction.CALL in actions:
        chosen = MicroAction.CALL
    elif MicroAction.CHECK in actions:
        chosen = MicroAction.CHECK
    else:
        chosen = MicroAction.FOLD
    return {action: Fraction(int(action == chosen), 1) for action in actions}


def uniform_micro_policy(
    state: PrivateDecisionState,
    actions: tuple[MicroAction, ...],
) -> Mapping[MicroAction, Fraction]:
    del state
    probability = Fraction(1, len(actions))
    return {action: probability for action in actions}


class HuReferenceMicrogame:
    def __init__(
        self,
        config: HuMicrogameConfig,
        ranges: Sequence[PrivateReachVector],
    ) -> None:
        config.validate()
        self.config = config
        self.ranges = tuple(sorted(ranges, key=lambda item: item.seat))
        seats = tuple(seat for seat, _ in config.stacks)
        if len(self.ranges) != 2 or {vector.seat for vector in self.ranges} != set(seats):
            raise HuReferenceMicrogameError(
                "HU microgame requires one private reach vector per table seat"
            )
        self.deals = self._enumerate_private_deals()
        if not self.deals:
            raise HuReferenceMicrogameError("flop/ranges have no compatible private deal")

    def _enumerate_private_deals(self) -> tuple[HuPrivateDeal, ...]:
        left, right = self.ranges
        flop_set = set(self.config.flop)
        raw: list[tuple[tuple[tuple[int, tuple[int, int]], tuple[int, tuple[int, int]]], Fraction]] = []
        for left_hand, left_weight in zip(left.hands, left.weights):
            if left_weight == 0 or set(left_hand) & flop_set:
                continue
            for right_hand, right_weight in zip(right.hands, right.weights):
                if right_weight == 0 or set(right_hand) & flop_set:
                    continue
                if set(left_hand) & set(right_hand):
                    continue
                weight = left_weight * right_weight
                if weight == 0:
                    continue
                rows = tuple(sorted(((left.seat, left_hand), (right.seat, right_hand))))
                raw.append((rows, weight))

        try:
            exact_mass = compatible_joint_mass(self.ranges, dead_cards=self.config.flop)
        except Exception as exc:
            raise HuReferenceMicrogameError(str(exc)) from exc
        enumerated_mass = sum((weight for _, weight in raw), Fraction(0, 1))
        if enumerated_mass != exact_mass:
            raise HuReferenceMicrogameError(
                "private-deal enumeration differs from exact compatible reach mass"
            )
        if exact_mass <= 0:
            return ()
        deals = tuple(
            HuPrivateDeal(hole_cards=rows, probability=weight / exact_mass)
            for rows, weight in raw
        )
        if sum((deal.probability for deal in deals), Fraction(0, 1)) != 1:
            raise HuReferenceMicrogameError("private deal probabilities do not sum to one")
        return deals

    def _root_branch(self, deal: HuPrivateDeal) -> ExactBranchState:
        branch = ExactBranchState.from_private_assignment(
            stake_cents=self.config.stake_cents,
            dealer_seat=self.config.dealer_seat,
            stacks=self.config.stacks,
            hole_cards=deal.mapping(),
            rules=self.config.rules,
            bbj_enabled=self.config.bbj_enabled,
        )
        # Fixed passive preflop line: call when priced, otherwise check. This is
        # part of the microgame definition, not a learned strategy.
        guard = 0
        while branch.node_kind == BranchNodeKind.DECISION and branch.state.street == Street.PREFLOP:
            legal = branch.legal_actions()
            if legal.can_check:
                branch = branch.apply_action(ActionKind.CHECK)
            elif legal.can_call:
                branch = branch.apply_action(ActionKind.CALL)
            else:
                raise HuReferenceMicrogameError("passive preflop root line became impossible")
            guard += 1
            if guard > 12:
                raise HuReferenceMicrogameError("preflop root-line decision guard exceeded")

        if branch.node_kind != BranchNodeKind.CHANCE or branch.state.street != Street.PREFLOP:
            raise HuReferenceMicrogameError("microgame root did not reach WAITING_FLOP")
        try:
            branch = branch.apply_chance(self.config.flop)
        except Exception as exc:
            raise HuReferenceMicrogameError(str(exc)) from exc
        if branch.node_kind != BranchNodeKind.DECISION or branch.state.street != Street.FLOP:
            raise HuReferenceMicrogameError("configured flop does not produce a strategic root")
        return branch

    def root_branches(self) -> tuple[tuple[HuPrivateDeal, ExactBranchState], ...]:
        rows = tuple((deal, self._root_branch(deal)) for deal in self.deals)
        public_fingerprints = set()
        for _, branch in rows:
            actor = branch.actor_seat
            if actor is None:
                raise HuReferenceMicrogameError("root branch has no actor")
            strategic = decision_state_from_components(
                branch.state,
                actor_hole_cards=branch.hole_cards_mapping()[actor],
                stake_cents=branch.stake_cents,
                rules=branch.rules,
                bbj_enabled=branch.bbj_enabled,
            )
            public_fingerprints.add(strategic.public.fingerprint())
        if len(public_fingerprints) != 1:
            raise HuReferenceMicrogameError(
                "private assignment changed the public root identity"
            )
        return rows

    @staticmethod
    def abstract_actions(branch: ExactBranchState) -> tuple[MicroAction, ...]:
        if branch.node_kind != BranchNodeKind.DECISION:
            raise HuReferenceMicrogameError("abstract actions require decision node")
        legal = branch.legal_actions()
        actions: list[MicroAction] = []
        if legal.can_check:
            actions.append(MicroAction.CHECK)
            if legal.can_raise:
                actions.append(MicroAction.BET_MIN)
        else:
            if legal.can_fold:
                actions.append(MicroAction.FOLD)
            if legal.can_call:
                actions.append(MicroAction.CALL)
        if not actions:
            raise HuReferenceMicrogameError("microgame action abstraction is empty")
        return tuple(actions)

    @staticmethod
    def _apply_micro_action(
        branch: ExactBranchState,
        action: MicroAction,
    ) -> ExactBranchState:
        legal = branch.legal_actions()
        if action == MicroAction.CHECK:
            return branch.apply_action(ActionKind.CHECK)
        if action == MicroAction.FOLD:
            return branch.apply_action(ActionKind.FOLD)
        if action == MicroAction.CALL:
            return branch.apply_action(ActionKind.CALL)
        if action == MicroAction.BET_MIN:
            if not legal.can_raise:
                raise HuReferenceMicrogameError("BET_MIN requested without raise right")
            return branch.apply_action(ActionKind.RAISE_TO, legal.min_raise_to)
        raise HuReferenceMicrogameError(f"unsupported micro action {action!r}")

    def _terminal_values(
        self,
        branch: ExactBranchState,
        objective_id: str,
    ) -> tuple[dict[int, Fraction], Fraction]:
        settlement = branch.settle()
        utility = utility_from_settlement(
            branch.state,
            settlement,
            stake_cents=branch.stake_cents,
            rules=branch.rules,
        )
        values: dict[int, Fraction] = {}
        for seat, _ in self.config.stacks:
            row = utility.for_seat(seat)
            if objective_id == GROSS_POKER_DELTA:
                values[seat] = row.gross_poker_delta_antes
            elif objective_id == NET_CASH_DELTA:
                values[seat] = row.net_cash_delta_antes
            else:
                raise HuReferenceMicrogameError("unsupported utility objective")
        house = Fraction(utility.total_house_deduction_units, utility.ante_units)
        return values, house

    def _evaluate_branch(
        self,
        branch: ExactBranchState,
        policy: MicroPolicy,
        objective_id: str,
    ) -> tuple[dict[int, Fraction], Fraction]:
        seats = tuple(seat for seat, _ in self.config.stacks)
        if branch.node_kind == BranchNodeKind.TERMINAL:
            return self._terminal_values(branch, objective_id)

        if branch.node_kind == BranchNodeKind.CHANCE:
            values = {seat: Fraction(0, 1) for seat in seats}
            expected_house = Fraction(0, 1)
            for outcome in branch.chance_outcomes():
                child_values, child_house = self._evaluate_branch(
                    branch.apply_chance(outcome.revealed),
                    policy,
                    objective_id,
                )
                for seat in seats:
                    values[seat] += outcome.probability * child_values[seat]
                expected_house += outcome.probability * child_house
            return values, expected_house

        actor = branch.actor_seat
        if actor is None:
            raise HuReferenceMicrogameError("decision branch has no actor")
        strategic = decision_state_from_components(
            branch.state,
            actor_hole_cards=branch.hole_cards_mapping()[actor],
            stake_cents=branch.stake_cents,
            rules=branch.rules,
            bbj_enabled=branch.bbj_enabled,
        )
        actions = self.abstract_actions(branch)
        distribution = _validated_policy_distribution(policy, strategic, actions)
        values = {seat: Fraction(0, 1) for seat in seats}
        expected_house = Fraction(0, 1)
        for action, probability in distribution:
            if probability == 0:
                continue
            child_values, child_house = self._evaluate_branch(
                self._apply_micro_action(branch, action),
                policy,
                objective_id,
            )
            for seat in seats:
                values[seat] += probability * child_values[seat]
            expected_house += probability * child_house
        return values, expected_house

    def evaluate(
        self,
        policy: MicroPolicy,
        *,
        objective_id: str,
    ) -> ExactMicrogameEvaluation:
        if objective_id not in (GROSS_POKER_DELTA, NET_CASH_DELTA):
            raise HuReferenceMicrogameError("objective must be gross poker or net cash")
        roots = self.root_branches()
        seats = tuple(sorted(seat for seat, _ in self.config.stacks))
        values = {seat: Fraction(0, 1) for seat in seats}
        expected_house = Fraction(0, 1)
        public_fingerprint: str | None = None

        for deal, root in roots:
            actor = root.actor_seat
            if actor is None:
                raise HuReferenceMicrogameError("root branch missing actor")
            strategic = decision_state_from_components(
                root.state,
                actor_hole_cards=root.hole_cards_mapping()[actor],
                stake_cents=root.stake_cents,
                rules=root.rules,
                bbj_enabled=root.bbj_enabled,
            )
            if public_fingerprint is None:
                public_fingerprint = strategic.public.fingerprint()
            elif public_fingerprint != strategic.public.fingerprint():
                raise HuReferenceMicrogameError("root public fingerprint drift across deals")

            deal_values, deal_house = self._evaluate_branch(root, policy, objective_id)
            for seat in seats:
                values[seat] += deal.probability * deal_values[seat]
            expected_house += deal.probability * deal_house

        if public_fingerprint is None:
            raise HuReferenceMicrogameError("missing root public fingerprint")
        result = ExactMicrogameEvaluation(
            version=HU_REFERENCE_MICROGAME_VERSION,
            objective_id=objective_id,
            seat_values_antes=tuple((seat, values[seat]) for seat in seats),  # type: ignore[arg-type]
            expected_house_deduction_antes=expected_house,
            private_deal_count=len(self.deals),
            root_public_fingerprint=public_fingerprint,
        )
        result.validate()
        return result
