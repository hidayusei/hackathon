"""Private motion range, centroid, and change panel."""

import pyqtgraph as pg
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from deskmate.core.types import DetailFrame
from deskmate.ui.labels import MOTION_PANEL_JA


class MotionPanel(QWidget):
    """Plot current centroid and show range/change aggregates."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = QLabel(MOTION_PANEL_JA)
        self.values = QLabel()
        self.plot = pg.PlotWidget()
        self.plot.setAspectLocked(True)
        self.plot.invertY(True)
        self.centroid = pg.ScatterPlotItem(size=10, symbol="+", pen="#EF4444")
        self.plot.addItem(self.centroid)
        self._trajectory_x: list[float] = []
        self._trajectory_y: list[float] = []
        self.trajectory = self.plot.plot(pen=pg.mkPen("#9CA3AF", width=1))
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.values)
        layout.addWidget(self.plot)

    def update_frame(self, detail: DetailFrame) -> None:
        """Update bbox metrics, centroid, trajectory, and change metrics."""
        g = detail.features.global_features
        self._trajectory_x = [*self._trajectory_x[-19:], g.centroid_x]
        self._trajectory_y = [*self._trajectory_y[-19:], g.centroid_y]
        self.centroid.setData([g.centroid_x], [g.centroid_y])
        self.trajectory.setData(self._trajectory_x, self._trajectory_y)
        self.values.setText(
            f"bbox {g.bbox_width:.1f} × {g.bbox_height:.1f} px / "
            f"area {g.bbox_area_ratio:.3f} / speed {g.centroid_speed:.1f} px/s / "
            f"delta {g.event_rate_delta:.1f} eps / change {detail.smoothed.change_score:.3f}"
        )
