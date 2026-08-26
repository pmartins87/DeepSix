"""Training and solver experiments for DeepSix.

The package starts with tiny, exactly auditable games.  Large Short Deck
training code must beat these baselines and preserve their invariants before it
is trusted with long Ryzen runs.
"""

from .experiment_profile import (
    SOLVER_EXPERIMENT_PROFILE_SCHEMA,
    SolverExperimentProfile,
    SolverExperimentProfileError,
)
from .kuhn import (
    KuhnCFR,
    KuhnPolicy,
    exploitability as kuhn_exploitability,
    expected_value as kuhn_expected_value,
)
from .river_external_sampling import RiverExternalSamplingMCCFR
from .river_microgame import (
    RangeHand,
    RiverCFR,
    RiverDeal,
    RiverMicrogameConfig,
    RiverMicrogameError,
    RiverPolicy,
    best_response_value_player0 as river_best_response_value_player0,
    best_response_value_player1 as river_best_response_value_player1,
    expected_value as river_expected_value,
    exploitability as river_exploitability,
)
from .river_multisize import (
    MultiSizeDeal,
    RiverMultiSizeCFR,
    RiverMultiSizeConfig,
    RiverMultiSizeError,
    RiverMultiSizePolicy,
    best_response_value_player0 as multisize_best_response_value_player0,
    best_response_value_player1 as multisize_best_response_value_player1,
    expected_value as multisize_expected_value,
    exploitability as multisize_exploitability,
    uniform_policy as multisize_uniform_policy,
)
from .stream_scheduler import (
    DurableTrainingReceipt,
    TrainingIterationLease,
    TrainingSchedulerCheckpointReceipt,
    TrainingStreamError,
    TrainingStreamKey,
    TrainingStreamPlan,
    TrainingStreamScheduler,
    load_training_scheduler_checkpoint,
    save_training_scheduler_checkpoint_atomic,
)

__all__ = [
    "DurableTrainingReceipt",
    "KuhnCFR",
    "KuhnPolicy",
    "MultiSizeDeal",
    "RangeHand",
    "RiverCFR",
    "RiverDeal",
    "RiverExternalSamplingMCCFR",
    "RiverMicrogameConfig",
    "RiverMicrogameError",
    "RiverMultiSizeCFR",
    "RiverMultiSizeConfig",
    "RiverMultiSizeError",
    "RiverMultiSizePolicy",
    "RiverPolicy",
    "SOLVER_EXPERIMENT_PROFILE_SCHEMA",
    "SolverExperimentProfile",
    "SolverExperimentProfileError",
    "TrainingIterationLease",
    "TrainingSchedulerCheckpointReceipt",
    "TrainingStreamError",
    "TrainingStreamKey",
    "TrainingStreamPlan",
    "TrainingStreamScheduler",
    "kuhn_exploitability",
    "kuhn_expected_value",
    "load_training_scheduler_checkpoint",
    "multisize_best_response_value_player0",
    "multisize_best_response_value_player1",
    "multisize_expected_value",
    "multisize_exploitability",
    "multisize_uniform_policy",
    "river_best_response_value_player0",
    "river_best_response_value_player1",
    "river_expected_value",
    "river_exploitability",
    "save_training_scheduler_checkpoint_atomic",
]
