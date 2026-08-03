"""Validated DeskMate configuration models."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from deskmate.core.enums import DeskStatus, RegionId, SourceKind


class StrictModel(BaseModel):
    """Base configuration that rejects unknown keys."""

    model_config = ConfigDict(extra="forbid")


class AppSectionConfig(StrictModel):
    """Application startup configuration."""

    locale: str = "ja"
    autostart_pipeline: bool = True
    fullscreen: bool = False


class SensorConfig(StrictModel):
    """Event-sensor resolution."""

    width: int = Field(320, ge=64, le=4096)
    height: int = Field(320, ge=64, le=4096)


class MetavisionInputConfig(StrictModel):
    """Metavision live or RAW replay configuration."""

    delta_t_us: int = Field(20_000, ge=1)
    input_path: str = ""


class DummyInputConfig(StrictModel):
    """Synthetic input configuration."""

    mode: Literal["demo", "manual"] = "demo"
    scenario: str = "keyboard_focus"
    loop: bool = True
    seed: int = 20260726
    batch_interval_ms: int = Field(20, ge=1)
    rate_scale: float = Field(1.0, ge=0.0)


class FileInputConfig(StrictModel):
    """Portable replay-file configuration."""

    path: Path | None = None
    speed: float = Field(1.0, gt=0.0)
    loop: bool = True


class Hdf5InputConfig(StrictModel):
    """Optional HDF5 input configuration."""

    path: Path | None = None
    events_dataset: str = "/events"
    speed: float = Field(1.0, gt=0.0)
    loop: bool = False


class UdpInputConfig(StrictModel):
    """Bounded UDP event receiver configuration."""

    bind_host: str = "0.0.0.0"
    allowed_host: str = "127.0.0.1"
    allow_public_sender: bool = False
    port: int = Field(5005, ge=1, le=65535)
    reassembly_timeout_ms: int = Field(500, ge=1, le=60_000)
    max_batch_events: int = Field(200_000, ge=1)
    max_pending_batches: int = Field(64, ge=1, le=4096)


class InputConfig(StrictModel):
    """Input selection and recovery configuration."""

    source: SourceKind = SourceKind.AUTO
    metavision: MetavisionInputConfig = Field(default_factory=MetavisionInputConfig)
    poll_timeout_ms: int = Field(50, ge=1)
    stall_timeout_ms: int = Field(1500, ge=1)
    disconnect_timeout_ms: int = Field(5000, ge=1)
    reconnect_interval_ms: int = Field(3000, ge=1)
    max_open_retries: int = Field(10, ge=1)
    dummy: DummyInputConfig = Field(default_factory=DummyInputConfig)
    file: FileInputConfig = Field(default_factory=FileInputConfig)
    hdf5: Hdf5InputConfig = Field(default_factory=Hdf5InputConfig)
    udp: UdpInputConfig = Field(default_factory=UdpInputConfig)


class UdpOutputConfig(StrictModel):
    """Optional raw-event UDP output, disabled by default."""

    enabled: bool = False
    destination_host: str = "127.0.0.1"
    allow_public_destination: bool = False
    destination_port: int = Field(5005, ge=1, le=65535)
    max_datagram_bytes: int = Field(1200, ge=64, le=65_507)
    stream_id: int = Field(1, ge=0, le=4_294_967_295)


class UdpConfig(StrictModel):
    """UDP transport configuration."""

    output: UdpOutputConfig = Field(default_factory=UdpOutputConfig)


class PipelineConfig(StrictModel):
    """Pipeline queue configuration."""

    queue_size: int = Field(64, ge=1)
    queue_overflow: Literal["drop_oldest"] = "drop_oldest"


class WindowConfig(StrictModel):
    """Sensor-time window configuration."""

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
    """One normalized desk region."""

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
    """Return the canonical GenX320 desk regions."""

    return [
        RegionConfigItem(id=RegionId.KEYBOARD, rect=(0.25, 0.62, 0.75, 1.0)),
        RegionConfigItem(id=RegionId.MOUSE, rect=(0.75, 0.60, 1.0, 1.0)),
        RegionConfigItem(id=RegionId.CENTER, rect=(0.30, 0.25, 0.70, 0.62)),
        RegionConfigItem(id=RegionId.LEFT, rect=(0.0, 0.0, 0.30, 0.62)),
        RegionConfigItem(id=RegionId.RIGHT, rect=(0.70, 0.0, 1.0, 0.60)),
    ]


class VoxelConfig(StrictModel):
    """Optional voxel features."""

    enabled: bool = False
    time_bins: int = Field(4, ge=1)
    spatial_scale: int = Field(4, ge=1)


class FeatureConfig(StrictModel):
    """Feature extraction configuration."""

    ema_short_seconds: float = Field(1.0, gt=0.0)
    ema_long_seconds: float = Field(10.0, gt=0.0)
    history_seconds: float = Field(60.0, gt=0.0)
    bbox_percentile: float = Field(0.05, ge=0.0, lt=0.5)
    voxel: VoxelConfig = Field(default_factory=VoxelConfig)


class MetavisionEstimationConfig(StrictModel):
    """Live-camera overrides calibrated from the installed GenX320 view."""

    idle_eps: float = Field(10_000.0, ge=0.0)
    focus_min_eps: float = Field(15_000.0, ge=0.0)
    focus_region_share: float = Field(0.0, ge=0.0, le=1.0)
    focus_max_bbox_area_ratio: float = Field(0.75, ge=0.0, le=1.0)
    focus_max_activity_cv: float = Field(3.0, ge=0.0)


class EstimationConfig(StrictModel):
    """Three-state rule-estimation configuration."""

    estimator: Literal["rule", "ml"] = "rule"
    model_path: Path | None = None
    warmup_seconds: float = Field(3.0, ge=0.0)
    idle_eps: float = Field(100.0, ge=0.0)
    away_seconds: float = Field(30.0, ge=0.0)
    focus_min_eps: float = Field(400.0, ge=0.0)
    high_activity_eps: float = Field(5000.0, gt=0.0)
    focus_regions: list[RegionId] = Field(
        default_factory=lambda: [RegionId.KEYBOARD, RegionId.MOUSE]
    )
    focus_region_share: float = Field(0.60, ge=0.0, le=1.0)
    focus_min_seconds: float = Field(5.0, ge=0.0)
    focus_max_bbox_area_ratio: float = Field(0.20, ge=0.0, le=1.0)
    focus_max_activity_cv: float = Field(0.60, ge=0.0)
    background_residual_eps: float = Field(15_000.0, ge=0.0)
    metavision: MetavisionEstimationConfig = Field(
        default_factory=MetavisionEstimationConfig
    )


class BreakConfig(StrictModel):
    """Independent break-prompt timing."""

    enabled: bool = True
    after_seconds: float = Field(1500.0, gt=0.0)
    reset_seconds: float = Field(180.0, gt=0.0)
    snooze_seconds: float = Field(300.0, gt=0.0)
    demo_scale: float = Field(1.0, gt=0.0)


class MinDwellConfig(StrictModel):
    """Per-state minimum display duration."""

    default: float = Field(3.0, ge=0.0)
    away: float = Field(5.0, ge=0.0)


class SmoothingConfig(StrictModel):
    """Vote and confidence smoothing."""

    vote_window_size: int = Field(5, ge=1)
    vote_min_count: int = Field(3, ge=1)
    enter_confidence: float = Field(0.50, ge=0.0, le=1.0)
    exit_confidence: float = Field(0.35, ge=0.0, le=1.0)
    confidence_ema_seconds: float = Field(2.0, gt=0.0)
    min_dwell_seconds: MinDwellConfig = Field(default_factory=MinDwellConfig)


class CharacterConfig(StrictModel):
    """Character renderer and sprite scaling."""

    renderer: Literal["gif", "shape"] = "gif"
    assets_dir: Path = Path("assets/character")
    scale: int = Field(4, ge=1, le=12)


class WidgetUiConfig(StrictModel):
    """Main-window layout."""

    width: int = Field(460, ge=180)
    height: int = Field(250, ge=90)
    opacity: float = Field(0.96, ge=0.1, le=1.0)
    show_history: bool = True
    character_size: int = Field(120, ge=30)
    minimized_size: int = Field(96, ge=48)
    last_position: tuple[int, int] | None = None
    minimized: bool = False


class DetailUiConfig(StrictModel):
    """Detail/demo-window layout."""

    max_preview_points: int = Field(200_000, ge=1)
    history_seconds: int = Field(300, ge=1)
    refresh_hz: int = Field(10, ge=1)
    character_size: int = Field(120, ge=30)
    calibration_seconds: float = Field(10.0, ge=0.0)


class UiConfig(StrictModel):
    """User-interface configuration."""

    theme: Literal["dark", "light"] = "dark"
    widget: WidgetUiConfig = Field(default_factory=WidgetUiConfig)
    detail: DetailUiConfig = Field(default_factory=DetailUiConfig)


class PrivacyConfig(StrictModel):
    """Privacy controls, disabled by default."""

    save_raw_events: bool = False
    save_features: bool = False
    history_retention_minutes: int = Field(60, ge=1)
    allow_external_send: bool = False
    show_caveat: bool = True


class LoggingConfig(StrictModel):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file_enabled: bool = True
    dir: Path | None = None
    max_bytes: int = 1_048_576
    backup_count: int = 3
    log_features: bool = False


class DebugConfig(StrictModel):
    """Development-only controls."""

    enabled: bool = False
    force_status: DeskStatus | None = None
    break_start_seconds: float = Field(3000.0, ge=0.0)


class AppConfig(StrictModel):
    """Complete DeskMate configuration."""

    version: int = 1
    app: AppSectionConfig = Field(default_factory=AppSectionConfig)
    sensor: SensorConfig = Field(default_factory=SensorConfig)
    input: InputConfig = Field(default_factory=InputConfig)
    udp: UdpConfig = Field(default_factory=UdpConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    window: WindowConfig = Field(default_factory=WindowConfig)
    regions: list[RegionConfigItem] = Field(default_factory=default_regions)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    estimation: EstimationConfig = Field(default_factory=EstimationConfig)
    break_prompt: BreakConfig = Field(default_factory=BreakConfig, alias="break")
    smoothing: SmoothingConfig = Field(default_factory=SmoothingConfig)
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
