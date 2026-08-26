import unittest

from deepsix_core.ggpoker_economy import GGPOKER_SHORTDECK_ECONOMY_VERSION
from deepsix_simulator import (
    SIMULATOR_OBSERVATION_SCHEMA_VERSION,
    SIMULATOR_RULES_VERSION,
    SIMULATOR_SETTLEMENT_VERSION,
    SIMULATOR_UTILITY_VERSION,
)
from deepsix_trainer.experiment_profile import (
    SOLVER_EXPERIMENT_PROFILE_SCHEMA,
    SolverExperimentProfile,
    SolverExperimentProfileError,
)


def profile(**overrides):
    values = {
        "rules_version": SIMULATOR_RULES_VERSION,
        "economy_version": GGPOKER_SHORTDECK_ECONOMY_VERSION,
        "settlement_version": SIMULATOR_SETTLEMENT_VERSION,
        "utility_version": SIMULATOR_UTILITY_VERSION,
        "simulator_observation_schema": SIMULATOR_OBSERVATION_SCHEMA_VERSION,
        "player_count": 2,
        "stake_cents": 2,
        "bbj_enabled": False,
        "stack_profile_id": "fixed-40-ante-hu-v1",
        "training_distribution_id": "river-lab-six-texture-v1",
        "state_representation_id": "identity-private-state-v1",
        "action_abstraction_id": "two-size-one-raise-v1",
        "solver_family": "external_sampling_mccfr",
        "objective_id": "GROSS_POKER_DELTA",
    }
    values.update(overrides)
    return SolverExperimentProfile(**values)


class SolverExperimentProfileTests(unittest.TestCase):
    def test_roundtrip_preserves_canonical_identity(self):
        original = profile()
        payload = original.to_dict()
        self.assertEqual(payload["schema"], SOLVER_EXPERIMENT_PROFILE_SCHEMA)
        restored = SolverExperimentProfile.from_dict(payload)
        self.assertEqual(restored, original)
        self.assertEqual(restored.profile_id, original.profile_id)
        self.assertEqual(restored.policy_id, original.policy_id)

    def test_every_strategy_semantic_axis_changes_profile_identity(self):
        base = profile()
        variants = (
            profile(rules_version=base.rules_version + "-alt"),
            profile(economy_version=base.economy_version + "-alt"),
            profile(settlement_version=base.settlement_version + "-alt"),
            profile(utility_version=base.utility_version + "-alt"),
            profile(simulator_observation_schema=base.simulator_observation_schema + 1),
            profile(player_count=3),
            profile(stake_cents=5),
            profile(bbj_enabled=True),
            profile(stack_profile_id="asymmetric-stack-curriculum-v1"),
            profile(training_distribution_id="heldout-river-v2"),
            profile(state_representation_id="cfv-kmedoids-v1"),
            profile(action_abstraction_id="four-size-one-raise-v1"),
            profile(solver_family="synchronous_rmplus"),
            profile(objective_id="NET_CASH_DELTA"),
        )
        identities = {base.profile_id, *(item.profile_id for item in variants)}
        self.assertEqual(len(identities), 1 + len(variants))

    def test_stream_key_is_bound_to_profile_and_solver_semantics(self):
        item = profile(player_count=6, solver_family="external_sampling_mccfr")
        stream = item.stream_key(20260826)
        self.assertEqual(stream.experiment_id, item.profile_id)
        self.assertEqual(stream.solver_family, item.solver_family)
        self.assertEqual(stream.player_count, 6)
        self.assertEqual(stream.algorithm_seed, 20260826)

    def test_objective_must_explicitly_select_gross_or_net_cash(self):
        with self.assertRaises(SolverExperimentProfileError):
            profile(objective_id="ICM")
        with self.assertRaises(SolverExperimentProfileError):
            profile(objective_id="")

    def test_player_count_and_stake_are_fail_closed(self):
        with self.assertRaises(SolverExperimentProfileError):
            profile(player_count=1)
        with self.assertRaises(SolverExperimentProfileError):
            profile(player_count=7)
        with self.assertRaises(SolverExperimentProfileError):
            profile(stake_cents=0)

    def test_serialized_identity_tampering_is_rejected(self):
        payload = profile().to_dict()
        payload["profile_id"] = "deepsix-exp-v1:" + "0" * 64
        with self.assertRaises(SolverExperimentProfileError):
            SolverExperimentProfile.from_dict(payload)

    def test_policy_identity_is_derived_from_experiment_identity(self):
        base = profile()
        changed = profile(action_abstraction_id="four-size-one-raise-v1")
        self.assertNotEqual(base.profile_id, changed.profile_id)
        self.assertNotEqual(base.policy_id, changed.policy_id)


if __name__ == "__main__":
    unittest.main()
