"""Private inspection window showing the full inference process."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from deskmate.character.renderer import create_renderer
from deskmate.config.schema import AppConfig
from deskmate.core.enums import DeskStatus
from deskmate.core.types import DetailFrame, StatusSnapshot

from .bridge import UiBridge
from .character_view import CharacterView
from .labels import (
    AWAY_NOTE_JA,
    CANDIDATE_JA,
    CURRENT_STATUS_JA,
    DETAIL_TITLE_JA,
    RULE_JA,
    format_duration,
)
from .panels import EventScatterPanel
from .theme import resolve_theme


class StatusHeader(QWidget):
    """Show confirmed/candidate status, duration, confidence, and rule."""

    def __init__(self, character: CharacterView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.character = character
        self.status = QLabel()
        self.rule = QLabel()
        self.note = QLabel()
        self.note.setObjectName("awayNote")
        self.note.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(CURRENT_STATUS_JA))
        layout.addWidget(character)
        layout.addWidget(self.status)
        layout.addWidget(self.rule)
        layout.addWidget(self.note)

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
        # The "away" caveat lives here, on the explanatory screen only, so the
        # main window stays clean (status-definition.md 10.1).
        self.note.setText(
            AWAY_NOTE_JA if snapshot.status is DeskStatus.AWAY else ""
        )


class DetailWindow(QMainWindow):
    """Show only the live event preview and the original character."""

    def __init__(self, bridge: UiBridge, config: AppConfig) -> None:
        super().__init__()
        self.bridge = bridge
        self.config = config
        self.setWindowTitle(DETAIL_TITLE_JA)
        self.resize(900, 520)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        central = QWidget()
        root = QHBoxLayout(central)
        self.event_panel = EventScatterPanel(config.sensor)
        self.character = CharacterView(
            create_renderer(config.character, resolve_theme(config.ui.theme)),
            config.ui.detail.character_size,
        )
        root.addWidget(self.event_panel, 1)
        root.addWidget(self.character, 0, Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(central)
        bridge.detail_updated.connect(self.apply_detail)

    def apply_detail(self, detail: DetailFrame) -> None:
        """Update the two visible elements from one private frame."""
        self.event_panel.update_frame(detail)
        self.character.apply_snapshot(detail.snapshot)

    def showEvent(self, event: QShowEvent) -> None:
        """Subscribe when displayed."""
        self.bridge.open_detail()
        super().showEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Unsubscribe before destruction."""
        self.bridge.close_detail()
        super().closeEvent(event)
