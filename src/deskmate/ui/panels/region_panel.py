"""Private six-region activity and heatmap panel."""

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from deskmate.core.types import DetailFrame
from deskmate.pipeline.regions import REGION_ORDER
from deskmate.ui.labels import REGION_PANEL_JA


class RegionPanel(QWidget):
    """Render region shares/rates and the aggregate grid heatmap."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = QLabel(REGION_PANEL_JA)
        self.values = QLabel()
        self.image = pg.ImageView()
        self.image.ui.roiBtn.hide()
        self.image.ui.menuBtn.hide()
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.values)
        layout.addWidget(self.image)

    def update_frame(self, detail: DetailFrame) -> None:
        """Update all six region lines and the heatmap."""
        self.values.setText(
            "\n".join(
                f"{region.value}: {detail.features.regions[region].share:.1%} / "
                f"{detail.features.regions[region].event_rate_eps:.0f} eps"
                for region in REGION_ORDER
            )
        )
        self.image.setImage(np.asarray(detail.features.grid_counts).T, autoLevels=True)
