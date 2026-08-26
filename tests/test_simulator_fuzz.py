import random
import unittest

from deepsix_core.state import ActionKind
from deepsix_simulator import (
    SimulatedHand,
    SimulatorAction,
    replay_transcript,
    transcript_from_hand,
)


class DeterministicRandomPolicy:
    def __init__(self, seed):
        self.rng = random.Random(seed)

    def __call__(self, obs):
        legal = obs.legal
        if legal is None:
            raise AssertionError("policy called without legal actions")
        choices = []
        if legal.can_check:
            choices.append(SimulatorAction(ActionKind.CHECK))
        if legal.can_call:
            choices.append(SimulatorAction(ActionKind.CALL))
        if legal.can_fold:
            choices.append(SimulatorAction(ActionKind.FOLD))
        if legal.can_raise:
            choices.append(SimulatorAction(ActionKind.RAISE_TO, legal.min_raise_to))
            if legal.max_raise_to != legal.min_raise_to:
                choices.append(SimulatorAction(ActionKind.RAISE_TO, legal.max_raise_to))
        if not choices:
            raise AssertionError("no legal simulator action")
        return self.rng.choice(choices)


class SimulatorFuzzTests(unittest.TestCase):
    def test_randomized_2_to_6_player_hands_conserve_money_and_replay(self):
        master = random.Random(20260825)
        cases = 0
        for player_count in range(2, 7):
            for local_index in range(12):
                seats = tuple(range(player_count))
                dealer = local_index % player_count
                stacks = tuple(
                    (seat, master.randint(8, 160))
                    for seat in seats
                )
                seed = master.randrange(1, 10_000_000)
                hand = SimulatedHand.start(
                    hand_id=f"fuzz-{player_count}-{local_index}",
                    stake_cents=2,
                    seed=seed,
                    dealer_seat=dealer,
                    stacks=stacks,
                    bbj_enabled=bool(local_index % 2),
                )
                agents = {
                    seat: DeterministicRandomPolicy(seed * 100 + seat)
                    for seat in seats
                }
                settlement = hand.play_to_terminal(agents, max_decisions=250)

                starting_total = sum(stack for _, stack in stacks)
                self.assertEqual(
                    sum(value for _, value in settlement.post_hand_stacks),
                    starting_total - settlement.deductions.total_units,
                )
                self.assertEqual(
                    sum(value for _, value in settlement.gross_awards),
                    settlement.gross_pot_units,
                )
                self.assertEqual(
                    sum(value for _, value in settlement.net_awards),
                    settlement.gross_pot_units - settlement.deductions.total_units,
                )
                # A fold can terminate preflop/flop/turn/river. Showdown always
                # has five cards, but a terminal hand does not need to run unused
                # future streets merely to satisfy a test artifact.
                self.assertIn(len(hand.state.board), (0, 3, 4, 5))

                known_cards = [
                    card
                    for cards in hand.hole_cards.values()
                    for card in cards
                ] + list(hand.state.board)
                self.assertEqual(len(known_cards), len(set(known_cards)))

                if local_index in (0, 7):
                    transcript = transcript_from_hand(hand)
                    replayed = replay_transcript(transcript)
                    self.assertEqual(replayed.settlement, hand.settlement)
                    self.assertEqual(replayed.state.actions, hand.state.actions)
                cases += 1
        self.assertEqual(cases, 60)


if __name__ == "__main__":
    unittest.main()
