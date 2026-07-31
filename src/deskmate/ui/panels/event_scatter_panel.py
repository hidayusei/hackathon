"""Private event frame rendered with Metavision's native frame generator."""

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from deskmate.config.schema import SensorConfig
from deskmate.core.types import DetailFrame, EVENT_DTYPE_METAVISION
from deskmate.ui.labels import (
    EVENT_COUNT_JA,
    EVENTS_PANEL_JA,
    TRUNCATED_JA,
    WINDOW_JA,
)


class EventScatterPanel(QWidget):
    """Plot the subscribed private event preview and window metadata."""

    def __init__(
        self,
        sensor: SensorConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.title = QLabel(EVENTS_PANEL_JA)
        self.window_label = QLabel()
        self.configured_width = sensor.width if sensor is not None else 320
        self.configured_height = sensor.height if sensor is not None else 320
        self.plot = pg.PlotWidget()
        self.plot.setAspectLocked(True)
        self.plot.invertY(True)
        self.plot.hideAxis("left")
        self.plot.hideAxis("bottom")
        if sensor is not None:
            self.plot.setXRange(0, sensor.width, padding=0)
            self.plot.setYRange(0, sensor.height, padding=0)
            self.plot.setLimits(
                xMin=0,
                xMax=sensor.width,
                yMin=0,
                yMax=sensor.height,
            )
        self.frame = pg.ImageItem(axisOrder="row-major")
        self.plot.addItem(self.frame)
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.window_label)
        layout.addWidget(self.plot)

    def update_frame(self, detail: DetailFrame) -> None:
        """Render one complete window using the same generator as Metavision Viewer."""
        events = np.empty(detail.preview_x.size, dtype=EVENT_DTYPE_METAVISION)
        events["x"] = detail.preview_x
        events["y"] = detail.preview_y
        events["p"] = detail.preview_p
        events["t"] = np.arange(detail.preview_x.size, dtype=np.int64)
        image = np.empty(
            (self.configured_height, self.configured_width, 3),
            dtype=np.uint8,
        )
        try:
            from metavision_sdk_core import BaseFrameGenerationAlgorithm

            BaseFrameGenerationAlgorithm.generate_frame(events, image)
        except ImportError:
            image.fill(52)
            image[detail.preview_y, detail.preview_x] = np.where(
                detail.preview_p[:, None] == 1,
                (201, 126, 64),
                (80, 80, 80),
            )
        self.frame.setImage(image, autoLevels=False)
        truncated = f" / {TRUNCATED_JA}" if detail.features.global_features.event_count > detail.preview_x.size else ""
        self.window_label.setText(
            f"{WINDOW_JA} #{detail.features.window_index} / "
            f"{detail.features.duration_s * 1000:.0f} ms / "
            f"{EVENT_COUNT_JA} {detail.features.global_features.event_count}{truncated}"
        )
