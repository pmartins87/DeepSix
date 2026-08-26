"""Canonical semantic identity for DeepSix solver/training experiments.

Long poker training is only reproducible when an artifact identifies the game,
economy, utility, representation, action abstraction and solver family that
created it.  This profile follows the useful identity/provenance separation
seen in SpinCore while using DeepSix-specific Short Deck cash semantics.

Human labels, timestamps and machine names do not participate in the semantic
hash.  If a field can change strategic incentives or the policy mapping, it must
be inside this profile (or inside a version/id referenced by it).
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .stream_scheduler import TrainingStreamKey


SOLVER_EXPERIMENT_PROFILE_SCHEMA = "DEEPSIX_SOLVER_EXPERIMENT_PROFILE_V1"
_ALLOWED_OBJECTIVES = frozenset({"GROSS_POKER_DELTA", "NET_CASH_DELTA"})


class SolverExperimentProfileError(ValueError):
    pass


def _required_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SolverExperimentProfileError(f"{name} is required")
    return value


@dataclass(frozen=True)
class SolverExperimentProfile:
    rules_version: str
    economy_version: str
    settlement_version: str
    utility_version: str
    simulator_observation_schema: int
    player_count: int
    stake_cents: int
    bbj_enabled: bool
    stack_profile_id: str
    training_distribution_id: str
    state_representation_id: str
    action_abstraction_id: str
    solver_family: str
    objective_id: str

    def __post_init__(self) -> None:
        for name in (
            "rules_version",
            "economy_version",
            "settlement_version",
            "utility_version",
            "stack_profile_id",
            "training_distribution_id",
            "state_representation_id",
            "action_abstraction_id",
            "solver_family",
            "objective_id",
        ):
            _required_text(name, getattr(self, name))
        if (
            isinstance(self.simulator_observation_schema, bool)
            or not isinstance(self.simulator_observation_schema, int)
            or self.simulator_observation_schema <= 0
        ):
            raise SolverExperimentProfileError(
                "simulator_observation_schema must be a positive integer"
            )
        if isinstance(self.player_count, bool) or not isinstance(self.player_count, int):
            raise SolverExperimentProfileError("player_count must be an integer")
        if not 2 <= self.player_count <= 6:
            raise SolverExperimentProfileError("player_count must be within 2..6")
        if isinstance(self.stake_cents, bool) or not isinstance(self.stake_cents, int):
            raise SolverExperimentProfileError("stake_cents must be an integer")
        if self.stake_cents <= 0:
            raise SolverExperimentProfileError("stake_cents must be positive")
        if not isinstance(self.bbj_enabled, bool):
            raise SolverExperimentProfileError("bbj_enabled must be boolean")
        if self.objective_id not in _ALLOWED_OBJECTIVES:
            raise SolverExperimentProfileError(
                "objective_id must explicitly select gross zero-sum or net cash utility"
            )

    def semantic_payload(self) -> dict[str, object]:
        return {
            "schema": SOLVER_EXPERIMENT_PROFILE_SCHEMA,
            "product_target": "OFFLINE_6PLUS_SIMULATOR",
            "rules_version": self.rules_version,
            "economy_version": self.economy_version,
            "settlement_version": self.settlement_version,
            "utility_version": self.utility_version,
            "simulator_observation_schema": self.simulator_observation_schema,
            "player_count": self.player_count,
            "stake_cents": self.stake_cents,
            "bbj_enabled": self.bbj_enabled,
            "stack_profile_id": self.stack_profile_id,
            "training_distribution_id": self.training_distribution_id,
            "state_representation_id": self.state_representation_id,
            "action_abstraction_id": self.action_abstraction_id,
            "solver_family": self.solver_family,
            "objective_id": self.objective_id,
        }

    @property
    def profile_id(self) -> str:
        raw = json.dumps(
            self.semantic_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return "deepsix-exp-v1:" + hashlib.sha256(raw).hexdigest()

    @property
    def policy_id(self) -> str:
        raw = (self.profile_id + "|policy").encode("utf-8")
        return "deepsix-policy-v1:" + hashlib.sha256(raw).hexdigest()

    def stream_key(self, algorithm_seed: int) -> TrainingStreamKey:
        return TrainingStreamKey(
            experiment_id=self.profile_id,
            solver_family=self.solver_family,
            player_count=self.player_count,
            algorithm_seed=algorithm_seed,
        )

    def to_dict(self) -> dict[str, object]:
        payload = self.semantic_payload()
        payload["profile_id"] = self.profile_id
        payload["policy_id"] = self.policy_id
        return payload

    @classmethod
    def from_dict(cls, payload: dict) -> "SolverExperimentProfile":
        if payload.get("schema") != SOLVER_EXPERIMENT_PROFILE_SCHEMA:
            raise SolverExperimentProfileError("wrong solver experiment profile schema")
        if payload.get("product_target") != "OFFLINE_6PLUS_SIMULATOR":
            raise SolverExperimentProfileError("wrong solver experiment target")
        profile = cls(
            rules_version=str(payload["rules_version"]),
            economy_version=str(payload["economy_version"]),
            settlement_version=str(payload["settlement_version"]),
            utility_version=str(payload["utility_version"]),
            simulator_observation_schema=payload["simulator_observation_schema"],
            player_count=payload["player_count"],
            stake_cents=payload["stake_cents"],
            bbj_enabled=payload["bbj_enabled"],
            stack_profile_id=str(payload["stack_profile_id"]),
            training_distribution_id=str(payload["training_distribution_id"]),
            state_representation_id=str(payload["state_representation_id"]),
            action_abstraction_id=str(payload["action_abstraction_id"]),
            solver_family=str(payload["solver_family"]),
            objective_id=str(payload["objective_id"]),
        )
        if payload.get("profile_id") != profile.profile_id:
            raise SolverExperimentProfileError("solver experiment profile hash mismatch")
        if payload.get("policy_id") != profile.policy_id:
            raise SolverExperimentProfileError("solver policy hash mismatch")
        return profile
