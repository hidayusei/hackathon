"""Compact break-prompt banner for the main window."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .bridge import UiBridge
from .labels import (
    BREAK_BODY_JA,
    BREAK_SNOOZE_JA,
    BREAK_TAKEN_JA,
    BREAK_TITLE_JA,
    format_duration,
)


class BreakBanner(QWidget):
    """Show a dismissible prompt while the inferred state remains focused."""

    def __init__(self, bridge: UiBridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("breakBanner")
        self.title = QLabel(BREAK_TITLE_JA)
        self.title.setObjectName("breakTitle")
        self.body = QLabel()
        self.snooze_button = QPushButton(BREAK_SNOOZE_JA)
        self.taken_button = QPushButton(BREAK_TAKEN_JA)
        buttons = QHBoxLayout()
        buttons.addWidget(self.snooze_button)
        buttons.addWidget(self.taken_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.addWidget(self.title)
        layout.addWidget(self.body)
        layout.addLayout(buttons)
        self.snooze_button.clicked.connect(bridge.snooze_break)
        self.taken_button.clicked.connect(bridge.acknowledge_break)
        self.hide()

    def apply(self, due: bool, focus_seconds: float) -> None:
        """Update prompt visibility and focused duration."""

        self.body.setText(
            BREAK_BODY_JA.format(duration=format_duration(focus_seconds))
        )
        self.setVisible(due)
