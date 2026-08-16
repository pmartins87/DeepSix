import random
import unittest

from deepsix_core.betting import legal_actions
from deepsix_core.hand import (
    HandConfig,
    HandPhase,
    apply_hand_action,
    deal_next_board,
    fold_winner,
    hand_chip_total,
    start_hand,
)
from deepsix_core.state import ActionKind


class FullHandFuzzTests(unittest.TestCase):
    def test_300_deterministic_random_hands_preserve_invariants(self):
        config = HandConfig(
            ante=2,
            preflop_full_raise_increment=4,
            postflop_min_bet=4,
        )

        for seed in range(300):
            rng = random.Random(seed)
            player_count = rng.randint(2, 6)
            seats = tuple(sorted(rng.sample(range(6), player_count)))
            dealer = rng.choice(seats)
            stacks = tuple((seat, rng.randint(8, 80)) for seat in seats)
            state = start_hand(dealer_seat=dealer, stacks=stacks, config=config)
            initial_total = sum(stack for _, stack in stacks)
            remaining_board_cards = list(range(36))
            rng.shuffle(remaining_board_cards)

            for step in range(250):
                state.validate()
                self.assertEqual(hand_chip_total(state), initial_total)
                self.assertEqual(state.pot(), sum(p.committed_total for p in state.players))

                if state.phase == HandPhase.TERMINAL_FOLD:
                    self.assertIsNotNone(fold_winner(state))
                    break
                if state.phase == HandPhase.SHOWDOWN:
                    self.assertEqual(len(state.board), 5)
                    break

                if state.phase == HandPhase.WAITING_FLOP:
                    cards = tuple(remaining_board_cards.pop() for _ in range(3))
                    state = deal_next_board(state, cards)
                    continue
                if state.phase in (HandPhase.WAITING_TURN, HandPhase.WAITING_RIVER):
                    state = deal_next_board(state, (remaining_board_cards.pop(),))
                    continue

                self.assertEqual(state.phase, HandPhase.BETTING)
                legal = legal_actions(state.betting_round)
                candidates = []
                if legal.can_fold:
                    candidates.append((ActionKind.FOLD, None))
                if legal.can_check:
                    candidates.append((ActionKind.CHECK, None))
                if legal.can_call:
                    candidates.append((ActionKind.CALL, None))
                if legal.can_raise:
                    candidates.append((ActionKind.RAISE_TO, legal.min_raise_to))
                    if legal.max_raise_to != legal.min_raise_to:
                        candidates.append((ActionKind.RAISE_TO, legal.max_raise_to))

                self.assertTrue(candidates)
                action, amount_to = rng.choice(candidates)
                state = apply_hand_action(state, action, amount_to)
            else:
                self.fail(f"seed {seed} did not terminate within 250 transitions")

            state.validate()
            self.assertEqual(hand_chip_total(state), initial_total)
            self.assertIn(state.phase, (HandPhase.TERMINAL_FOLD, HandPhase.SHOWDOWN))


if __name__ == "__main__":
    unittest.main()
