import itertools
import unittest
from dataclasses import replace

from deepsix_core.cards import SUITS, decode_card, encode_card, parse_card
from deepsix_core.canonical import canonicalize_observation
from deepsix_core.state import (
    ActionEvent,
    ActionKind,
    SCHEMA_VERSION,
    SeatObservation,
    Street,
    TableObservation,
)


def obs():
    return TableObservation(
        schema_version=SCHEMA_VERSION,
        hand_id="H1",
        observation_seq=1,
        source_timestamp_ms=1,
        street=Street.TURN,
        dealer_seat=5,
        hero_seat=2,
        hero_cards=(parse_card("Ah"), parse_card("Ks")),
        board=(parse_card("Qc"), parse_card("Jd"), parse_card("9h"), parse_card("6s")),
        seats=(
            SeatObservation(2, True, False, False, 90, 10, 20),
            SeatObservation(5, True, False, False, 80, 20, 30),
            SeatObservation(0, False, False, False, 100, 0, 0),
        ),
        actions=(
            ActionEvent(1, Street.PREFLOP, 2, ActionKind.CALL),
            ActionEvent(2, Street.PREFLOP, 5, ActionKind.CHECK),
        ),
        ante=10,
        pot=50,
        to_call=10,
        min_raise_to=30,
        max_raise_to=100,
    )


def permute_suits(card, permutation):
    decoded = decode_card(card)
    old = SUITS.index(decoded.suit)
    return encode_card(decoded.rank, SUITS[permutation[old]])


class CanonicalizationTests(unittest.TestCase):
    def test_hole_and_flop_order_do_not_matter(self):
        base = obs()
        changed = replace(
            base,
            hero_cards=tuple(reversed(base.hero_cards)),
            board=(base.board[2], base.board[0], base.board[1], base.board[3]),
        )
        self.assertEqual(
            canonicalize_observation(base).fingerprint(),
            canonicalize_observation(changed).fingerprint(),
        )

    def test_all_24_global_suit_permutations_are_identical(self):
        base = obs()
        expected = canonicalize_observation(base).fingerprint()
        for permutation in itertools.permutations(range(4)):
            changed = replace(
                base,
                hero_cards=tuple(permute_suits(c, permutation) for c in base.hero_cards),
                board=tuple(permute_suits(c, permutation) for c in base.board),
            )
            self.assertEqual(canonicalize_observation(changed).fingerprint(), expected)

    def test_physical_chair_rotation_and_waiting_seat_do_not_matter(self):
        base = obs()

        def rotate(seat):
            return (seat + 2) % 6

        changed = replace(
            base,
            dealer_seat=rotate(base.dealer_seat),
            hero_seat=rotate(base.hero_seat),
            seats=tuple(replace(s, seat=rotate(s.seat)) for s in base.seats),
            actions=tuple(replace(a, actor_seat=rotate(a.actor_seat)) for a in base.actions),
        )
        self.assertEqual(
            canonicalize_observation(base).fingerprint(),
            canonicalize_observation(changed).fingerprint(),
        )

    def test_turn_and_river_are_not_permutation_invariant(self):
        base = replace(obs(), street=Street.RIVER, board=obs().board + (parse_card("7c"),))
        swapped = replace(base, board=base.board[:3] + (base.board[4], base.board[3]))
        self.assertNotEqual(
            canonicalize_observation(base).fingerprint(),
            canonicalize_observation(swapped).fingerprint(),
        )

    def test_action_size_difference_remains_distinct(self):
        base = obs()
        changed = replace(base, min_raise_to=31)
        self.assertNotEqual(
            canonicalize_observation(base).fingerprint(),
            canonicalize_observation(changed).fingerprint(),
        )


if __name__ == "__main__":
    unittest.main()
