import json
import unittest

from deepsix_core.raw_snapshot import (
    RAW_MYTURN_ALLOWED_MASK,
    RAW_MYTURN_CALL,
    RAW_MYTURN_FOLD,
    RAW_MYTURN_RAISE,
    RawSnapshotError,
    raw_snapshot_from_dict,
    raw_snapshot_from_json,
)


EXPECTED_AUDIT_FINGERPRINT = (
    "01a5c5b35baab7940a696e302ad0bee9d71c7c511f5b431c01765ede694dbe04"
)


def raw_card(*, any_card=False, card_back=False, known=False, rank=-1, suit=-1):
    return {
        "any_card": any_card,
        "card_back": card_back,
        "known": known,
        "openholdem_rank": rank,
        "suit": suit,
    }


def sample_payload():
    board = [raw_card() for _ in range(5)]
    board[0] = raw_card(any_card=True, known=True, rank=6, suit=0)
    board[1] = raw_card(any_card=True, known=True, rank=14, suit=3)
    board[2] = raw_card(any_card=True, known=True, rank=10, suit=1)

    seats = []
    for chair in range(10):
        seats.append(
            {
                "active": False,
                "all_in": False,
                "balance": "0",
                "chair": chair,
                "current_bet": "0",
                "dealer": False,
                "has_any_cards": False,
                "has_known_cards": False,
                "hole_cards": [raw_card(), raw_card()],
                "seated": False,
                "stack_including_current_bet": "0",
            }
        )
    seats[5].update(
        {
            "active": True,
            "balance": "97.5",
            "current_bet": "2",
            "dealer": True,
            "seated": True,
            "stack_including_current_bet": "99.5",
        }
    )

    return {
        "board": board,
        "community_card_count": 3,
        "dealer_chair": 5,
        "hero_chair": -1,
        "hero_myturnbits": RAW_MYTURN_FOLD | RAW_MYTURN_CALL | RAW_MYTURN_RAISE,
        "hero_sitting_in": True,
        "pots": ["12.5"] + ["0"] * 9,
        "schema_version": 2,
        "seats": seats,
    }


class RawSnapshotTests(unittest.TestCase):
    def test_sample_canonical_json_and_fingerprint(self):
        payload = sample_payload()
        snapshot = raw_snapshot_from_dict(payload)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self.assertEqual(snapshot.canonical_json(), canonical)
        self.assertEqual(snapshot.audit_fingerprint(), EXPECTED_AUDIT_FINGERPRINT)
        self.assertEqual(raw_snapshot_from_json(canonical), snapshot)

    def test_observer_mode_hero_is_valid(self):
        snapshot = raw_snapshot_from_dict(sample_payload())
        self.assertEqual(snapshot.hero_chair, -1)

    def test_visible_turn_evidence_is_preserved(self):
        snapshot = raw_snapshot_from_dict(sample_payload())
        self.assertEqual(
            snapshot.hero_myturnbits,
            RAW_MYTURN_FOLD | RAW_MYTURN_CALL | RAW_MYTURN_RAISE,
        )
        self.assertTrue(snapshot.hero_sitting_in)

    def test_unknown_myturn_bit_is_rejected(self):
        payload = sample_payload()
        payload["hero_myturnbits"] = RAW_MYTURN_ALLOWED_MASK | 0x20
        with self.assertRaises(RawSnapshotError):
            raw_snapshot_from_dict(payload)

    def test_removed_rank_rejected(self):
        payload = sample_payload()
        payload["board"][0]["openholdem_rank"] = 5
        with self.assertRaises(RawSnapshotError):
            raw_snapshot_from_dict(payload)

    def test_duplicate_known_card_rejected(self):
        payload = sample_payload()
        payload["seats"][0]["hole_cards"][0] = dict(payload["board"][0])
        with self.assertRaises(RawSnapshotError):
            raw_snapshot_from_dict(payload)

    def test_nonfinite_and_negative_money_rejected(self):
        for bad in ("NaN", "Infinity", "-0.01"):
            payload = sample_payload()
            payload["seats"][0]["balance"] = bad
            with self.subTest(bad=bad), self.assertRaises(RawSnapshotError):
                raw_snapshot_from_dict(payload)

    def test_numeric_money_rejected_to_avoid_float_transport(self):
        payload = sample_payload()
        payload["pots"][0] = 12.5
        with self.assertRaises(RawSnapshotError):
            raw_snapshot_from_dict(payload)

    def test_unknown_card_must_use_minus_one_sentinels(self):
        payload = sample_payload()
        payload["board"][4]["openholdem_rank"] = 6
        with self.assertRaises(RawSnapshotError):
            raw_snapshot_from_dict(payload)

    def test_physical_seat_order_must_match_chair_index(self):
        payload = sample_payload()
        payload["seats"][0]["chair"] = 7
        with self.assertRaises(RawSnapshotError):
            raw_snapshot_from_dict(payload)

    def test_board_count_boundary_rejected(self):
        payload = sample_payload()
        payload["community_card_count"] = 2
        with self.assertRaises(RawSnapshotError):
            raw_snapshot_from_dict(payload)

    def test_old_schema_is_rejected(self):
        payload = sample_payload()
        payload["schema_version"] = 1
        with self.assertRaises(RawSnapshotError):
            raw_snapshot_from_dict(payload)


if __name__ == "__main__":
    unittest.main()
