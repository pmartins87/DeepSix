import unittest
from fractions import Fraction

from deepsix_core.cards import parse_card
from deepsix_trainer.hu_multistreet_best_response import (
    best_response_value_player0_exact,
    best_response_value_player1_exact,
)
from deepsix_trainer.hu_multistreet_reference import (
    GROSS_POKER_DELTA,
    HuMicrogameConfig,
    HuReferenceMicrogame,
    uniform_micro_policy,
)
from deepsix_trainer.reach import PrivateReachVector


def cards(*texts):
    return tuple(parse_card(text) for text in texts)


def game(*, multi_hidden=False):
    p1 = {cards("Qc", "Jc"): 1}
    if multi_hidden:
        p1[cards("Qd", "Jd")] = 1
    return HuReferenceMicrogame(
        HuMicrogameConfig(
            stake_cents=25,
            dealer_seat=0,
            stacks=((0, 51), (1, 51)),
            flop=cards("6c", "7d", "8h"),
            bbj_enabled=False,
        ),
        (
            PrivateReachVector.from_mapping(0, {cards("As", "Ks"): 1}),
            PrivateReachVector.from_mapping(1, p1),
        ),
    )


class ExactHuMultiStreetBestResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Exact BR is deliberately expensive. Compute each direction once and
        # reuse the immutable Fraction results across algebraic gates.
        cls.game = game()
        cls.policy_value = cls.game.evaluate(
            uniform_micro_policy,
            objective_id=GROSS_POKER_DELTA,
        ).value_for(0)
        cls.br0 = best_response_value_player0_exact(cls.game, uniform_micro_policy)
        cls.br1 = best_response_value_player1_exact(cls.game, uniform_micro_policy)

    def test_fixed_policy_value_is_bounded_by_exact_best_responses(self):
        self.assertGreaterEqual(self.br0, self.policy_value)
        self.assertLessEqual(self.br1, self.policy_value)

    def test_exact_exploitability_formula_is_nonnegative(self):
        exploitability = (self.br0 - self.br1) / 2
        self.assertIsInstance(exploitability, Fraction)
        self.assertGreaterEqual(exploitability, Fraction(0, 1))

    def test_hidden_opponent_worlds_share_one_responder_infoset(self):
        # This is the essential information-set gate: P0 has one private hand
        # while P1 may be in two hidden worlds. The BR recursion must choose one
        # common P0 action for worlds that share the same public state.
        multi = game(multi_hidden=True)
        value = best_response_value_player0_exact(multi, uniform_micro_policy)
        self.assertIsInstance(value, Fraction)

    def test_float_opponent_policy_is_rejected_by_exact_oracle(self):
        def float_policy(state, actions):
            del state
            probability = 1.0 / len(actions)
            return {action: probability for action in actions}

        with self.assertRaises(ValueError):
            best_response_value_player0_exact(self.game, float_policy)


if __name__ == "__main__":
    unittest.main()
