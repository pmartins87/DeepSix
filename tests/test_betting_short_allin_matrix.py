import itertools
import unittest

from deepsix_core.betting import (
    BettingConfig,
    BettingPlayer,
    ShortAllInReopenPolicy,
    apply_action,
    legal_actions,
    start_betting_round,
)
from deepsix_core.state import ActionKind, Street


class CumulativeShortAllInMatrixTests(unittest.TestCase):
    def test_every_generated_short_allin_chain_reopens_exactly_at_full_increment(self):
        """Exhaustively stress cumulative reopen across 2..6-player rounds.

        Seat 0 first makes a full opening bet/raise of B. One to four following
        seats then make exact all-in raises whose *individual* increments are all
        below B. A final deep-stacked seat calls, returning action to seat 0.

        Under the simulator v1 CUMULATIVE_FULL_RAISE rule, seat 0 must regain
        raise rights iff the sum of the intervening short increments reaches B.
        """

        cases = 0
        for full_increment in range(2, 11):
            short_increments = range(1, full_increment)
            for short_count in range(1, 5):
                for increments in itertools.product(
                    short_increments,
                    repeat=short_count,
                ):
                    cumulative = 0
                    players = [BettingPlayer(0, stack=1000, committed_street=0)]
                    for seat, increment in enumerate(increments, start=1):
                        cumulative += increment
                        # With zero starting commitment, this stack makes the
                        # desired raise target the seat's exact all-in target.
                        players.append(
                            BettingPlayer(
                                seat,
                                stack=full_increment + cumulative,
                                committed_street=0,
                            )
                        )
                    final_seat = short_count + 1
                    players.append(
                        BettingPlayer(final_seat, stack=1000, committed_street=0)
                    )

                    state = start_betting_round(
                        street=Street.FLOP,
                        players=tuple(players),
                        initial_full_raise_increment=full_increment,
                        config=BettingConfig(
                            short_all_in_reopen=(
                                ShortAllInReopenPolicy.CUMULATIVE_FULL_RAISE
                            )
                        ),
                    )
                    state = apply_action(
                        state,
                        ActionKind.RAISE_TO,
                        full_increment,
                    )

                    running = 0
                    for increment in increments:
                        running += increment
                        target = full_increment + running
                        legal = legal_actions(state)
                        self.assertTrue(legal.can_raise)
                        self.assertEqual(legal.min_raise_to, target)
                        self.assertEqual(legal.max_raise_to, target)
                        state = apply_action(state, ActionKind.RAISE_TO, target)

                    self.assertEqual(state.next_actor, final_seat)
                    state = apply_action(state, ActionKind.CALL)
                    self.assertEqual(state.next_actor, 0)

                    legal = legal_actions(state)
                    expected_reopen = sum(increments) >= full_increment
                    self.assertEqual(
                        legal.raise_right_open,
                        expected_reopen,
                        msg=(
                            f"B={full_increment}, increments={increments}, "
                            f"current_bet={state.current_bet}"
                        ),
                    )
                    self.assertEqual(legal.can_raise, expected_reopen)
                    if expected_reopen:
                        self.assertEqual(
                            legal.min_raise_to,
                            state.current_bet + full_increment,
                        )
                    cases += 1

        self.assertEqual(cases, 17688)


if __name__ == "__main__":
    unittest.main()
