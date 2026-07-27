"""Immutable data exchanged between DeskMate components."""

from dataclasses import dataclass
from datetime import datetime
import time

import numpy as np

from .enums import (
    AnimationId,
    DeskStatus,
    RegionId,
    SourceStatus,
    SystemStatus,
)
from .errors import DecodeError


EVENT_DTYPE = np.dtype([("x", "<u2"), ("y", "<u2"), ("t", "<i8"), ("p", "i1")])
EVENT_DTYPE_METAVISION = np.dtype([("x", "<u2"), ("y", "<u2"), ("p", "<i2"), ("t", "<i8")])


def _readonly(array: np.ndarray, dtype: np.dtype) -> np.ndarray:
    result = np.asarray(array, dtype=dtype)
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True)
class EventBatch:
    """Events returned by one input-source read."""

    x: np.ndarray
    y: np.ndarray
    t: np.ndarray
    p: np.ndarray
    t_start_us: int
    t_end_us: int
    seq: int
    received_monotonic: float

    @property
    def size(self) -> int:
        """Return the event count."""
        return int(self.x.size)

    @staticmethod
    def empty(t_start_us: int, t_end_us: int, seq: int) -> "EventBatch":
        """Create an empty batch for a represented sensor interval."""
        return EventBatch(
            _readonly(np.empty(0), np.dtype("uint16")),
            _readonly(np.empty(0), np.dtype("uint16")),
            _readonly(np.empty(0), np.dtype("int64")),
            _readonly(np.empty(0), np.dtype("int8")),
            t_start_us,
            t_end_us,
            seq,
            time.monotonic(),
        )

    @staticmethod
    def from_records(records: list[dict[str, object]], seq: int) -> "EventBatch":
        """Build a validated batch; raise DecodeError for malformed records."""
        required = {"x", "y", "t", "p"}
        if not records:
            return EventBatch.empty(0, 0, seq)
        try:
            if any(set(record) < required for record in records):
                raise DecodeError("event record is missing x, y, t, or p")
            x64 = np.asarray([record["x"] for record in records], dtype=np.int64)
            y64 = np.asarray([record["y"] for record in records], dtype=np.int64)
            t = np.asarray([record["t"] for record in records], dtype=np.int64)
            p = np.asarray([record["p"] for record in records], dtype=np.int8)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise DecodeError("event record has an invalid value") from exc
        if np.any(x64 < 0) or np.any(x64 > np.iinfo(np.uint16).max):
            raise DecodeError("x coordinate is outside uint16 sensor range")
        if np.any(y64 < 0) or np.any(y64 > np.iinfo(np.uint16).max):
            raise DecodeError("y coordinate is outside uint16 sensor range")
        if np.any((p != 0) & (p != 1)):
            raise DecodeError("polarity must be 0 or 1")
        if t.size > 1 and np.any(np.diff(t) < 0):
            raise DecodeError("event timestamps must be monotonic")
        return EventBatch(
            _readonly(x64, np.dtype("uint16")),
            _readonly(y64, np.dtype("uint16")),
            _readonly(t, np.dtype("int64")),
            _readonly(p, np.dtype("int8")),
            int(t[0]),
            int(t[-1]) + 1,
            seq,
            time.monotonic(),
        )

    @staticmethod
    def from_structured(arr: np.ndarray, seq: int) -> "EventBatch":
        """Build a validated batch from a named numpy event array."""
        names = arr.dtype.names
        if names is None or not {"x", "y", "t", "p"}.issubset(names):
            raise DecodeError("structured events require x, y, t, and p fields")
        if arr.size == 0:
            return EventBatch.empty(0, 0, seq)
        t = np.asarray(arr["t"], dtype=np.int64)
        if t.size > 1 and np.any(np.diff(t) < 0):
            raise DecodeError("event timestamps must be monotonic")
        x64 = np.asarray(arr["x"], dtype=np.int64)
        y64 = np.asarray(arr["y"], dtype=np.int64)
        if np.any(x64 < 0) or np.any(x64 > np.iinfo(np.uint16).max):
            raise DecodeError("x coordinate is outside uint16 sensor range")
        if np.any(y64 < 0) or np.any(y64 > np.iinfo(np.uint16).max):
            raise DecodeError("y coordinate is outside uint16 sensor range")
        p = (np.asarray(arr["p"]) > 0).astype(np.int8)
        return EventBatch(
            _readonly(x64, np.dtype("uint16")),
            _readonly(y64, np.dtype("uint16")),
            _readonly(t, np.dtype("int64")),
            _readonly(p, np.dtype("int8")),
            int(t[0]),
            int(t[-1]) + 1,
            seq,
            time.monotonic(),
        )


