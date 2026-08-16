"""Short Deck river microgame with multiple initial bet sizes and one raise layer.

This is the next controlled action-abstraction laboratory after:

* ``river_multisize``: multiple initial bet sizes, no raises; and
* ``river_one_raise``: one initial bet size, one fixed raise-to.

V1 combines exactly those two dimensions and nothing more.  When no bet is
faced, a player may CHECK or choose one configured BET size.  Facing any bet,
the defender may FOLD, CALL, or RAISE to one configured absolute ``raise_to``.
Facing that raise, the original bettor may only FOLD or CALL.  No re-raise is
available.

The configured values are laboratory integer chip units, not KKPoker sizing
recommendations.  The purpose is to quantify how much tree/CPU cost appears
when multiple sizings and a first raise coexist, while exact best response is
still cheap enough to audit independently.

V1 caps initial bet sizes at two.  For S sizes, one private hand has

    (1 + S) * 3**S * 2**S == (1 + S) * 6**S

pure response plans.  S=2 therefore means 108 plans per hand, still practical
for exact gates.  Larger action sets should move to a different exact-BR
implementation rather than silently turning validation into an exponential
bottleneck.
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


class RiverMultiSizeOneRaiseError(ValueError):
    pass


def _bet_token(size: int) -> str:
    return f"b{size}"


def _parse_bet_token(token: str) -> int:
    if not token.startswith("b") or len(token) == 1:
        raise RiverMultiSizeOneRaiseError(f"not a bet token: {token!r}")
    try:
        size = int(token[1:])
    except ValueError as exc:
        raise RiverMultiSizeOneRaiseError(f"invalid bet token: {token!r}") from exc
    if size <= 0 or _bet_token(size) != token:
        raise RiverMultiSizeOneRaiseError(f"non-canonical bet token: {token!r}")
    return size


@dataclass(frozen=True)
class MultiSizeOneRaiseDeal:
    p0_cards: tuple[int, int]
    p1_cards: tuple[int, int]
    probability: float
    showdown_sign: int


@dataclass(frozen=True)
class RiverMultiSizeOneRaiseConfig:
    board: tuple[int, int, int, int, int]
    pot: int
    bet_sizes: tuple[int, ...]
    raise_to: int
    p0_range: tuple[RangeHand, ...]
    p1_range: tuple[RangeHand, ...]

    def validate(self) -> None:
        if len(self.board) != 5 or len(set(self.board)) != 5:
            raise RiverMultiSizeOneRaiseError(
                "river board must contain five distinct cards"
            )
        try:
            for card in self.board:
                decode_card(card)
        except ShortDeckCardError as exc:
            raise RiverMultiSizeOneRaiseError(str(exc)) from exc
        if isinstance(self.pot, bool) or not isinstance(self.pot, int) or self.pot <= 0:
            raise RiverMultiSizeOneRaiseError("pot must be a positive integer")
        if not self.bet_sizes:
            raise RiverMultiSizeOneRaiseError("at least one bet size is required")
        if len(self.bet_sizes) > 2:
            raise RiverMultiSizeOneRaiseError(
                "v1 exact audit intentionally caps initial bet sizes at two"
            )
        previous = 0
        for size in self.bet_sizes:
            if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
                raise RiverMultiSizeOneRaiseError(
                    "bet sizes must be positive integers"
                )
            if size <= previous:
                raise RiverMultiSizeOneRaiseError(
                    "bet sizes must be unique and strictly increasing"
                )
            previous = size
        if (
            isinstance(self.raise_to, bool)
            or not isinstance(self.raise_to, int)
            or self.raise_to <= max(self.bet_sizes)
        ):
            raise RiverMultiSizeOneRaiseError(
                "raise_to must be an integer strictly above every bet size"
            )
        if not self.p0_range or not self.p1_range:
            raise RiverMultiSizeOneRaiseError("both ranges must be non-empty")

        board_set = set(self.board)
        for label, hands in (("p0", self.p0_range), ("p1", self.p1_range)):
            seen: set[tuple[int, int]] = set()
            for hand in hands:
                try:
                    cards = hand.canonical_cards()
                except Exception as exc:
                    raise RiverMultiSizeOneRaiseError(str(exc)) from exc
                if set(cards) & board_set:
                    raise RiverMultiSizeOneRaiseError(f"{label} range overlaps board")
                if cards in seen:
                    raise RiverMultiSizeOneRaiseError(
                        f"duplicate exact combo in {label} range"
                    )
                seen.add(cards)
        if not self.compatible_deals():
            raise RiverMultiSizeOneRaiseError(
                "ranges contain no compatible chance deal"
            )

    @lru_cache(maxsize=None)
    def compatible_deals(self) -> tuple[MultiSizeOneRaiseDeal, ...]:
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
            MultiSizeOneRaiseDeal(p0, p1, weight / total_weight, sign)
            for p0, p1, weight, sign in raw
        )

    def bet_tokens(self) -> tuple[str, ...]:
        return tuple(_bet_token(size) for size in self.bet_sizes)


@dataclass(frozen=True)
class RiverMultiSizeOneRaisePolicy:
    strategies: Mapping[PolicyKey, tuple[float, ...]]

    def strategy(
        self,
        config: RiverMultiSizeOneRaiseConfig,
        player: int,
        cards: tuple[int, int],
        history: History,
    ) -> tuple[float, ...]:
        key = (player, tuple(sorted(cards)), history)
        try:
            strategy = self.strategies[key]
        except KeyError as exc:
            raise RiverMultiSizeOneRaiseError(f"policy missing infoset {key}") from exc
        actions = legal_actions(config, history)
        if len(strategy) != len(actions):
            raise RiverMultiSizeOneRaiseError("strategy/action arity mismatch")
        if any((not isfinite(value)) or value < 0.0 for value in strategy):
            raise RiverMultiSizeOneRaiseError("invalid strategy probability")
        if abs(sum(strategy) - 1.0) > 1e-9:
            raise RiverMultiSizeOneRaiseError(
                "strategy probabilities must sum to one"
            )
        return strategy


@dataclass
class _Node:
    action_count: int
    regret_sum: list[float] = field(init=False)
    strategy_sum: list[float] = field(init=False)

    def __post_init__(self) -> None:
        if self.action_count < 2:
            raise RiverMultiSizeOneRaiseError(
                "decision node requires at least two actions"
            )
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


def legal_actions(
    config: RiverMultiSizeOneRaiseConfig,
    history: History,
) -> tuple[str, ...]:
    bets = config.bet_tokens()
    if history == () or history == ("x",):
        return ("x",) + bets
    if len(history) == 1 and history[0] in bets:
        return ("f", "c", "r")
    if len(history) == 2 and history[0] == "x" and history[1] in bets:
        return ("f", "c", "r")
    if len(history) == 2 and history[0] in bets and history[1] == "r":
        return ("f", "c")
    if (
        len(history) == 3
        and history[0] == "x"
        and history[1] in bets
        and history[2] == "r"
    ):
        return ("f", "c")
    raise RiverMultiSizeOneRaiseError(
        f"history has no legal actions: {history!r}"
    )


def is_terminal(config: RiverMultiSizeOneRaiseConfig, history: History) -> bool:
    bets = set(config.bet_tokens())
    if history == ("x", "x"):
        return True
    if len(history) == 2 and history[0] in bets and history[1] in ("f", "c"):
        return True
    if (
        len(history) == 3
        and history[0] in bets
        and history[1] == "r"
        and history[2] in ("f", "c")
    ):
        return True
    if (
        len(history) == 3
        and history[0] == "x"
        and history[1] in bets
        and history[2] in ("f", "c")
    ):
        return True
    if (
        len(history) == 4
        and history[0] == "x"
        and history[1] in bets
        and history[2] == "r"
        and history[3] in ("f", "c")
    ):
        return True
    return False


def player_to_act(config: RiverMultiSizeOneRaiseConfig, history: History) -> int:
    if is_terminal(config, history):
        raise RiverMultiSizeOneRaiseError("terminal history has no actor")
    bets = set(config.bet_tokens())
    if history == ():
        return 0
    if history == ("x",):
        return 1
    if len(history) == 1 and history[0] in bets:
        return 1
    if len(history) == 2 and history[0] == "x" and history[1] in bets:
        return 0
    if len(history) == 2 and history[0] in bets and history[1] == "r":
        return 0
    if (
        len(history) == 3
        and history[0] == "x"
        and history[1] in bets
        and history[2] == "r"
    ):
        return 1
    raise RiverMultiSizeOneRaiseError(
        f"invalid nonterminal history: {history!r}"
    )


def terminal_utility_p0(
    config: RiverMultiSizeOneRaiseConfig,
    deal: MultiSizeOneRaiseDeal,
    history: History,
) -> float:
    if not is_terminal(config, history):
        raise RiverMultiSizeOneRaiseError("history is not terminal")
    half_pot = config.pot / 2.0

    if history == ("x", "x"):
        return deal.showdown_sign * half_pot

    # P0 bet first.
    if len(history) == 2 and history[0] in config.bet_tokens():
        bet = _parse_bet_token(history[0])
        if history[1] == "f":
            return half_pot
        if history[1] == "c":
            return deal.showdown_sign * (half_pot + bet)
    if (
        len(history) == 3
        and history[0] in config.bet_tokens()
        and history[1] == "r"
    ):
        bet = _parse_bet_token(history[0])
        if history[2] == "f":
            return -(half_pot + bet)
        if history[2] == "c":
            return deal.showdown_sign * (half_pot + config.raise_to)

    # P0 checked, P1 bet.
    if (
        len(history) == 3
        and history[0] == "x"
        and history[1] in config.bet_tokens()
    ):
        bet = _parse_bet_token(history[1])
        if history[2] == "f":
            return -half_pot
        if history[2] == "c":
            return deal.showdown_sign * (half_pot + bet)
    if (
        len(history) == 4
        and history[0] == "x"
        and history[1] in config.bet_tokens()
        and history[2] == "r"
    ):
        bet = _parse_bet_token(history[1])
        if history[3] == "f":
            return half_pot + bet
        if history[3] == "c":
            return deal.showdown_sign * (half_pot + config.raise_to)

    raise RiverMultiSizeOneRaiseError(
        f"unhandled terminal history {history!r}"
    )


def player_histories(
    config: RiverMultiSizeOneRaiseConfig,
    player: int,
) -> tuple[History, ...]:
    bets = config.bet_tokens()
    if player == 0:
        return (
            ((),)
            + tuple(("x", bet) for bet in bets)
            + tuple((bet, "r") for bet in bets)
        )
    if player == 1:
        return (
            (("x",),)
            + tuple((bet,) for bet in bets)
            + tuple(("x", bet, "r") for bet in bets)
        )
    raise RiverMultiSizeOneRaiseError("player must be 0 or 1")


def pure_plan_count(config: RiverMultiSizeOneRaiseConfig) -> int:
    sizes = len(config.bet_sizes)
    return (1 + sizes) * (6**sizes)


class RiverMultiSizeOneRaiseCFR:
    def __init__(self, config: RiverMultiSizeOneRaiseConfig) -> None:
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
            raise RiverMultiSizeOneRaiseError("infoset action count changed")
        return node

    @staticmethod
    def _delta(
        deltas: dict[PolicyKey, _NodeDelta],
        key: PolicyKey,
        action_count: int,
    ) -> _NodeDelta:
        delta = deltas.get(key)
        if delta is None:
            delta = _NodeDelta(action_count)
            deltas[key] = delta
        elif delta.action_count != action_count:
            raise RiverMultiSizeOneRaiseError("delta action count changed")
        return delta

    def _cfr(
        self,
        deal: MultiSizeOneRaiseDeal,
        history: History,
        reach0: float,
        reach1: float,
        chance_reach: float,
        deltas: dict[PolicyKey, _NodeDelta],
    ) -> float:
        if is_terminal(self.config, history):
            return terminal_utility_p0(self.config, deal, history)

        player = player_to_act(self.config, history)
        cards = deal.p0_cards if player == 0 else deal.p1_cards
        key: PolicyKey = (player, tuple(sorted(cards)), history)
        actions = legal_actions(self.config, history)
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
        if (
            isinstance(iterations, bool)
            or not isinstance(iterations, int)
            or iterations <= 0
        ):
            raise RiverMultiSizeOneRaiseError(
                "iterations must be a positive integer"
            )
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

    def average_policy(self) -> RiverMultiSizeOneRaisePolicy:
        strategies: dict[PolicyKey, tuple[float, ...]] = {}
        for player, hands in ((0, self.config.p0_range), (1, self.config.p1_range)):
            for hand in hands:
                cards = hand.canonical_cards()
                for history in player_histories(self.config, player):
                    actions = legal_actions(self.config, history)
                    key: PolicyKey = (player, cards, history)
                    node = self.nodes.get(key)
                    if node is None:
                        p = 1.0 / len(actions)
                        strategies[key] = (p,) * len(actions)
                    else:
                        strategies[key] = node.average_strategy()
        return RiverMultiSizeOneRaisePolicy(strategies)


def _deal_value(
    config: RiverMultiSizeOneRaiseConfig,
    policy0: RiverMultiSizeOneRaisePolicy,
    policy1: RiverMultiSizeOneRaisePolicy,
    deal: MultiSizeOneRaiseDeal,
    history: History = (),
) -> float:
    if is_terminal(config, history):
        return terminal_utility_p0(config, deal, history)
    player = player_to_act(config, history)
    policy = policy0 if player == 0 else policy1
    cards = deal.p0_cards if player == 0 else deal.p1_cards
    strategy = policy.strategy(config, player, cards, history)
    actions = legal_actions(config, history)
    return sum(
        strategy[index]
        * _deal_value(config, policy0, policy1, deal, history + (action,))
        for index, action in enumerate(actions)
    )


def expected_value(
    config: RiverMultiSizeOneRaiseConfig,
    policy0: RiverMultiSizeOneRaisePolicy,
    policy1: RiverMultiSizeOneRaisePolicy,
) -> float:
    config.validate()
    return sum(
        deal.probability * _deal_value(config, policy0, policy1, deal)
        for deal in config.compatible_deals()
    )


def uniform_policy(
    config: RiverMultiSizeOneRaiseConfig,
) -> RiverMultiSizeOneRaisePolicy:
    config.validate()
    strategies: dict[PolicyKey, tuple[float, ...]] = {}
    for player, hands in ((0, config.p0_range), (1, config.p1_range)):
        for hand in hands:
            cards = hand.canonical_cards()
            for history in player_histories(config, player):
                count = len(legal_actions(config, history))
                p = 1.0 / count
                strategies[(player, cards, history)] = (p,) * count
    return RiverMultiSizeOneRaisePolicy(strategies)


def _deal_value_against_pure_hand_response(
    config: RiverMultiSizeOneRaiseConfig,
    fixed_opponent: RiverMultiSizeOneRaisePolicy,
    deal: MultiSizeOneRaiseDeal,
    br_player: int,
    choices: Mapping[History, int],
    history: History = (),
) -> float:
    if is_terminal(config, history):
        return terminal_utility_p0(config, deal, history)
    player = player_to_act(config, history)
    actions = legal_actions(config, history)
    if player == br_player:
        try:
            index = choices[history]
        except KeyError as exc:
            raise RiverMultiSizeOneRaiseError(
                f"best-response choice missing history {history!r}"
            ) from exc
        if index < 0 or index >= len(actions):
            raise RiverMultiSizeOneRaiseError(
                "best-response action index outside legal actions"
            )
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


def pure_plans_for_player(
    config: RiverMultiSizeOneRaiseConfig,
    player: int,
) -> tuple[dict[History, int], ...]:
    histories = player_histories(config, player)
    ranges = [range(len(legal_actions(config, history))) for history in histories]
    return tuple(dict(zip(histories, choices)) for choices in product(*ranges))


def best_response_value_player0(
    config: RiverMultiSizeOneRaiseConfig,
    opponent: RiverMultiSizeOneRaisePolicy,
) -> float:
    config.validate()
    deals = config.compatible_deals()
    plans = pure_plans_for_player(config, 0)
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
    config: RiverMultiSizeOneRaiseConfig,
    opponent: RiverMultiSizeOneRaisePolicy,
) -> float:
    """Minimum P0 utility achievable by P1's exact best response."""
    config.validate()
    deals = config.compatible_deals()
    plans = pure_plans_for_player(config, 1)
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
    config: RiverMultiSizeOneRaiseConfig,
    policy: RiverMultiSizeOneRaisePolicy,
) -> float:
    """Exact half-NashConv in configured chip units/hand."""
    br0 = best_response_value_player0(config, policy)
    br1_as_p0 = best_response_value_player1(config, policy)
    return (br0 - br1_as_p0) / 2.0
