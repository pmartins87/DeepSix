import copy
import unittest

from deepsix_core.cards import parse_card
from deepsix_core.raw_reconstructor import (
    ChairLayout,
    MoneyScale,
    RawTransitionKind,
    ReconstructionError,
    StableSnapshotGate,
    classify_raw_transition,
    project_raw_snapshot,
)
from deepsix_core.raw_snapshot import (
    RAW_MYTURN_CALL,
    RAW_MYTURN_CHECK,
    RAW_MYTURN_FOLD,
    RAW_MYTURN_RAISE,
    raw_snapshot_from_dict,
)
from deepsix_core.state import Street


def raw_card(*, any_card=False, card_back=False, known=False, rank=-1, suit=-1):
    return {
        "any_card": any_card,
        "card_back": card_back,
        "known": known,
        "openholdem_rank": rank,
        "suit": suit,
    }


def payload(
    *,
    board=(),
    dealer=5,
    hero=2,
    hero_myturnbits=0,
    hero_sitting_in=True,
):
    raw_board = [raw_card() for _ in range(5)]
    for index, (rank, suit) in enumerate(board):
        raw_board[index] = raw_card(any_card=True, known=True, rank=rank, suit=suit)
    seats = []
    for chair in range(10):
        seats.append(
            {
                "active": False,
                "all_in": False,
                "balance": "0",
                "chair": chair,
                "current_bet": "0",
                "dealer": chair == dealer,
                "has_any_cards": False,
                "has_known_cards": False,
                "hole_cards": [raw_card(), raw_card()],
                "seated": False,
                "stack_including_current_bet": "0",
            }
        )
    for chair in (2, 5, 8):
        seats[chair].update(
            {
                "active": True,
                "balance": "9.8",
                "current_bet": "0.2",
                "seated": True,
                "stack_including_current_bet": "10.0",
            }
        )
    return {
        "board": raw_board,
        "community_card_count": len(board),
        "dealer_chair": dealer,
        "hero_chair": hero,
        "hero_myturnbits": hero_myturnbits,
        "hero_sitting_in": hero_sitting_in,
        "pots": ["0.8"] + ["0"] * 9,
        "schema_version": 2,
        "seats": seats,
    }