@dataclass(frozen=True, slots=True)
class EventWindow:
    """A fixed sensor-time event window."""

    x: np.ndarray
    y: np.ndarray
    t: np.ndarray
    p: np.ndarray
    window_index: int
    t_start_us: int
    t_end_us: int
    duration_s: float
    truncated: bool


@dataclass(frozen=True, slots=True)
class GlobalFeatures:
    """Features aggregated over the whole sensor."""

    event_count: int
    positive_count: int
    negative_count: int
    positive_ratio: float
    event_rate_eps: float
    centroid_x: float
    centroid_y: float
    centroid_shift: float
    centroid_speed: float
    var_x: float
    var_y: float
    spatial_std: float
    bbox_width: float
    bbox_height: float
    bbox_area_ratio: float
    active_cell_ratio: float
    event_count_delta: int
    event_rate_delta: float
    activity_ratio_10s: float
    idle_seconds: float
    active_seconds: float
    noise_ratio: float


@dataclass(frozen=True, slots=True)
class RegionFeatures:
    """Features aggregated for one configured desk region."""

    region_id: RegionId
    event_count: int
    event_rate_eps: float
    share: float
    centroid_x: float
    centroid_y: float
    active_cell_ratio: float


@dataclass(frozen=True, slots=True)
class VoxelFeatures:
    """Optional temporal voxel-difference features."""

    diff_l1: float
    diff_centroid_x: float
    diff_centroid_y: float
    diff_energy: float
    diff_centroid_shift: float


@dataclass(frozen=True, slots=True)
class FeatureFrame:
    """Features for one event window."""

    window_index: int
    t_start_us: int
    t_end_us: int
    duration_s: float
    global_features: GlobalFeatures
    regions: dict[RegionId, RegionFeatures]
    voxel: VoxelFeatures | None
    grid_counts: np.ndarray
    compute_ms: float

    def to_display_dict(self) -> dict[str, str]:
        """Return stable, formatted values for the private detail view."""
        values: dict[str, str] = {}
        for name in self.global_features.__dataclass_fields__:
            value = getattr(self.global_features, name)
            values[name] = f"{value:.3f}" if isinstance(value, float) else str(value)
        return values


@dataclass(frozen=True, slots=True)
class SmoothedFeatures:
    """History-derived values consumed by estimators."""

    rate_short: float
    rate_long: float
    centroid_short_x: float
    centroid_short_y: float
    centroid_long_x: float
    centroid_long_y: float
    area_short: float
    area_long: float
    speed_short: float
    cell_short: float
    share_short: dict[RegionId, float]
    share_long: dict[RegionId, float]
    rate_cv_10s: float
    idle_seconds: float
    active_seconds: float
    activity_ratio_10s: float
    noise_ratio: float
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class StatusEstimate:
    """An unsmoothed state estimate."""

    status: DeskStatus
    confidence: float
    rule_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """A confirmed state interval."""

    status: DeskStatus
    started_monotonic: float
    ended_monotonic: float | None
    peak_confidence: float


@dataclass(frozen=True, slots=True)
class StatusSnapshot:
    """Public-safe confirmed state without coordinates or features."""

    status: DeskStatus
    system_status: SystemStatus
    label: str
    animation: AnimationId
    duration_seconds: float
    confidence: float
    focus_streak_seconds: float
    break_due: bool
    changed: bool
    updated_at: datetime

    def to_public_dict(self) -> dict[str, object]:
        """Return the only externally shareable state representation."""
        return {
            "status": self.status.value,
            "label": self.label,
            "animation": self.animation.value,
            "duration_seconds": self.duration_seconds,
            "focus_streak_seconds": self.focus_streak_seconds,
            "break_due": self.break_due,
            "system_status": self.system_status.value,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(slots=True)
class PipelineStats:
    """Mutable pipeline counters copied to the UI."""

    windows_processed: int
    dropped_batches: int
    last_compute_ms: float
    avg_compute_ms: float
    source_status: SourceStatus
    source_name: str
    queue_depth: int


@dataclass(slots=True)
class DetailFrame:
    """Private detail data generated only while subscribed."""

    snapshot: StatusSnapshot
    features: FeatureFrame
    smoothed: SmoothedFeatures
    estimate: StatusEstimate
    preview_x: np.ndarray
    preview_y: np.ndarray
    preview_p: np.ndarray
    history: list[HistoryEntry]
    rate_series: np.ndarray
    stats: PipelineStats
