import unittest

from deepsix_core.state import ActionKind
from deepsix_simulator import (
    SimulatedHand,
    SimulatorAction,
    SimulatorHandTranscript,
    SimulatorReplayError,
    check_call_policy,
    replay_transcript,
    transcript_from_hand,
)


class SimulatorReplayTests(unittest.TestCase):
    def _settled_checkdown(self):
        hand = SimulatedHand.start(
            hand_id="replay-checkdown",
            stake_cents=25,
            seed=424242,
            dealer_seat=0,
            stacks=((0, 1000), (1, 850), (2, 1200), (4, 777)),
        )
        hand.play_to_terminal({seat: check_call_policy for seat in hand.hole_cards})
        return hand

    def test_transcript_json_roundtrip_and_exact_replay(self):
        hand = self._settled_checkdown()
        transcript = transcript_from_hand(hand)
        encoded = transcript.canonical_json()
        decoded = SimulatorHandTranscript.from_json(encoded)
        self.assertEqual(decoded, transcript)
        self.assertEqual(decoded.fingerprint(), transcript.fingerprint())

        replayed = replay_transcript(decoded)
        self.assertEqual(replayed.hole_cards, hand.hole_cards)
        self.assertEqual(replayed.state.board, hand.state.board)
        self.assertEqual(replayed.state.actions, hand.state.actions)
        self.assertEqual(replayed.settlement, hand.settlement)

    def test_seed_tamper_is_detected_by_private_or_settlement_digest(self):
        hand = self._settled_checkdown()
        transcript = transcript_from_hand(hand)
        payload = transcript.to_dict()
        payload["seed"] += 1
        tampered = SimulatorHandTranscript.from_dict(payload)
        with self.assertRaises(SimulatorReplayError):
            replay_transcript(tampered)

    def test_decision_actor_tamper_fails_before_action(self):
        hand = self._settled_checkdown()
        transcript = transcript_from_hand(hand)
        payload = transcript.to_dict()
        self.assertTrue(payload["decisions"])
        first = payload["decisions"][0]
        seats = [seat for seat, _ in transcript.starting_stacks]
        first["actor_seat"] = next(seat for seat in seats if seat != first["actor_seat"])
        tampered = SimulatorHandTranscript.from_dict(payload)
        with self.assertRaises(SimulatorReplayError):
            replay_transcript(tampered)

    def test_preflop_fold_transcript_has_no_board_and_replays(self):
        hand = SimulatedHand.start(
            hand_id="preflop-fold",
            stake_cents=25,
            seed=11,
            dealer_seat=0,
            stacks=((0, 1000), (1, 1000)),
        )
        actor = hand.actor_seat
        self.assertIsNotNone(actor)
        hand.act(actor, SimulatorAction(ActionKind.FOLD))
        self.assertTrue(hand.terminal)
        transcript = transcript_from_hand(hand)
        self.assertEqual(transcript.final_board, ())
        replayed = replay_transcript(transcript)
        self.assertEqual(replayed.settlement, hand.settlement)


if __name__ == "__main__":
    unittest.main()
