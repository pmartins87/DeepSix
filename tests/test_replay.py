import json
import unittest
from dataclasses import replace

from deepsix_core.cards import parse_card
from deepsix_core.replay import DecisionToken, ReplayFrame, ReplayIntegrityError
from deepsix_core.state import SCHEMA_VERSION, SeatObservation, Street, TableObservation


def observation():
    return TableObservation(
        schema_version=SCHEMA_VERSION,
        hand_id="H-REPLAY-1",
        observation_seq=17,
        source_timestamp_ms=123456789,
        street=Street.FLOP,
        dealer_seat=0,
        hero_seat=1,
        hero_cards=(parse_card("Ah"), parse_card("Ks")),
        board=(parse_card("Qc"), parse_card("Jd"), parse_card("9h")),
        seats=(
            SeatObservation(0, True, False, False, 80, 20, 30),
            SeatObservation(1, True, False, False, 90, 10, 20),
        ),
        actions=(),
        ante=10,
        pot=50,
        to_call=10,
        min_raise_to=30,
        max_raise_to=100,
    )


class ReplayTests(unittest.TestCase):
    def test_round_trip_verifies(self):
        frame = ReplayFrame.capture(observation())
        recovered = ReplayFrame.from_json(frame.to_json())
        self.assertEqual(recovered, frame)
        recovered.verify()

    def test_decision_token_accepts_transport_only_rescrape(self):
        base = observation()
        token = DecisionToken.capture(base)
        rescrape = replace(base, observation_seq=18, source_timestamp_ms=123456999)
        self.assertTrue(token.matches(rescrape))

    def test_decision_token_rejects_changed_state_or_hand(self):
        base = observation()
        token = DecisionToken.capture(base)
        self.assertFalse(token.matches(replace(base, pot=51)))
        self.assertFalse(token.matches(replace(base, hand_id="H-REPLAY-2")))

    def test_tampering_is_detected(self):
        frame = ReplayFrame.capture(observation())
        data = json.loads(frame.to_json())
        data["observation"]["pot"] += 1
        with self.assertRaises(ReplayIntegrityError):
            ReplayFrame.from_json(json.dumps(data))


if __name__ == "__main__":
    unittest.main()
