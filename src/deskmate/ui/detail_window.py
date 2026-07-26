"""Private inspection window showing the full inference process."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import QGridLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from deskmate.character.renderer import create_renderer
from deskmate.config.schema import AppConfig
from deskmate.core.types import DetailFrame, StatusSnapshot

from .bridge import UiBridge
from .character_view import CharacterView
from .labels import (
    CANDIDATE_JA,
    CURRENT_STATUS_JA,
    DETAIL_CAVEAT_JA,
    DETAIL_TITLE_JA,
    PIPELINE_STATS_JA,
    PRIVACY_CAVEAT_JA,
    PRIVACY_NOTICE_JA,
    RULE_JA,
    SOURCE_JA,
    format_duration,
)
from .panels import (
    EventScatterPanel,
    FeatureTablePanel,
    HistoryPanel,
    MotionPanel,
    RegionPanel,
)
from .theme import resolve_theme


class StatusHeader(QWidget):
    """Show confirmed/candidate status, duration, confidence, and rule."""

    def __init__(self, character: CharacterView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.character = character
        self.status = QLabel()
        self.rule = QLabel()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(CURRENT_STATUS_JA))
        layout.addWidget(character)
        layout.addWidget(self.status)
        layout.addWidget(self.rule)

    def update_frame(self, detail: DetailFrame) -> None:
        """Update state header from one private frame."""
        snapshot = detail.snapshot
        self.character.apply_snapshot(snapshot)
        self.status.setText(
            f"{snapshot.label} / {format_duration(snapshot.duration_seconds)} / "
            f"{snapshot.confidence:.2f}"
        )
        self.rule.setText(
            f"{RULE_JA}: {detail.estimate.rule_id} {detail.estimate.reason}\n"
            f"{CANDIDATE_JA}: {detail.estimate.status.value}"
        )


class DetailWindow(QMainWindow):
    """Compose all ten private inference-inspection items."""

    def __init__(self, bridge: UiBridge, config: AppConfig) -> None:
        super().__init__()
        self.bridge = bridge
        self.config = config
        self.setWindowTitle(DETAIL_TITLE_JA)
        self.resize(1200, 800)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        central = QWidget()
        root = QVBoxLayout(central)
        root.addWidget(QLabel(PRIVACY_NOTICE_JA))
        root.addWidget(QLabel(PRIVACY_CAVEAT_JA))
        root.addWidget(QLabel(DETAIL_CAVEAT_JA))
        self.source_stats = QLabel(f"{SOURCE_JA} / {PIPELINE_STATS_JA}")
        root.addWidget(self.source_stats)
        grid = QGridLayout()
        self.event_panel = EventScatterPanel()
        self.motion_panel = MotionPanel()
        self.region_panel = RegionPanel()
        self.feature_panel = FeatureTablePanel()
        self.history_panel = HistoryPanel()
        character = CharacterView(
            create_renderer(config.character, resolve_theme(config.ui.theme)),
            config.ui.detail.character_size,
            fps=config.character.fps,
        )
        self.status_header = StatusHeader(character)
        grid.addWidget(self.event_panel, 0, 0)
        grid.addWidget(self.motion_panel, 0, 1)
        grid.addWidget(self.region_panel, 0, 2)
        grid.addWidget(self.feature_panel, 1, 0)
        grid.addWidget(self.history_panel, 1, 1)
        grid.addWidget(self.status_header, 1, 2)
        root.addLayout(grid)
        self.setCentralWidget(central)
        bridge.detail_updated.connect(self.apply_detail)

    def apply_detail(self, detail: DetailFrame) -> None:
        """Distribute a private frame to all panels."""
        self.event_panel.update_frame(detail)
        self.motion_panel.update_frame(detail)
        self.region_panel.update_frame(detail)
        self.feature_panel.update_frame(detail)
        self.history_panel.update_frame(detail)
        self.status_header.update_frame(detail)
        stats = detail.stats
        self.source_stats.setText(
            f"{SOURCE_JA}: {stats.source_name} ({stats.source_status.value}) / "
            f"{PIPELINE_STATS_JA}: {stats.last_compute_ms:.1f} ms, "
            f"dropped={stats.dropped_batches}, queue={stats.queue_depth}"
        )

    def showEvent(self, event: QShowEvent) -> None:
        """Subscribe when displayed."""
        self.bridge.open_detail()
        super().showEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Unsubscribe before destruction."""
        self.bridge.close_detail()
        super().closeEvent(event)
