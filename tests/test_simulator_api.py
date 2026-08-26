import json
import unittest

from deepsix_core.state import ActionKind
from deepsix_simulator import (
    DeepSixEnv,
    SimulatorAction,
    SimulatorEnvironmentError,
    SimulatorResetConfig,
    observation_canonical_json,
    observation_fingerprint,
    observation_to_dict,
)


class SimulatorApiTests(unittest.TestCase):
    def _env(self):
        return DeepSixEnv(
            SimulatorResetConfig(
                stake_cents=25,
                dealer_seat=0,
                stacks=((0, 1000), (1, 1000), (2, 1000)),
                bbj_enabled=True,
            )
        )

    def test_reset_is_reproducible_for_same_explicit_hand_id(self):
        env = self._env()
        a = env.reset(seed=77, hand_id="same")
        self.assertIsNotNone(a)
        fp_a = observation_fingerprint(a)
        b = env.reset(seed=77, hand_id="same")
        self.assertIsNotNone(b)
        self.assertEqual(fp_a, observation_fingerprint(b))

    def test_observation_wire_format_contains_only_hero_private_cards(self):
        env = self._env()
        obs = env.reset(seed=101, hand_id="wire")
        self.assertIsNotNone(obs)
        payload = observation_to_dict(obs)
        self.assertIn("hero_hole_cards", payload)
        self.assertNotIn("hole_cards", payload)
        self.assertNotIn("opponent_hole_cards", payload)
        encoded = observation_canonical_json(obs)
        self.assertEqual(json.loads(encoded), payload)
        self.assertEqual(len(observation_fingerprint(obs)), 64)

    def test_step_advances_exactly_one_decision(self):
        env = self._env()
        obs = env.reset(seed=9, hand_id="step")
        self.assertIsNotNone(obs)
        actor = obs.actor_seat
        self.assertIsNotNone(actor)
        legal = env.legal_actions(actor)
        decision = (
            SimulatorAction(ActionKind.CHECK)
            if legal.can_check
            else SimulatorAction(ActionKind.CALL)
        )
        result = env.step(decision, seat=actor)
        self.assertEqual(result.acted_seat, actor)
        self.assertEqual(result.decision_index, 0)
        self.assertFalse(result.terminal)
        self.assertIsNotNone(result.next_observation)
        self.assertEqual(result.next_observation.decision_index, 1)

    def test_out_of_turn_legal_and_step_requests_fail_closed(self):
        env = self._env()
        obs = env.reset(seed=9, hand_id="turn")
        actor = obs.actor_seat
        wrong = next(seat for seat, _ in env.config.stacks if seat != actor)
        with self.assertRaises(SimulatorEnvironmentError):
            env.legal_actions(wrong)
        with self.assertRaises(SimulatorEnvironmentError):
            env.step(SimulatorAction(ActionKind.CALL), seat=wrong)

    def test_use_before_reset_is_rejected(self):
        env = self._env()
        with self.assertRaises(SimulatorEnvironmentError):
            env.observe(0)
        with self.assertRaises(SimulatorEnvironmentError):
            env.step(SimulatorAction(ActionKind.CHECK))


if __name__ == "__main__":
    unittest.main()
