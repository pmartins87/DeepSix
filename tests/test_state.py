import unittest
from dataclasses import replace

from deepsix_core.cards import parse_card
from deepsix_core.state import (
    ActionEvent,
    ActionKind,
    ObservationError,
    SCHEMA_VERSION,
    SeatObservation,
    Street,
    TableObservation,
)


def sample_observation():
    return TableObservation(
        schema_version=SCHEMA_VERSION,
        hand_id="H1",
        observation_seq=7,
        source_timestamp_ms=123456,
        street=Street.FLOP,
        dealer_seat=5,
        hero_seat=2,
        hero_cards=(parse_card("Ah"), parse_card("Ks")),
        board=(parse_card("Qc"), parse_card("Jd"), parse_card("9h")),
        seats=(
            SeatObservation(2, True, False, False, 90, 10, 10),
            SeatObservation(5, True, False, False, 80, 20, 20),
        ),
        actions=(
            ActionEvent(1, Street.PREFLOP, 2, ActionKind.CALL),
            ActionEvent(2, Street.PREFLOP, 5, ActionKind.CHECK),
        ),
        ante=10,
        pot=40,
        to_call=0,
        min_raise_to=10,
        max_raise_to=90,
    )


class ObservationContractTests(unittest.TestCase):
    def test_sample_is_valid_and_fingerprints_are_deterministic(self):
        obs = sample_observation()
        obs.validate()
        self.assertEqual(obs.semantic_fingerprint(), obs.semantic_fingerprint())
        self.assertEqual(obs.observation_fingerprint(), obs.observation_fingerprint())

    def test_transport_metadata_does_not_change_semantic_fingerprint(self):
        obs = sample_observation()
        changed = replace(
            obs, hand_id="H2", observation_seq=99, source_timestamp_ms=999999
        )
        self.assertEqual(obs.semantic_fingerprint(), changed.semantic_fingerprint())
        self.assertNotEqual(obs.observation_fingerprint(), changed.observation_fingerprint())

    def test_game_state_change_changes_semantic_fingerprint(self):
        obs = sample_observation()
        changed = replace(obs, pot=41)
        self.assertNotEqual(obs.semantic_fingerprint(), changed.semantic_fingerprint())

    def test_wrong_board_count_is_rejected(self):
        obs = sample_observation()
        with self.assertRaises(ObservationError):
            replace(obs, street=Street.TURN).validate()

    def test_duplicate_known_card_is_rejected(self):
        obs = sample_observation()
        with self.assertRaises(ObservationError):
            replace(obs, board=(obs.hero_cards[0],) + obs.board[1:]).validate()

    def test_action_sequence_must_be_monotonic(self):
        obs = sample_observation()
        bad = replace(
            obs,
            actions=(
                ActionEvent(2, Street.PREFLOP, 2, ActionKind.CALL),
                ActionEvent(2, Street.PREFLOP, 5, ActionKind.CHECK),
            ),
        )
        with self.assertRaises(ObservationError):
            bad.validate()


if __name__ == "__main__":
    unittest.main()
