import json
import unittest

from deepsix_core.cards import parse_card
from deepsix_trainer.river_external_sampling import (
    RiverExternalSamplingMCCFR,
    external_sampling_config_fingerprint,
)
from deepsix_trainer.river_microgame import RangeHand
from deepsix_trainer.river_multisize_one_raise import RiverMultiSizeOneRaiseError, uniform_policy
from deepsix_trainer.river_multisize_one_raise_dpbr import exploitability_dp
from deepsix_trainer.river_multisize_one_raise_scalable import (
    ScalableRiverMultiSizeOneRaiseConfig,
)


def c(text):
    return parse_card(text)


def config():
    return ScalableRiverMultiSizeOneRaiseConfig(
        board=(c("Ac"), c("Kd"), c("Qs"), c("8d"), c("6s")),
        pot=12,
        bet_sizes=(4, 8),
        raise_to=14,
        p0_range=(
            RangeHand((c("Tc"), c("7d"))),
            RangeHand((c("Kc"), c("9s"))),
            RangeHand((c("Jc"), c("Tc"))),
        ),
        p1_range=(
            RangeHand((c("Th"), c("7s"))),
            RangeHand((c("Kh"), c("9d"))),
            RangeHand((c("Jh"), c("Th"))),
        ),
    )


def altered_config():
    base = config()
    return ScalableRiverMultiSizeOneRaiseConfig(
        board=base.board,
        pot=13,
        bet_sizes=base.bet_sizes,
        raise_to=base.raise_to,
        p0_range=base.p0_range,
        p1_range=base.p1_range,
    )


class RiverExternalSamplingMCCFRTests(unittest.TestCase):
    def test_same_seed_is_exactly_deterministic(self):
        cfg = config()
        left = RiverExternalSamplingMCCFR(cfg, seed=1234)
        right = RiverExternalSamplingMCCFR(cfg, seed=1234)
        left.train(300)
        right.train(300)
        self.assertEqual(left.average_policy(), right.average_policy())
        self.assertEqual(left.sampled_deals, right.sampled_deals)
        self.assertEqual(left.nodes_visited, right.nodes_visited)
        self.assertEqual(left.checkpoint_sha256(), right.checkpoint_sha256())

    def test_split_training_matches_single_run(self):
        cfg = config()
        split = RiverExternalSamplingMCCFR(cfg, seed=991)
        single = RiverExternalSamplingMCCFR(cfg, seed=991)
        split.train(150)
        split.train(150)
        single.train(300)
        self.assertEqual(split.average_policy(), single.average_policy())
        self.assertEqual(split.iterations, single.iterations)
        self.assertEqual(split.sampled_deals, 300)
        self.assertEqual(split.nodes_visited, single.nodes_visited)

    def test_checkpoint_resume_is_exactly_equivalent_to_uninterrupted_run(self):
        cfg = config()
        interrupted = RiverExternalSamplingMCCFR(cfg, seed=8080)
        uninterrupted = RiverExternalSamplingMCCFR(cfg, seed=8080)

        interrupted.train(175)
        checkpoint = interrupted.checkpoint_json()
        restored = RiverExternalSamplingMCCFR.from_checkpoint_json(cfg, checkpoint)
        restored.train(225)
        uninterrupted.train(400)

        self.assertEqual(restored.average_policy(), uninterrupted.average_policy())
        self.assertEqual(restored.state_dict(), uninterrupted.state_dict())
        self.assertEqual(restored.checkpoint_sha256(), uninterrupted.checkpoint_sha256())
        self.assertAlmostEqual(
            exploitability_dp(cfg, restored.average_policy()),
            exploitability_dp(cfg, uninterrupted.average_policy()),
            places=15,
        )

    def test_checkpoint_is_bound_to_exact_game_configuration(self):
        cfg = config()
        trainer = RiverExternalSamplingMCCFR(cfg, seed=44)
        trainer.train(20)
        self.assertNotEqual(
            external_sampling_config_fingerprint(cfg),
            external_sampling_config_fingerprint(altered_config()),
        )
        with self.assertRaises(RiverMultiSizeOneRaiseError):
            RiverExternalSamplingMCCFR.from_checkpoint_json(
                altered_config(), trainer.checkpoint_json()
            )

    def test_checkpoint_semantic_tampering_is_rejected(self):
        cfg = config()
        trainer = RiverExternalSamplingMCCFR(cfg, seed=55)
        trainer.train(20)
        payload = json.loads(trainer.checkpoint_json())
        payload["sampled_deals"] += 1
        with self.assertRaises(RiverMultiSizeOneRaiseError):
            RiverExternalSamplingMCCFR.from_state_dict(cfg, payload)

        payload = json.loads(trainer.checkpoint_json())
        payload["nodes"][0]["action_count"] += 1
        with self.assertRaises(RiverMultiSizeOneRaiseError):
            RiverExternalSamplingMCCFR.from_state_dict(cfg, payload)

    def test_sampling_candidate_reduces_exact_exploitability(self):
        cfg = config()
        initial = exploitability_dp(cfg, uniform_policy(cfg))
        trainer = RiverExternalSamplingMCCFR(cfg, seed=20260826)
        trainer.train(4000)
        final = exploitability_dp(cfg, trainer.average_policy())
        self.assertLess(final, initial)
        self.assertTrue(trainer.all_regrets_finite())
        self.assertEqual(trainer.sampled_deals, 4000)

    def test_invalid_seed_and_iteration_count_are_rejected(self):
        cfg = config()
        with self.assertRaises(RiverMultiSizeOneRaiseError):
            RiverExternalSamplingMCCFR(cfg, seed=-1)
        trainer = RiverExternalSamplingMCCFR(cfg)
        with self.assertRaises(RiverMultiSizeOneRaiseError):
            trainer.train(0)


if __name__ == "__main__":
    unittest.main()
