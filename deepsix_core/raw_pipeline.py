"""End-to-end read-only Python boundary for OH6Plus raw JSON frames.

``RawObservationPipeline`` composes the already-gated layers without adding new
poker semantics:

    RawTableSnapshot JSON
      -> validation/parser
      -> raw-chair projection + exact money scale
      -> stable-frame gate
      -> conservative evidence timeline

It is intentionally useful both for offline replay and for future read-only
runtime logging.  The class never clicks, never chooses a policy action and
never bypasses an ``AMBIGUOUS`` timeline result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .raw_reconstructor import (
    ChairLayout,
    MoneyScale,
    ProjectedSnapshot,
    StableSnapshotGate,
    project_raw_snapshot,
)
from .raw_snapshot import RawTableSnapshot, raw_snapshot_from_json
from .raw_timeline import RawEvidenceTimeline, TimelineEvent


class RawPipelineError(ValueError):
    pass


@dataclass
class RawObservationPipeline:
    layout: ChairLayout
    money_scale: MoneyScale
    required_identical: int = 2
    ante_units: int | None = None
    dealer_total_antes: int = 2
    _stable_gate: StableSnapshotGate = field(init=False)
    _timeline: RawEvidenceTimeline = field(init=False)

    def __post_init__(self) -> None:
        self.layout.validate()
        self.money_scale.decimal_unit()
        try:
            self._stable_gate = StableSnapshotGate(self.required_identical)
            self._timeline = RawEvidenceTimeline(
                ante_units=self.ante_units,
                dealer_total_antes=self.dealer_total_antes,
            )
        except ValueError as exc:
            raise RawPipelineError(str(exc)) from exc

    @property
    def timeline(self) -> RawEvidenceTimeline:
        return self._timeline

    def project(self, snapshot: RawTableSnapshot) -> ProjectedSnapshot:
        return project_raw_snapshot(
            snapshot,
            layout=self.layout,
            money_scale=self.money_scale,
        )

    def push_snapshot(self, snapshot: RawTableSnapshot) -> TimelineEvent | None:
        projected = self.project(snapshot)
        stable = self._stable_gate.push(projected)
        if stable is None:
            return None
        return self._timeline.push(stable)

    def push_json(self, text: str) -> TimelineEvent | None:
        try:
            snapshot = raw_snapshot_from_json(text)
        except ValueError as exc:
            raise RawPipelineError(str(exc)) from exc
        try:
            return self.push_snapshot(snapshot)
        except ValueError as exc:
            raise RawPipelineError(str(exc)) from exc
