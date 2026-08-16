"""Multi-sizing Short Deck river microgame for action-abstraction experiments.

This deliberately extends ``river_microgame`` by exactly one dimension: each
player may choose CHECK or one of several configured BET sizes when no bet is
faced; the defender may only FOLD or CALL.  Raises remain outside the lab game.

The sizes are experimental integer chip units, not production KKPoker sizing
recommendations.  The purpose is to measure what extra actions buy in strategy
quality relative to their tree/CPU cost before freezing a larger abstraction.

CFR iterations are synchronous across all chance deals. Exact best responses
are optimized independently per own private hand and enumerate only that hand's
small pure action plan, keeping the audit exact while range size grows.
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


class RiverMultiSizeError(ValueError):
    pass


def _bet_token(size: int) -> str:
    return f"b{size}"


def _parse_bet_token(token: str) -> int:
    if not token.startswith("b") or len(token) == 1:
        raise RiverMultiSizeError(f"not a bet token: {token!r}")
    try:
        size = int(token[1:])
    except ValueError as exc:
        raise RiverMultiSizeError(f"invalid bet token: {token!r}") from exc
    if size <= 0 or _bet_token(size) != token:
        raise RiverMultiSizeError(f"non-canonical bet token: {token!r}")
    return size


@dataclass(frozen=True)
class MultiSizeDeal:
    p0_cards: tuple[int, int]
    p1_cards: tuple[int, int]
    probability: float
    showdown_sign: int


@dataclass(frozen=True)
class RiverMultiSizeConfig:
    board: tuple[int, int, int, int, int]
    pot: int
    bet_sizes: tuple[int, ...]
    p0_range: tuple[RangeHand, ...]
    p1_range: tuple[RangeHand, ...]

    def validate(self) -> None:
        if len(self.board) != 5 or len(set(self.board)) != 5:
            raise RiverMultiSizeError("river board must contain five distinct cards")
        try:
            for card in self.board:
                decode_card(card)
        except ShortDeckCardError as exc:
            raise RiverMultiSizeError(str(exc)) from exc
        if isinstance(self.pot, bool) or not isinstance(self.pot, int) or self.pot <= 0:
            raise RiverMultiSizeError("pot must be a positive integer")
        if not self.bet_sizes:
            raise RiverMultiSizeError("at least one bet size is required")
        if len(self.bet_sizes) > 4:
            raise RiverMultiSizeError(
                "v1 exact audit intentionally caps action abstraction at four bet sizes"
            )
        previous = 0
        for size in self.bet_sizes:
            if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
                raise RiverMultiSizeError("bet sizes must be positive integers")
            if size <= previous:
                raise RiverMultiSizeError("bet sizes must be unique and strictly increasing")
            previous = size
        if not self.p0_range or not self.p1_range:
            raise RiverMultiSizeError("both ranges must be non-empty")

        board_set = set(self.board)
        for label, range_hands in (("p0", self.p0_range), ("p1", self.p1_range)):
            seen: set[tuple[int, int]] = set()
            for hand in range_hands:
                try:
                    cards = hand.canonical_cards()
                except Exception as exc:
                    raise RiverMultiSizeError(str(exc)) from exc
                if set(cards) & board_set:
                    raise RiverMultiSizeError(f"{label} range overlaps board")
                if cards in seen:
                    raise RiverMultiSizeError(f"duplicate exact combo in {label} range")
                seen.add(cards)
        if not self.compatible_deals():
            raise RiverMultiSizeError("ranges contain no compatible chance deal")

    @lru_cache(maxsize=None)
    def compatible_deals(self) -> tuple[MultiSizeDeal, ...]:
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
                p0_value: HandValue = evaluate_best(p0_cards + self.board)
                p1_value: HandValue = evaluate_best(p1_cards + self.board)
                sign = 1 if p0_value > p1_value else -1 if p0_value < p1_value else 0
                raw.append((p0_cards, p1_cards, weight, sign))
                total_weight += weight
        if not raw or total_weight <= 0.0:
            return ()
        return tuple(
            MultiSizeDeal(p0, p1, weight / total_weight, sign)
            for p0, p1, weight, sign in raw
        )

    def bet_tokens(self) -> tuple[str, ...]:
        return tuple(_bet_token(size) for size in self.bet_sizes)


@dataclass(frozen=True)
class RiverMultiSizePolicy:
    strategies: Mapping[PolicyKey, tuple[float, ...]]

    def strategy(
        self,
        config: RiverMultiSizeConfig,
        player: int,
        cards: tuple[int, int],
        history: History,
    ) -> tuple[float, ...]:
        key = (player, tuple(sorted(cards)), history)
        try:
            strategy = self.strategies[key]
        except KeyError as exc:
            raise RiverMultiSizeError(f"policy missing infoset {key}") from exc
        actions = _legal_actions(config, history)
        if len(strategy) != len(actions):
            raise RiverMultiSizeError("strategy/action arity mismatch")
        if any((not isfinite(value)) or value < 0.0 for value in strategy):
            raise RiverMultiSizeError("invalid strategy probability")
        if abs(sum(strategy) - 1.0) > 1e-9:
            raise RiverMultiSizeError("strategy probabilities must sum to one")
        return strategy


@dataclass
class _Node:
    action_count: int
    regret_sum: list[float] = field(init=False)
    strategy_sum: list[float] = field(init=False)

    def __post_init__(self) -> None:
        if self.action_count < 2:
            raise RiverMultiSizeError("decision node requires at least two actions")
        self.regret_sum = [0.0] * self.action_count
        self.strategy_sum = [0.0] * self.action_count

    def current_strategy(self) -> tuple[float, ...]:
        positive = [max(value, 0.0) for value in self.regret_sum]
        normalizer = sum(positive)
        if normalizer > 0.0:
            return tuple(value / normalizer for value in positive)
        probability = 1.0 / self.action_count
        return (probability,) * self.action_count

    def average_strategy(self) -> tuple[float, ...]:
        normalizer = sum(self.strategy_sum)
        if normalizer > 0.0:
            return tuple(value / normalizer for value in self.strategy_sum)
        probability = 1.0 / self.action_count
        return (probability,) * self.action_count


@dataclass
class _NodeDelta:
    action_count: int
    regret: list[float] = field(init=False)
    strategy: list[float] = field(init=False)

    def __post_init__(self) -> None:
        self.regret = [0.0] * self.action_count
        self.strategy = [0.0] * self.action_count


def _legal_actions(config: RiverMultiSizeConfig, history: History) -> tuple[str, ...]:
    bets = config.bet_tokens()
    if history == () or history == ("x",):
        return ("x",) + bets
    if len(history) == 1 and history[0] in bets:
        return ("f", "c")
    if len(history) == 2 and history[0] == "x" and history[1] in bets:
        return ("f", "c")
    raise RiverMultiSizeError(f"history has no legal actions: {history!r}")


def _is_terminal(config: RiverMultiSizeConfig, history: History) -> bool:
    bets = set(config.bet_tokens())
    if history == ("x", "x"):
        return True
    if len(history) == 2 and history[0] in bets and history[1] in ("f", "c"):
        return True
    if (
        len(history) == 3
        and history[0] == "x"
        and history[1] in bets
        and history[2] in ("f", "c")
    ):
        return True
    return False


def _player_to_act(config: RiverMultiSizeConfig, history: History) -> int:
    if _is_terminal(config, history):
        raise RiverMultiSizeError("terminal history has no actor")
    bets = set(config.bet_tokens())
    if history == ():
        return 0
    if history == ("x",):
        return 1
    if len(history) == 1 and history[0] in bets:
        return 1
    if len(history) == 2 and history[0] == "x" and history[1] in bets:
        return 0
    raise RiverMultiSizeError(f"invalid nonterminal history: {history!r}")


def _terminal_utility_p0(
    config: RiverMultiSizeConfig,
    deal: MultiSizeDeal,
    history: History,
) -> float:
    if not _is_terminal(config, history):
        raise RiverMultiSizeError("history is not terminal")
    half_pot = config.pot / 2.0
    if history == ("x", "x"):
        return deal.showdown_sign * half_pot
    if len(history) == 2:
        size = _parse_bet_token(history[0])
        if history[1] == "f":
            return half_pot
        return deal.showdown_sign * (half_pot + size)
    size = _parse_bet_token(history[1])
    if history[2] == "f":
        return -half_pot
    return deal.showdown_sign * (half_pot + size)


def _player_histories(config: RiverMultiSizeConfig, player: int) -> tuple[History, ...]:
    bets = config.bet_tokens()
    if player == 0:
        return ((),) + tuple(("x", bet) for bet in bets)
    if player == 1:
        return (("x",),) + tuple((bet,) for bet in bets)
    raise RiverMultiSizeError("player must be 0 or 1")


class RiverMultiSizeCFR:
    """Synchronous full-chance CFR over the multi-sizing river lab game."""

    def __init__(self, config: RiverMultiSizeConfig) -> None:
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
            raise RiverMultiSizeError("infoset action count changed")
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
            raise RiverMultiSizeError("delta action count changed")
        return delta

    def _cfr(
        self,
        deal: MultiSizeDeal,
        history: History,
        reach0: float,
        reach1: float,
        chance_reach: float,
        deltas: dict[PolicyKey, _NodeDelta],
    ) -> float:
        if _is_terminal(self.config, history):
            return _terminal_utility_p0(self.config, deal, history)

        player = _player_to_act(self.config, history)
        cards = deal.p0_cards if player == 0 else deal.p1_cards
        key: PolicyKey = (player, tuple(sorted(cards)), history)
        actions = _legal_actions(self.config, history)
        node = self._node(key, len(actions))
        strategy = node.current_strategy()

        action_values = [0.0] * len(actions)
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
            action_values[index] = value
            node_value += strategy[index] * value

        delta = self._delta(deltas, key, len(actions))
        if player == 0:
            counterfactual_reach = chance_reach * reach1
            average_reach = chance_reach * reach0
            for index in range(len(actions)):
                delta.regret[index] += counterfactual_reach * (
                    action_values[index] - node_value
                )
                delta.strategy[index] += average_reach * strategy[index]
        else:
            counterfactual_reach = chance_reach * reach0
            average_reach = chance_reach * reach1
            for index in range(len(actions)):
                delta.regret[index] += counterfactual_reach * (
                    node_value - action_values[index]
                )
                delta.strategy[index] += average_reach * strategy[index]
        return node_value

    def train(self, iterations: int) -> None:
        if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations <= 0:
            raise RiverMultiSizeError("iterations must be a positive integer")
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

    def average_policy(self) -> RiverMultiSizePolicy:
        strategies: dict[PolicyKey, tuple[float, ...]] = {}
        for player, range_hands in ((0, self.config.p0_range), (1, self.config.p1_range)):
            for hand in range_hands:
                cards = hand.canonical_cards()
                for history in _player_histories(self.config, player):
                    key: PolicyKey = (player, cards, history)
                    action_count = len(_legal_actions(self.config, history))
                    node = self.nodes.get(key)
                    if node is None:
                        probability = 1.0 / action_count
                        strategies[key] = (probability,) * action_count
                    else:
                        strategies[key] = node.average_strategy()
        return RiverMultiSizePolicy(strategies)


def _deal_value(
    config: RiverMultiSizeConfig,
    policy0: RiverMultiSizePolicy,
    policy1: RiverMultiSizePolicy,
    deal: MultiSizeDeal,
    history: History = (),
) -> float:
    if _is_terminal(config, history):
        return _terminal_utility_p0(config, deal, history)
    player = _player_to_act(config, history)
    policy = policy0 if player == 0 else policy1
    cards = deal.p0_cards if player == 0 else deal.p1_cards
    strategy = policy.strategy(config, player, cards, history)
    actions = _legal_actions(config, history)
    return sum(
        strategy[index]
        * _deal_value(config, policy0, policy1, deal, history + (action,))
        for index, action in enumerate(actions)
    )


def expected_value(
    config: RiverMultiSizeConfig,
    policy0: RiverMultiSizePolicy,
    policy1: RiverMultiSizePolicy,
) -> float:
    config.validate()
    return sum(
        deal.probability * _deal_value(config, policy0, policy1, deal)
        for deal in config.compatible_deals()
    )


def uniform_policy(config: RiverMultiSizeConfig) -> RiverMultiSizePolicy:
    """Convenience baseline covering every configured range-hand infoset."""
    config.validate()
    strategies: dict[PolicyKey, tuple[float, ...]] = {}
    for player, range_hands in ((0, config.p0_range), (1, config.p1_range)):
        for hand in range_hands:
            cards = hand.canonical_cards()
            for history in _player_histories(config, player):
                action_count = len(_legal_actions(config, history))
                probability = 1.0 / action_count
                strategies[(player, cards, history)] = (probability,) * action_count
    return RiverMultiSizePolicy(strategies)


def _deal_value_against_pure_hand_response(
    config: RiverMultiSizeConfig,
    fixed_opponent: RiverMultiSizePolicy,
    deal: MultiSizeDeal,
    br_player: int,
    choices: Mapping[History, int],
    history: History = (),
) -> float:
    if _is_terminal(config, history):
        return _terminal_utility_p0(config, deal, history)
    player = _player_to_act(config, history)
    actions = _legal_actions(config, history)
    if player == br_player:
        try:
            action_index = choices[history]
        except KeyError as exc:
            raise RiverMultiSizeError(
                f"best-response choice missing history {history!r}"
            ) from exc
        if action_index < 0 or action_index >= len(actions):
            raise RiverMultiSizeError("best-response action index outside legal actions")
        return _deal_value_against_pure_hand_response(
            config,
            fixed_opponent,
            deal,
            br_player,
            choices,
            history + (actions[action_index],),
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


def _pure_plans_for_player(
    config: RiverMultiSizeConfig, player: int
) -> tuple[dict[History, int], ...]:
    histories = _player_histories(config, player)
    action_ranges = [range(len(_legal_actions(config, history))) for history in histories]
    return tuple(
        dict(zip(histories, choices))
        for choices in product(*action_ranges)
    )


def best_response_value_player0(
    config: RiverMultiSizeConfig,
    opponent: RiverMultiSizePolicy,
) -> float:
    config.validate()
    deals = config.compatible_deals()
    plans = _pure_plans_for_player(config, 0)
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
    config: RiverMultiSizeConfig,
    opponent: RiverMultiSizePolicy,
) -> float:
    """Minimum P0 utility achievable by the exact P1 best response."""
    config.validate()
    deals = config.compatible_deals()
    plans = _pure_plans_for_player(config, 1)
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
    config: RiverMultiSizeConfig,
    policy: RiverMultiSizePolicy,
) -> float:
    """Exact half-NashConv in configured chip units/hand."""
    br0 = best_response_value_player0(config, policy)
    br1_as_p0 = best_response_value_player1(config, policy)
    return (br0 - br1_as_p0) / 2.0
