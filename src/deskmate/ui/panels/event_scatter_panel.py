"""Private polarity-colored event scatter panel."""

import pyqtgraph as pg
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from deskmate.core.types import DetailFrame
from deskmate.ui.labels import (
    EVENT_COUNT_JA,
    EVENTS_PANEL_JA,
    TRUNCATED_JA,
    WINDOW_JA,
)


class EventScatterPanel(QWidget):
    """Plot the subscribed private event preview and window metadata."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = QLabel(EVENTS_PANEL_JA)
        self.window_label = QLabel()
        self.plot = pg.PlotWidget()
        self.plot.setAspectLocked(True)
        self.plot.invertY(True)
        self.positive = pg.ScatterPlotItem(size=3, pen=None, brush="#F59E0B")
        self.negative = pg.ScatterPlotItem(size=3, pen=None, brush="#60A5FA")
        self.plot.addItem(self.positive)
        self.plot.addItem(self.negative)
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.window_label)
        layout.addWidget(self.plot)

    def update_frame(self, detail: DetailFrame) -> None:
        """Replace preview points without retaining prior raw arrays."""
        positive = detail.preview_p == 1
        self.positive.setData(detail.preview_x[positive], detail.preview_y[positive])
        self.negative.setData(detail.preview_x[~positive], detail.preview_y[~positive])
        truncated = f" / {TRUNCATED_JA}" if detail.features.global_features.event_count > detail.preview_x.size else ""
        self.window_label.setText(
            f"{WINDOW_JA} #{detail.features.window_index} / "
            f"{detail.features.duration_s * 1000:.0f} ms / "
            f"{EVENT_COUNT_JA} {detail.features.global_features.event_count}{truncated}"
        )
