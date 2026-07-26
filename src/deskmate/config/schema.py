"""Validated DeskMate configuration models."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from deskmate.core.enums import DeskStatus, RegionId, SourceKind


class StrictModel(BaseModel):
    """Base configuration that rejects unknown keys."""

    model_config = ConfigDict(extra="forbid")


class AppSectionConfig(StrictModel):
    locale: str = "ja"
    autostart_pipeline: bool = True
    show_share_window: bool = False


class SensorConfig(StrictModel):
    width: int = Field(320, ge=64, le=4096)
    height: int = Field(320, ge=64, le=4096)


class DummyInputConfig(StrictModel):
    mode: Literal["demo", "manual"] = "demo"
    scenario: str = "keyboard_steady"
    loop: bool = True
    seed: int = 20260726
    batch_interval_ms: int = Field(20, ge=1)
    rate_scale: float = Field(1.0, ge=0.0)


class FileInputConfig(StrictModel):
    path: Path | None = None
    speed: float = Field(1.0, gt=0.0)
    loop: bool = True


class Hdf5InputConfig(StrictModel):
    path: Path | None = None
    events_dataset: str = "/events"
    speed: float = Field(1.0, gt=0.0)
    loop: bool = False


class InputConfig(StrictModel):
    source: SourceKind = SourceKind.DUMMY
    poll_timeout_ms: int = Field(50, ge=1)
    stall_timeout_ms: int = Field(1500, ge=1)
    disconnect_timeout_ms: int = Field(5000, ge=1)
    reconnect_interval_ms: int = Field(3000, ge=1)
    max_open_retries: int = Field(10, ge=1)
    dummy: DummyInputConfig = Field(default_factory=DummyInputConfig)
    file: FileInputConfig = Field(default_factory=FileInputConfig)
    hdf5: Hdf5InputConfig = Field(default_factory=Hdf5InputConfig)


class PipelineConfig(StrictModel):
    queue_size: int = Field(64, ge=1)
    queue_overflow: Literal["drop_oldest"] = "drop_oldest"


class WindowConfig(StrictModel):
    window_ms: int = Field(200, ge=100, le=1000)
    stride_ms: int = Field(200, ge=10, le=1000)
    max_events_per_window: int = Field(200_000, ge=1000)
    grid_cols: int = Field(16, ge=2, le=128)
    grid_rows: int = Field(16, ge=2, le=128)

    @model_validator(mode="after")
    def _check_stride(self) -> "WindowConfig":
        if self.stride_ms > self.window_ms:
            raise ValueError("stride_ms must be <= window_ms")
        return self


class RegionConfigItem(StrictModel):
    id: RegionId
    rect: tuple[float, float, float, float]

    @model_validator(mode="after")
    def _check_rect(self) -> "RegionConfigItem":
        x0, y0, x1, y1 = self.rect
        if self.id is RegionId.OTHER:
            raise ValueError("other is implicit and cannot be configured")
        if not all(0.0 <= value <= 1.0 for value in self.rect):
            raise ValueError("region coordinates must be within [0, 1]")
        if x0 >= x1 or y0 >= y1:
            raise ValueError("region rectangle must have positive area")
        return self


def default_regions() -> list[RegionConfigItem]:
    return [
        RegionConfigItem(id=RegionId.KEYBOARD, rect=(0.25, 0.62, 0.75, 1.0)),
        RegionConfigItem(id=RegionId.MOUSE, rect=(0.75, 0.60, 1.0, 1.0)),
        RegionConfigItem(id=RegionId.CENTER, rect=(0.30, 0.25, 0.70, 0.62)),
        RegionConfigItem(id=RegionId.LEFT, rect=(0.0, 0.0, 0.30, 0.62)),
        RegionConfigItem(id=RegionId.RIGHT, rect=(0.70, 0.0, 1.0, 0.60)),
    ]


class VoxelConfig(StrictModel):
    enabled: bool = False
    time_bins: int = Field(4, ge=1)
    spatial_scale: int = Field(4, ge=1)


class FeatureConfig(StrictModel):
    ema_short_seconds: float = Field(1.0, gt=0.0)
    ema_long_seconds: float = Field(10.0, gt=0.0)
    history_seconds: float = Field(60.0, gt=0.0)
    bbox_percentile: float = Field(0.05, ge=0.0, lt=0.5)
    voxel: VoxelConfig = Field(default_factory=VoxelConfig)


class EstimationConfig(StrictModel):
    estimator: Literal["rule", "ml"] = "rule"
    model_path: Path | None = None
    warmup_seconds: float = 3.0
    idle_eps: float = 100.0
    low_activity_eps: float = 400.0
    focus_min_eps: float = 400.0
    active_eps: float = 2000.0
    high_activity_eps: float = 5000.0
    no_motion_seconds: float = 20.0
    focus_regions: list[RegionId] = Field(
        default_factory=lambda: [RegionId.KEYBOARD, RegionId.MOUSE]
    )
    focus_region_share: float = 0.60
    focus_min_seconds: float = 5.0
    focus_max_bbox_area_ratio: float = 0.20
    focus_max_activity_cv: float = 0.60
    organizing_bbox_area_ratio: float = 0.25
    organizing_active_cell_ratio: float = 0.25
    organizing_centroid_speed: float = 35.0
    break_max_eps: float = 600.0
    break_decay_ratio: float = 0.40
    transition_change_score: float = 0.55
    transition_max_seconds: float = 6.0
    noise_ratio_threshold: float = 0.79


class MinDwellConfig(StrictModel):
    default: float = 3.0
    transition: float = 2.0
    no_motion: float = 5.0
    unknown: float = 2.0


class SmoothingConfig(StrictModel):
    vote_window_size: int = Field(5, ge=1)
    vote_min_count: int = Field(3, ge=1)
    enter_confidence: float = 0.50
    exit_confidence: float = 0.35
    confidence_ema_seconds: float = 2.0
    display_confidence_floor: float = 0.45
    min_dwell_seconds: MinDwellConfig = Field(default_factory=MinDwellConfig)


class ShareConfig(StrictModel):
    enabled: bool = True
    min_confidence: float = 0.50
    approachable_after_break_seconds: float = 10.0
    recent_busy_lookback_seconds: float = 120.0
    prefer_later_min_seconds: float = 30.0
    update_interval_ms: int = 1000
    min_hold_seconds: float = 5.0


class CharacterConfig(StrictModel):
    renderer: Literal["shape", "image"] = "shape"
    assets_dir: Path = Path("assets/character")
    loop_period_seconds: float = 2.0
    transition_ms: int = 350
    fps: int = 20


class WidgetUiConfig(StrictModel):
    width: int = Field(460, ge=180)
    height: int = Field(250, ge=90)
    opacity: float = 0.96
    show_confidence: bool = True
    show_history: bool = True
    show_privacy_notice: bool = True
    character_size: int = Field(132, ge=32)
    minimized_size: int = Field(96, ge=48)
    last_position: tuple[int, int] | None = None
    minimized: bool = False


class DetailUiConfig(StrictModel):
    max_preview_points: int = 5000
    history_seconds: int = 300
    refresh_hz: int = 10
    character_size: int = 96


class ShareUiConfig(StrictModel):
    width: int = 480
    height: int = 320
    character_size: int = 96
    fullscreen: bool = False


class UiConfig(StrictModel):
    theme: Literal["dark", "light"] = "dark"
    widget: WidgetUiConfig = Field(default_factory=WidgetUiConfig)
    detail: DetailUiConfig = Field(default_factory=DetailUiConfig)
    share: ShareUiConfig = Field(default_factory=ShareUiConfig)


class PrivacyConfig(StrictModel):
    save_raw_events: bool = False
    save_features: bool = False
    history_retention_minutes: int = Field(60, ge=1)
    allow_external_send: bool = False
    show_caveat: bool = True


class LoggingConfig(StrictModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file_enabled: bool = True
    dir: Path | None = None
    max_bytes: int = 1_048_576
    backup_count: int = 3
    log_features: bool = False


class DebugConfig(StrictModel):
    enabled: bool = False
    force_status: DeskStatus | None = None


class AppConfig(StrictModel):
    version: int = 1
    app: AppSectionConfig = Field(default_factory=AppSectionConfig)
    sensor: SensorConfig = Field(default_factory=SensorConfig)
    input: InputConfig = Field(default_factory=InputConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    window: WindowConfig = Field(default_factory=WindowConfig)
    regions: list[RegionConfigItem] = Field(default_factory=default_regions)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    estimation: EstimationConfig = Field(default_factory=EstimationConfig)
    smoothing: SmoothingConfig = Field(default_factory=SmoothingConfig)
    share: ShareConfig = Field(default_factory=ShareConfig)
    character: CharacterConfig = Field(default_factory=CharacterConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    debug: DebugConfig = Field(default_factory=DebugConfig)

    @model_validator(mode="after")
    def _check_regions(self) -> "AppConfig":
        ids = [region.id for region in self.regions]
        if len(ids) != len(set(ids)):
            raise ValueError("region ids must be unique")
        return self