class RawReconstructionBoundaryTests(unittest.TestCase):
    def setUp(self):
        # This mapping is deliberately explicit and non-contiguous: no test
        # assumes that real KKPoker 6+ seats must be raw OH chairs 0..5.
        self.layout = ChairLayout((2, 5, 8))
        self.scale = MoneyScale("0.1")

    def project(self, source):
        return project_raw_snapshot(
            raw_snapshot_from_dict(source),
            layout=self.layout,
            money_scale=self.scale,
        )

    def test_exact_money_scale_rejects_fractional_table_unit(self):
        self.assertEqual(MoneyScale("0.05").to_units("12.50"), 250)
        with self.assertRaises(ReconstructionError):
            MoneyScale("0.02").to_units("0.03")
        with self.assertRaises(ReconstructionError):
            MoneyScale("0").to_units("1")

    def test_explicit_noncontiguous_chair_mapping_and_money_projection(self):
        source = payload(
            hero_myturnbits=RAW_MYTURN_FOLD | RAW_MYTURN_CALL | RAW_MYTURN_RAISE
        )
        source["seats"][2]["hole_cards"] = [
            raw_card(any_card=True, known=True, rank=14, suit=0),
            raw_card(any_card=True, known=True, rank=13, suit=1),
        ]
        source["seats"][2]["has_any_cards"] = True
        source["seats"][2]["has_known_cards"] = True
        projected = self.project(source)
        self.assertEqual(projected.street, Street.PREFLOP)
        self.assertEqual(projected.dealer_seat, 1)
        self.assertEqual(projected.hero_seat, 0)
        self.assertEqual(
            projected.hero_myturnbits,
            RAW_MYTURN_FOLD | RAW_MYTURN_CALL | RAW_MYTURN_RAISE,
        )
        self.assertTrue(projected.hero_sitting_in)
        self.assertEqual(projected.seats[0].raw_chair, 2)
        self.assertEqual(projected.seats[0].balance, 98)
        self.assertEqual(projected.seats[0].current_bet, 2)
        self.assertEqual(projected.seats[0].stack_including_current_bet, 100)
        self.assertEqual(projected.pots[0], 8)
        self.assertEqual(
            projected.seats[0].hole_cards,
            (parse_card("Ac"), parse_card("Kd")),
        )

    def test_unmapped_dealer_or_hero_is_rejected(self):
        with self.assertRaises(ReconstructionError):
            self.project(payload(dealer=4))
        with self.assertRaises(ReconstructionError):
            self.project(payload(hero=4))

    def test_observer_mode_hero_maps_to_none_and_preserves_sitting_state(self):
        projected = self.project(payload(hero=-1, hero_sitting_in=False))
        self.assertIsNone(projected.hero_seat)
        self.assertFalse(projected.hero_sitting_in)

    def test_board_count_requires_known_revealed_cards(self):
        source = payload(board=((6, 0), (7, 1), (8, 2)))
        source["board"][1] = raw_card()
        with self.assertRaises(ReconstructionError):
            self.project(source)

    def test_same_street_money_delta_is_not_invented_as_action(self):
        first = self.project(payload())
        second_source = payload()
        second_source["seats"][2]["balance"] = "9.4"
        second_source["seats"][2]["current_bet"] = "0.6"
        second = self.project(second_source)
        transition = classify_raw_transition(first, second)
        self.assertEqual(transition.kind, RawTransitionKind.SAME_STREET_DELTA)
        self.assertNotIn("raise", transition.reason.lower())
        self.assertNotIn("call", transition.reason.lower())

    def test_visible_button_delta_is_raw_evidence_not_inferred_action(self):
        first = self.project(payload(hero_myturnbits=0))
        second = self.project(
            payload(hero_myturnbits=RAW_MYTURN_CHECK | RAW_MYTURN_RAISE)
        )
        transition = classify_raw_transition(first, second)
        self.assertEqual(transition.kind, RawTransitionKind.SAME_STREET_DELTA)
        self.assertEqual(
            second.hero_myturnbits,
            RAW_MYTURN_CHECK | RAW_MYTURN_RAISE,
        )
        self.assertNotIn("bet", transition.reason.lower())
        self.assertNotIn("raise", transition.reason.lower())
        self.assertNotIn("check", transition.reason.lower())

    def test_exact_forward_street_preserves_board_prefix(self):
        preflop = self.project(payload())
        flop = self.project(payload(board=((6, 0), (7, 1), (8, 2))))
        self.assertEqual(
            classify_raw_transition(preflop, flop).kind,
            RawTransitionKind.FORWARD_STREET,
        )
        turn = self.project(payload(board=((6, 0), (7, 1), (8, 2), (9, 3))))
        self.assertEqual(
            classify_raw_transition(flop, turn).kind,
            RawTransitionKind.FORWARD_STREET,
        )

    def test_mutated_same_street_board_is_ambiguous(self):
        first = self.project(payload(board=((6, 0), (7, 1), (8, 2))))
        second = self.project(payload(board=((6, 0), (7, 1), (9, 2))))
        self.assertEqual(
            classify_raw_transition(first, second).kind,
            RawTransitionKind.AMBIGUOUS,
        )

    def test_board_reset_is_only_hand_boundary_candidate(self):
        river = self.project(
            payload(board=((6, 0), (7, 1), (8, 2), (9, 3), (10, 0)))
        )
        preflop = self.project(payload())
        transition = classify_raw_transition(river, preflop)
        self.assertEqual(transition.kind, RawTransitionKind.HAND_BOUNDARY_CANDIDATE)
        self.assertIn("confirmation", transition.reason)

    def test_dealer_change_inside_same_street_is_ambiguous(self):
        first = self.project(payload(dealer=5))
        second = self.project(payload(dealer=8))
        self.assertEqual(
            classify_raw_transition(first, second).kind,
            RawTransitionKind.AMBIGUOUS,
        )

    def test_stability_gate_needs_two_identical_frames_and_resets_on_change(self):
        gate = StableSnapshotGate(required_identical=2)
        a = self.project(payload())
        self.assertIsNone(gate.push(a))
        emitted = gate.push(a)
        self.assertIsNotNone(emitted)
        self.assertIsNone(gate.push(a))

        changed_source = copy.deepcopy(payload())
        changed_source["seats"][2]["balance"] = "9.7"
        changed_source["seats"][2]["current_bet"] = "0.3"
        b = self.project(changed_source)
        self.assertIsNone(gate.push(b))
        self.assertEqual(gate.push(b), b)

    def test_stability_gate_requires_visible_turn_bits_to_stabilize(self):
        gate = StableSnapshotGate(required_identical=2)
        no_turn = self.project(payload(hero_myturnbits=0))
        hero_turn = self.project(
            payload(hero_myturnbits=RAW_MYTURN_FOLD | RAW_MYTURN_CALL)
        )
        self.assertIsNone(gate.push(no_turn))
        self.assertIsNone(gate.push(hero_turn))
        self.assertEqual(gate.push(hero_turn), hero_turn)


if __name__ == "__main__":
    unittest.main()
