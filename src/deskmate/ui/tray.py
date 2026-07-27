"""System tray icon and application actions."""

from collections.abc import Callable

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from deskmate.core.enums import DeskStatus
from deskmate.core.types import StatusSnapshot

from .bridge import UiBridge
from .labels import (
    DETAIL_BUTTON_JA,
    PAUSE_BUTTON_JA,
    QUIT_BUTTON_JA,
    WINDOW_TITLE_JA,
    format_duration,
)
from .theme import status_color


def build_status_icon(status: DeskStatus, size: int = 32) -> QIcon:
    """Draw a state-coloured tray circle."""

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(status_color(status)))
    inset = size * 0.14
    painter.drawEllipse(
        QPointF(size / 2, size / 2), size / 2 - inset, size / 2 - inset
    )
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QSystemTrayIcon):
    """Expose the main window, detail view, pause, and quit actions."""

    def __init__(
        self,
        bridge: UiBridge,
        widget: QWidget,
        show_detail: Callable[[], None],
        quit_app: Callable[[], None],
    ) -> None:
        super().__init__(build_status_icon(DeskStatus.IDLE), widget)
        self._widget = widget
        self.setToolTip(WINDOW_TITLE_JA)
        menu = QMenu()
        show_widget = QAction(WINDOW_TITLE_JA, menu)
        detail = QAction(DETAIL_BUTTON_JA, menu)
        pause = QAction(PAUSE_BUTTON_JA, menu)
        quit_action = QAction(QUIT_BUTTON_JA, menu)
        show_widget.triggered.connect(self._show_widget)
        detail.triggered.connect(show_detail)
        pause.triggered.connect(lambda: bridge.set_paused(True))
        quit_action.triggered.connect(quit_app)
        menu.addActions([show_widget, detail, pause, quit_action])
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)
        bridge.snapshot_updated.connect(self.apply_snapshot)

    def apply_snapshot(self, snapshot: StatusSnapshot) -> None:
        """Update tray colour and tooltip."""

        self.setIcon(build_status_icon(snapshot.status))
        self.setToolTip(
            f"{WINDOW_TITLE_JA} — {snapshot.label} "
            f"{format_duration(snapshot.duration_seconds)}"
        )

    def _show_widget(self) -> None:
        self._widget.show()
        self._widget.raise_()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_widget()
