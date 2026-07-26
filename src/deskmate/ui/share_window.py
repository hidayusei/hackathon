"""Privacy-limited shared status window."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from deskmate.character.renderer import create_renderer
from deskmate.config.schema import AppConfig
from deskmate.core.enums import SystemStatus
from deskmate.core.types import StatusSnapshot

from .bridge import UiBridge
from .character_view import CharacterView
from .labels import (
    APPROACHABILITY_LABELS_JA,
    LAST_UPDATED_JA,
    SHARING_STOPPED_JA,
    SHARE_TITLE_JA,
    format_duration,
    resolve_share_label,
)
from .theme import resolve_theme


class ShareWindow(QWidget):
    """Show only character, state, duration, approachability, and update time."""

    received_signals = ("snapshot_updated",)

    def __init__(self, bridge: UiBridge, config: AppConfig) -> None:
        super().__init__()
        self.bridge = bridge
        self.config = config
        self.setWindowTitle(SHARE_TITLE_JA)
        self.resize(config.ui.share.width, config.ui.share.height)
        theme = resolve_theme(config.ui.theme)
        self.character_view = CharacterView(
            create_renderer(config.character, theme),
            config.ui.share.character_size,
            self,
            config.character.fps,
        )
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.duration_label = QLabel()
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.approachability_label = QLabel()
        self.approachability_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.updated_label = QLabel()
        self.updated_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stopped_label = QLabel(SHARING_STOPPED_JA)
        self.stopped_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stopped_label.hide()
        layout = QVBoxLayout(self)
        layout.addWidget(self.character_view, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        layout.addWidget(self.duration_label)
        layout.addWidget(self.approachability_label)
        layout.addWidget(self.updated_label)
        layout.addWidget(self.stopped_label)
        self.setStyleSheet(
            f"QWidget {{background:{theme.background};color:{theme.text};}}"
            f"QLabel {{font-size:20px;}}"
        )
        bridge.snapshot_updated.connect(self.apply_snapshot)
        if config.ui.share.fullscreen:
            self.showFullScreen()

    def _set_stopped(self, stopped: bool) -> None:
        self.stopped_label.setVisible(stopped)
        for widget in (
            self.character_view,
            self.status_label,
            self.duration_label,
            self.approachability_label,
            self.updated_label,
        ):
            widget.setVisible(not stopped)

    def apply_snapshot(self, snapshot: StatusSnapshot) -> None:
        """Render public-safe fields only."""
        stopped = (
            not self.bridge.sharing_enabled
            or snapshot.system_status in {SystemStatus.PAUSED, SystemStatus.SHARING_OFF}
        )
        self._set_stopped(stopped)
        if stopped:
            return
        self.character_view.apply_snapshot(snapshot)
        self.status_label.setText(
            resolve_share_label(
                snapshot.status,
                snapshot.confidence,
                snapshot.duration_seconds,
                snapshot.system_status,
                self.config.smoothing.display_confidence_floor,
            )
        )
        self.duration_label.setText(format_duration(snapshot.duration_seconds))
        self.approachability_label.setText(
            APPROACHABILITY_LABELS_JA[snapshot.approachability]
        )
        self.updated_label.setText(
            f"{LAST_UPDATED_JA} {snapshot.updated_at.astimezone().strftime('%H:%M')}"
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Toggle fullscreen with F11."""
        if event.key() == Qt.Key.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
            event.accept()
            return
        super().keyPressEvent(event)
