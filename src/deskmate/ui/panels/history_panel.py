"""Private status-history and event-rate panel."""

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from deskmate.core.types import DetailFrame
from deskmate.ui.labels import HISTORY_PANEL_JA


class HistoryPanel(QWidget):
    """Show a recent activity series and textual state intervals."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = QLabel(HISTORY_PANEL_JA)
        self.states = QLabel()
        self.plot = pg.PlotWidget()
        self.curve = self.plot.plot(pen=pg.mkPen("#5B8DEF", width=2))
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.states)
        layout.addWidget(self.plot)

    def update_frame(self, detail: DetailFrame) -> None:
        """Update recent status intervals and rate series."""
        self.states.setText(" | ".join(entry.status.value for entry in detail.history[-8:]))
        self.curve.setData(np.arange(detail.rate_series.size), detail.rate_series)
