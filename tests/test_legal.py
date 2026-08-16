import unittest
from dataclasses import replace

from deepsix_core.cards import parse_card
from deepsix_core.legal import LegalActionError, legal_actions_for_hero
from deepsix_core.state import SCHEMA_VERSION, SeatObservation, Street, TableObservation


def observation(to_call=10, min_raise_to=30, max_raise_to=100, hero_stack=90):
    return TableObservation(
        schema_version=SCHEMA_VERSION,
        hand_id="H",
        observation_seq=1,
        source_timestamp_ms=1,
        street=Street.FLOP,
        dealer_seat=0,
        hero_seat=1,
        hero_cards=(parse_card("Ah"), parse_card("Ks")),
        board=(parse_card("Qc"), parse_card("Jd"), parse_card("9h")),
        seats=(
            SeatObservation(0, True, False, False, 80, 20, 30),
            SeatObservation(1, True, False, False, hero_stack, 10, 20),
        ),
        actions=(),
        ante=10,
        pot=50,
        to_call=to_call,
        min_raise_to=min_raise_to,
        max_raise_to=max_raise_to,
    )


class LegalActionTests(unittest.TestCase):
    def test_facing_bet_exposes_fold_call_raise(self):
        legal = legal_actions_for_hero(observation())
        self.assertTrue(legal.can_fold)
        self.assertFalse(legal.can_check)
        self.assertTrue(legal.can_call)
        self.assertEqual(legal.call_amount, 10)
        self.assertTrue(legal.can_raise)
        self.assertTrue(legal.is_raise_to_legal(30))
        self.assertTrue(legal.is_raise_to_legal(100))
        self.assertFalse(legal.is_raise_to_legal(29))

    def test_check_spot(self):
        legal = legal_actions_for_hero(
            observation(to_call=0, min_raise_to=20, max_raise_to=100)
        )
        self.assertTrue(legal.can_check)
        self.assertFalse(legal.can_fold)
        self.assertFalse(legal.can_call)

    def test_short_stack_call_is_allin_call_not_raise(self):
        legal = legal_actions_for_hero(
            observation(to_call=50, min_raise_to=0, max_raise_to=0, hero_stack=20)
        )
        self.assertEqual(legal.call_amount, 20)
        self.assertTrue(legal.can_call)
        self.assertFalse(legal.can_raise)

    def test_impossible_raise_window_rejected(self):
        with self.assertRaises(LegalActionError):
            legal_actions_for_hero(observation(min_raise_to=15, max_raise_to=100))
        with self.assertRaises(LegalActionError):
            legal_actions_for_hero(observation(min_raise_to=30, max_raise_to=101))

    def test_folded_hero_cannot_receive_policy(self):
        base = observation()
        seats = tuple(
            replace(s, folded=True) if s.seat == 1 else s for s in base.seats
        )
        with self.assertRaises(LegalActionError):
            legal_actions_for_hero(replace(base, seats=seats))


if __name__ == "__main__":
    unittest.main()
