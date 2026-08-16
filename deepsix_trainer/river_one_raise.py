"""Short Deck river microgame with one fixed bet and one fixed raise-to.

This laboratory game isolates the next action-abstraction dimension after the
multi-sizing/no-raise game: what changes when a single raise is admitted?

Tree (``x`` check, ``b`` bet, ``r`` raise-to, ``f`` fold, ``c`` call):

    P0: x / b
      x -> P1: x / b
        b -> P0: f / c / r
          r -> P1: f / c
      b -> P1: f / c / r
        r -> P0: f / c

There are no re-raises after the first raise. Bet and raise-to amounts are fixed
integer laboratory units. They are not production KKPoker sizing choices.

The implementation keeps the same validation philosophy as the earlier river
microgames: real Short Deck cards/evaluator, blocker-aware exact chance deals,
synchronous full-chance CFR, deterministic/resumable training, and exact best
responses decomposed by own private hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from itertools import product
from math import isfinite
from typing import Mapping

from deepsix_core.cards import ShortDeckCardError, decode_card
from deepsix_core.evaluator import HandValue, evaluate_best
from .river_microgame import RangeHand


History = tuple[str, ...]
PolicyKey = tuple[int, tuple[int, int], History]


class RiverOneRaiseError(ValueError):
    pass


@dataclass(frozen=True)
class OneRaiseDeal:
    p0_cards: tuple[int, int]
    p1_cards: tuple[int, int]
    probability: float
    showdown_sign: int


@dataclass(frozen=True)
class RiverOneRaiseConfig:
    board: tuple[int, int, int, int, int]
    pot: int
    bet_size: int
    raise_to: int
    p0_range: tuple[RangeHand, ...]
    p1_range: tuple[RangeHand, ...]

    def validate(self) -> None:
        if len(self.board) != 5 or len(set(self.board)) != 5:
            raise RiverOneRaiseError("river board must contain five distinct cards")
        try:
            for card in self.board:
                decode_card(card)
        except ShortDeckCardError as exc:
            raise RiverOneRaiseError(str(exc)) from exc
        for name in ("pot", "bet_size", "raise_to"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise RiverOneRaiseError(f"{name} must be a positive integer")
        if self.raise_to <= self.bet_size:
            raise RiverOneRaiseError("raise_to must be strictly larger than bet_size")
        if not self.p0_range or not self.p1_range:
            raise RiverOneRaiseError("both ranges must be non-empty")

        board_set = set(self.board)
        for label, hands in (("p0", self.p0_range), ("p1", self.p1_range)):
            seen: set[tuple[int, int]] = set()
            for hand in hands:
                try:
                    cards = hand.canonical_cards()
                except Exception as exc:
                    raise RiverOneRaiseError(str(exc)) from exc
                if set(cards) & board_set:
                    raise RiverOneRaiseError(f"{label} range overlaps board")
                if cards in seen:
                    raise RiverOneRaiseError(f"duplicate exact combo in {label} range")
                seen.add(cards)
        if not self.compatible_deals():
            raise RiverOneRaiseError("ranges contain no compatible chance deal")

    @lru_cache(maxsize=None)
    def compatible_deals(self) -> tuple[OneRaiseDeal, ...]:
        board_set = set(self.board)
        raw: list[tuple[tuple[int, int], tuple[int, int], float, int]] = []
        total_weight = 0.0
        for p0 in self.p0_range:
            p0_cards = p0.canonical_cards()
            if set(p0_cards) & board_set:
                continue
            for p1 in self.p1_range:
                p1_cards = p1.canonical_cards()
                if set(p1_cards) & board_set or set(p0_cards) & set(p1_cards):
                    continue
                weight = p0.weight * p1.weight
                v0: HandValue = evaluate_best(p0_cards + self.board)
                v1: HandValue = evaluate_best(p1_cards + self.board)
                sign = 1 if v0 > v1 else -1 if v0 < v1 else 0
                raw.append((p0_cards, p1_cards, weight, sign))
                total_weight += weight
        if not raw or total_weight <= 0.0:
            return ()
        return tuple(
            OneRaiseDeal(p0, p1, weight / total_weight, sign)
            for p0, p1, weight, sign in raw
        )


@dataclass(frozen=True)
class RiverOneRaisePolicy:
    strategies: Mapping[PolicyKey, tuple[float, ...]]

    def strategy(
        self,
        config: RiverOneRaiseConfig,
        player: int,
        cards: tuple[int, int],
        history: History,
    ) -> tuple[float, ...]:
        key = (player, tuple(sorted(cards)), history)
        try:
            strategy = self.strategies[key]
        except KeyError as exc:
            raise RiverOneRaiseError(f"policy missing infoset {key}") from exc
        actions = legal_actions(history)
        if len(strategy) != len(actions):
            raise RiverOneRaiseError("strategy/action arity mismatch")
        if any((not isfinite(value)) or value < 0.0 for value in strategy):
            raise RiverOneRaiseError("invalid strategy probability")
        if abs(sum(strategy) - 1.0) > 1e-9:
            raise RiverOneRaiseError("strategy probabilities must sum to one")
        return strategy


@dataclass
class _Node:
    action_count: int
    regret_sum: list[float] = field(init=False)
    strategy_sum: list[float] = field(init=False)

    def __post_init__(self) -> None:
        if self.action_count < 2:
            raise RiverOneRaiseError("decision node requires at least two actions")
        self.regret_sum = [0.0] * self.action_count
        self.strategy_sum = [0.0] * self.action_count

    def current_strategy(self) -> tuple[float, ...]:
        positive = [max(value, 0.0) for value in self.regret_sum]
        total = sum(positive)
        if total > 0.0:
            return tuple(value / total for value in positive)
        p = 1.0 / self.action_count
        return (p,) * self.action_count

    def average_strategy(self) -> tuple[float, ...]:
        total = sum(self.strategy_sum)
        if total > 0.0:
            return tuple(value / total for value in self.strategy_sum)
        p = 1.0 / self.action_count
        return (p,) * self.action_count


@dataclass
class _NodeDelta:
    action_count: int
    regret: list[float] = field(init=False)
    strategy: list[float] = field(init=False)

    def __post_init__(self) -> None:
        self.regret = [0.0] * self.action_count
        self.strategy = [0.0] * self.action_count


def legal_actions(history: History) -> tuple[str, ...]:
    if history == () or history == ("x",):
        return ("x", "b")
    if history == ("b",) or history == ("x", "b"):
        return ("f", "c", "r")
    if history == ("b", "r") or history == ("x", "b", "r"):
        return ("f", "c")
    raise RiverOneRaiseError(f"history has no legal actions: {history!r}")


def is_terminal(history: History) -> bool:
    return history in {
        ("x", "x"),
        ("b", "f"),
        ("b", "c"),
        ("b", "r", "f"),
        ("b", "r", "c"),
        ("x", "b", "f"),
        ("x", "b", "c"),
        ("x", "b", "r", "f"),
        ("x", "b", "r", "c"),
    }


def player_to_act(history: History) -> int:
    if is_terminal(history):
        raise RiverOneRaiseError("terminal history has no actor")
    if history == ():
        return 0
    if history == ("x",):
        return 1
    if history == ("b",):
        return 1
    if history == ("x", "b"):
        return 0
    if history == ("b", "r"):
        return 0
    if history == ("x", "b", "r"):
        return 1
    raise RiverOneRaiseError(f"invalid nonterminal history: {history!r}")


def terminal_utility_p0(
    config: RiverOneRaiseConfig,
    deal: OneRaiseDeal,
    history: History,
) -> float:
    """P0 net utility relative to an equal claim on the starting pot."""
    if not is_terminal(history):
        raise RiverOneRaiseError("history is not terminal")
    half_pot = config.pot / 2.0
    bet = config.bet_size
    raise_to = config.raise_to

    if history == ("x", "x"):
        return deal.showdown_sign * half_pot

    # P0 bet first.
    if history == ("b", "f"):
        return half_pot
    if history == ("b", "c"):
        return deal.showdown_sign * (half_pot + bet)
    if history == ("b", "r", "f"):
        return -(half_pot + bet)
    if history == ("b", "r", "c"):
        return deal.showdown_sign * (half_pot + raise_to)

    # P0 checked, P1 bet.
    if history == ("x", "b", "f"):
        return -half_pot
    if history == ("x", "b", "c"):
        return deal.showdown_sign * (half_pot + bet)
    if history == ("x", "b", "r", "f"):
        # P1 loses its original bet when folding to P0's raise.
        return half_pot + bet
    if history == ("x", "b", "r", "c"):
        return deal.showdown_sign * (half_pot + raise_to)

    raise RiverOneRaiseError(f"unhandled terminal history {history!r}")


def player_histories(player: int) -> tuple[History, ...]:
    if player == 0:
        return ((), ("x", "b"), ("b", "r"))
    if player == 1:
        return (("x",), ("b",), ("x", "b", "r"))
    raise RiverOneRaiseError("player must be 0 or 1")


class RiverOneRaiseCFR:
    def __init__(self, config: RiverOneRaiseConfig) -> None:
        config.validate()
        self.config = config
        self.deals = config.compatible_deals()
        self.nodes: dict[PolicyKey, _Node] = {}
        self.iterations = 0

    def _node(self, key: PolicyKey, action_count: int) -> _Node:
        node = self.nodes.get(key)
        if node is None:
            node = _Node(action_count)
            self.nodes[key] = node
        elif node.action_count != action_count:
            raise RiverOneRaiseError("infoset action count changed")
        return node

    @staticmethod
    def _delta(
        deltas: dict[PolicyKey, _NodeDelta], key: PolicyKey, action_count: int
    ) -> _NodeDelta:
        delta = deltas.get(key)
        if delta is None:
            delta = _NodeDelta(action_count)
            deltas[key] = delta
        elif delta.action_count != action_count:
            raise RiverOneRaiseError("delta action count changed")
        return delta

    def _cfr(
        self,
        deal: OneRaiseDeal,
        history: History,
        reach0: float,
        reach1: float,
        chance_reach: float,
        deltas: dict[PolicyKey, _NodeDelta],
    ) -> float:
        if is_terminal(history):
            return terminal_utility_p0(self.config, deal, history)

        player = player_to_act(history)
        cards = deal.p0_cards if player == 0 else deal.p1_cards
        key: PolicyKey = (player, tuple(sorted(cards)), history)
        actions = legal_actions(history)
        node = self._node(key, len(actions))
        strategy = node.current_strategy()

        values = [0.0] * len(actions)
        node_value = 0.0
        for index, action in enumerate(actions):
            next_history = history + (action,)
            if player == 0:
                value = self._cfr(
                    deal,
                    next_history,
                    reach0 * strategy[index],
                    reach1,
                    chance_reach,
                    deltas,
                )
            else:
                value = self._cfr(
                    deal,
                    next_history,
                    reach0,
                    reach1 * strategy[index],
                    chance_reach,
                    deltas,
                )
            values[index] = value
            node_value += strategy[index] * value

        delta = self._delta(deltas, key, len(actions))
        if player == 0:
            counterfactual = chance_reach * reach1
            average_reach = chance_reach * reach0
            for index in range(len(actions)):
                delta.regret[index] += counterfactual * (values[index] - node_value)
                delta.strategy[index] += average_reach * strategy[index]
        else:
            counterfactual = chance_reach * reach0
            average_reach = chance_reach * reach1
            for index in range(len(actions)):
                delta.regret[index] += counterfactual * (node_value - values[index])
                delta.strategy[index] += average_reach * strategy[index]
        return node_value

    def train(self, iterations: int) -> None:
        if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations <= 0:
            raise RiverOneRaiseError("iterations must be a positive integer")
        for _ in range(iterations):
            deltas: dict[PolicyKey, _NodeDelta] = {}
            for deal in self.deals:
                self._cfr(deal, (), 1.0, 1.0, deal.probability, deltas)
            for key, delta in deltas.items():
                node = self.nodes[key]
                for index in range(node.action_count):
                    node.regret_sum[index] += delta.regret[index]
                    node.strategy_sum[index] += delta.strategy[index]
            self.iterations += 1

    def average_policy(self) -> RiverOneRaisePolicy:
        strategies: dict[PolicyKey, tuple[float, ...]] = {}
        for player, hands in ((0, self.config.p0_range), (1, self.config.p1_range)):
            for hand in hands:
                cards = hand.canonical_cards()
                for history in player_histories(player):
                    actions = legal_actions(history)
                    key: PolicyKey = (player, cards, history)
                    node = self.nodes.get(key)
                    if node is None:
                        p = 1.0 / len(actions)
                        strategies[key] = (p,) * len(actions)
                    else:
                        strategies[key] = node.average_strategy()
        return RiverOneRaisePolicy(strategies)


def _deal_value(
    config: RiverOneRaiseConfig,
    policy0: RiverOneRaisePolicy,
    policy1: RiverOneRaisePolicy,
    deal: OneRaiseDeal,
    history: History = (),
) -> float:
    if is_terminal(history):
        return terminal_utility_p0(config, deal, history)
    player = player_to_act(history)
    policy = policy0 if player == 0 else policy1
    cards = deal.p0_cards if player == 0 else deal.p1_cards
    strategy = policy.strategy(config, player, cards, history)
    actions = legal_actions(history)
    return sum(
        strategy[index]
        * _deal_value(config, policy0, policy1, deal, history + (action,))
        for index, action in enumerate(actions)
    )


def expected_value(
    config: RiverOneRaiseConfig,
    policy0: RiverOneRaisePolicy,
    policy1: RiverOneRaisePolicy,
) -> float:
    config.validate()
    return sum(
        deal.probability * _deal_value(config, policy0, policy1, deal)
        for deal in config.compatible_deals()
    )


def uniform_policy(config: RiverOneRaiseConfig) -> RiverOneRaisePolicy:
    config.validate()
    strategies: dict[PolicyKey, tuple[float, ...]] = {}
    for player, hands in ((0, config.p0_range), (1, config.p1_range)):
        for hand in hands:
            cards = hand.canonical_cards()
            for history in player_histories(player):
                count = len(legal_actions(history))
                p = 1.0 / count
                strategies[(player, cards, history)] = (p,) * count
    return RiverOneRaisePolicy(strategies)


def _deal_value_against_pure_hand_response(
    config: RiverOneRaiseConfig,
    fixed_opponent: RiverOneRaisePolicy,
    deal: OneRaiseDeal,
    br_player: int,
    choices: Mapping[History, int],
    history: History = (),
) -> float:
    if is_terminal(history):
        return terminal_utility_p0(config, deal, history)
    player = player_to_act(history)
    actions = legal_actions(history)
    if player == br_player:
        try:
            index = choices[history]
        except KeyError as exc:
            raise RiverOneRaiseError(
                f"best-response choice missing history {history!r}"
            ) from exc
        if index < 0 or index >= len(actions):
            raise RiverOneRaiseError("best-response action index outside legal actions")
        return _deal_value_against_pure_hand_response(
            config,
            fixed_opponent,
            deal,
            br_player,
            choices,
            history + (actions[index],),
        )

    cards = deal.p0_cards if player == 0 else deal.p1_cards
    strategy = fixed_opponent.strategy(config, player, cards, history)
    return sum(
        strategy[index]
        * _deal_value_against_pure_hand_response(
            config,
            fixed_opponent,
            deal,
            br_player,
            choices,
            history + (action,),
        )
        for index, action in enumerate(actions)
    )


def pure_plans_for_player(player: int) -> tuple[dict[History, int], ...]:
    histories = player_histories(player)
    ranges = [range(len(legal_actions(history))) for history in histories]
    return tuple(dict(zip(histories, choices)) for choices in product(*ranges))


def best_response_value_player0(
    config: RiverOneRaiseConfig,
    opponent: RiverOneRaisePolicy,
) -> float:
    config.validate()
    deals = config.compatible_deals()
    plans = pure_plans_for_player(0)
    total = 0.0
    for hand in config.p0_range:
        cards = hand.canonical_cards()
        hand_deals = tuple(deal for deal in deals if deal.p0_cards == cards)
        if not hand_deals:
            continue
        best = float("-inf")
        for choices in plans:
            contribution = sum(
                deal.probability
                * _deal_value_against_pure_hand_response(
                    config, opponent, deal, 0, choices
                )
                for deal in hand_deals
            )
            best = max(best, contribution)
        total += best
    return total


def best_response_value_player1(
    config: RiverOneRaiseConfig,
    opponent: RiverOneRaisePolicy,
) -> float:
    """Minimum P0 utility achievable by P1's exact best response."""
    config.validate()
    deals = config.compatible_deals()
    plans = pure_plans_for_player(1)
    total = 0.0
    for hand in config.p1_range:
        cards = hand.canonical_cards()
        hand_deals = tuple(deal for deal in deals if deal.p1_cards == cards)
        if not hand_deals:
            continue
        best_for_p1 = float("inf")
        for choices in plans:
            contribution = sum(
                deal.probability
                * _deal_value_against_pure_hand_response(
                    config, opponent, deal, 1, choices
                )
                for deal in hand_deals
            )
            best_for_p1 = min(best_for_p1, contribution)
        total += best_for_p1
    return total


def exploitability(
    config: RiverOneRaiseConfig,
    policy: RiverOneRaisePolicy,
) -> float:
    """Exact half-NashConv in configured chip units/hand."""
    br0 = best_response_value_player0(config, policy)
    br1_as_p0 = best_response_value_player1(config, policy)
    return (br0 - br1_as_p0) / 2.0
