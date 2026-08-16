import copy
import json
import unittest

from deepsix_core.raw_pipeline import RawObservationPipeline, RawPipelineError
from deepsix_core.raw_reconstructor import ChairLayout, MoneyScale
from deepsix_core.raw_timeline import TimelineEventKind
from deepsix_core.state import ActionKind


def raw_card(*, any_card=False, card_back=False, known=False, rank=-1, suit=-1):
    return {
        "any_card": any_card,
        "card_back": card_back,
        "known": known,
        "openholdem_rank": rank,
        "suit": suit,
    }


def baseline_payload():
    chairs = (2, 5, 8)
    dealer = 5
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
    for chair in chairs:
        forced = "0.2" if chair == dealer else "0.1"
        balance = "9.8" if chair == dealer else "9.9"
        seats[chair].update(
            {
                "active": True,
                "balance": balance,
                "current_bet": forced,
                "has_any_cards": True,
                "hole_cards": [
                    raw_card(any_card=True, card_back=True),
                    raw_card(any_card=True, card_back=True),
                ],
                "seated": True,
                "stack_including_current_bet": "10.0",
            }
        )
    return {
        "board": [raw_card() for _ in range(5)],
        "community_card_count": 0,
        "dealer_chair": dealer,
        "hero_chair": 2,
        "hero_myturnbits": 0,
        "hero_sitting_in": True,
        "pots": ["0.4"] + ["0"] * 9,
        "schema_version": 2,
        "seats": seats,
    }


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class RawObservationPipelineTests(unittest.TestCase):
    def pipeline(self):
        return RawObservationPipeline(
            layout=ChairLayout((2, 5, 8)),
            money_scale=MoneyScale("0.1"),
            required_identical=2,
            ante_units=1,
        )

    def test_two_identical_raw_frames_prove_hand_start_end_to_end(self):
        pipeline = self.pipeline()
        text = canonical(baseline_payload())
        self.assertIsNone(pipeline.push_json(text))
        event = pipeline.push_json(text)
        self.assertIsNotNone(event)
        self.assertEqual(event.kind, TimelineEventKind.HAND_START)
        self.assertEqual(event.hand_index, 0)
        self.assertTrue(pipeline.timeline.complete_from_hand_start)

    def test_changed_frame_must_stabilize_before_exact_call_is_emitted(self):
        pipeline = self.pipeline()
        start = canonical(baseline_payload())
        pipeline.push_json(start)
        self.assertEqual(pipeline.push_json(start).kind, TimelineEventKind.HAND_START)

        called = copy.deepcopy(baseline_payload())
        called["seats"][2]["balance"] = "9.8"
        called["seats"][2]["current_bet"] = "0.2"
        # stack including current bet stays exactly 10.0.
        called_text = canonical(called)
        self.assertIsNone(pipeline.push_json(called_text))
        event = pipeline.push_json(called_text)
        self.assertEqual(event.kind, TimelineEventKind.ACTION)
        self.assertEqual(event.action.action, ActionKind.CALL)
        self.assertEqual(event.action.paid, 1)
        self.assertEqual(event.action.hand_index, 0)

    def test_transport_only_json_key_order_does_not_break_stability(self):
        pipeline = self.pipeline()
        payload = baseline_payload()
        compact_sorted = canonical(payload)
        normal_order = json.dumps(payload, separators=(",", ":"))
        self.assertIsNone(pipeline.push_json(compact_sorted))
        event = pipeline.push_json(normal_order)
        self.assertEqual(event.kind, TimelineEventKind.HAND_START)

    def test_invalid_raw_json_is_wrapped_as_pipeline_error(self):
        pipeline = self.pipeline()
        with self.assertRaises(RawPipelineError):
            pipeline.push_json("not-json")

    def test_removed_rank_is_rejected_before_projection(self):
        pipeline = self.pipeline()
        payload = baseline_payload()
        payload["board"][0] = raw_card(any_card=True, known=True, rank=5, suit=0)
        payload["community_card_count"] = 3
        payload["board"][1] = raw_card(any_card=True, known=True, rank=6, suit=1)
        payload["board"][2] = raw_card(any_card=True, known=True, rank=7, suit=2)
        with self.assertRaises(RawPipelineError):
            pipeline.push_json(canonical(payload))


if __name__ == "__main__":
    unittest.main()
