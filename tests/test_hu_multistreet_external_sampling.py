import json
import unittest
from fractions import Fraction

from deepsix_core.cards import parse_card
from deepsix_trainer.hu_multistreet_external_sampling import (
    HuMultiStreetExternalSamplingMCCFR,
    hu_external_sampling_game_fingerprint,
)
from deepsix_trainer.hu_multistreet_reference import HuMicrogameConfig, HuReferenceMicrogame
from deepsix_trainer.reach import PrivateReachVector


def cards(*texts):
    return tuple(parse_card(text) for text in texts)


def game(*, flop=("6c", "7d", "8h")):
    return HuReferenceMicrogame(
        HuMicrogameConfig(
            stake_cents=25,
            dealer_seat=0,
            stacks=((0, 51), (1, 51)),
            flop=cards(*flop),
            bbj_enabled=False,
        ),
        (
            PrivateReachVector.from_mapping(0, {cards("As", "Ks"): 1}),
            PrivateReachVector.from_mapping(1, {cards("Qc", "Jc"): 1}),
        ),
    )


class HuMultiStreetExternalSamplingTests(unittest.TestCase):
    def test_same_seed_is_exactly_deterministic(self):
        left = HuMultiStreetExternalSamplingMCCFR(game(), seed=1234)
        right = HuMultiStreetExternalSamplingMCCFR(game(), seed=1234)
        left.train(12)
        right.train(12)
        self.assertEqual(left.state_dict(), right.state_dict())
        self.assertEqual(left.checkpoint_sha256(), right.checkpoint_sha256())
        self.assertEqual(
            left.average_policy().fingerprint(),
            right.average_policy().fingerprint(),
        )

    def test_split_training_matches_single_run(self):
        split = HuMultiStreetExternalSamplingMCCFR(game(), seed=991)
        single = HuMultiStreetExternalSamplingMCCFR(game(), seed=991)
        split.train(5)
        split.train(7)
        single.train(12)
        self.assertEqual(split.state_dict(), single.state_dict())
        self.assertEqual(split.checkpoint_sha256(), single.checkpoint_sha256())

    def test_checkpoint_resume_matches_uninterrupted_run(self):
        cfg = game()
        interrupted = HuMultiStreetExternalSamplingMCCFR(cfg, seed=8080)
        uninterrupted = HuMultiStreetExternalSamplingMCCFR(cfg, seed=8080)
        interrupted.train(5)
        restored = HuMultiStreetExternalSamplingMCCFR.from_checkpoint_json(
            cfg,
            interrupted.checkpoint_json(),
        )
        restored.train(7)
        uninterrupted.train(12)
        self.assertEqual(restored.state_dict(), uninterrupted.state_dict())
        self.assertEqual(
            restored.average_policy().fingerprint(),
            uninterrupted.average_policy().fingerprint(),
        )

    def test_checkpoint_is_bound_to_exact_game(self):
        original = game()
        altered = game(flop=("6c", "7d", "9h"))
        self.assertNotEqual(
            hu_external_sampling_game_fingerprint(original),
            hu_external_sampling_game_fingerprint(altered),
        )
        trainer = HuMultiStreetExternalSamplingMCCFR(original, seed=44)
        trainer.train(3)
        with self.assertRaises(ValueError):
            HuMultiStreetExternalSamplingMCCFR.from_checkpoint_json(
                altered,
                trainer.checkpoint_json(),
            )

    def test_checkpoint_tampering_and_malformed_nodes_are_rejected(self):
        cfg = game()
        trainer = HuMultiStreetExternalSamplingMCCFR(cfg, seed=55)
        trainer.train(3)

        payload = json.loads(trainer.checkpoint_json())
        payload["sampled_deals"] += 1
        with self.assertRaises(ValueError):
            HuMultiStreetExternalSamplingMCCFR.from_state_dict(cfg, payload)

        payload = json.loads(trainer.checkpoint_json())
        payload["nodes"][0]["actions"] = ["check", "check"]
        with self.assertRaises(ValueError):
            HuMultiStreetExternalSamplingMCCFR.from_state_dict(cfg, payload)

    def test_sampling_visits_all_required_stochastic_axes_and_policy_normalizes(self):
        trainer = HuMultiStreetExternalSamplingMCCFR(game(), seed=20260827)
        trainer.train(10)
        stats = trainer.stats()
        self.assertEqual(stats.iterations, 10)
        self.assertEqual(stats.sampled_deals, 10)
        self.assertGreater(stats.sampled_public_chance, 0)
        self.assertGreater(stats.sampled_opponent_actions, 0)
        self.assertGreater(stats.sampled_average_target_actions, 0)
        self.assertGreater(stats.regret_nodes_visited, 0)
        self.assertGreater(stats.average_nodes_visited, 0)
        self.assertTrue(trainer.all_regrets_finite())
        self.assertGreater(len(trainer.nodes), 0)

        exact_policy = trainer.average_policy().to_exact_policy()
        for row in exact_policy.rows.values():
            self.assertEqual(sum(row.probabilities, Fraction(0, 1)), Fraction(1, 1))

    def test_invalid_seed_and_iterations_are_rejected(self):
        with self.assertRaises(ValueError):
            HuMultiStreetExternalSamplingMCCFR(game(), seed=-1)
        trainer = HuMultiStreetExternalSamplingMCCFR(game())
        with self.assertRaises(ValueError):
            trainer.train(0)


if __name__ == "__main__":
    unittest.main()
