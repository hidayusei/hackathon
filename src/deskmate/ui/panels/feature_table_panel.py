"""Private feature table panel."""

from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from deskmate.core.types import DetailFrame
from deskmate.ui.labels import FEATURE_PANEL_JA


class FeatureTablePanel(QWidget):
    """Display the stable FeatureFrame display mapping."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = QLabel(FEATURE_PANEL_JA)
        self.table = QTableWidget(0, 2)
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.table)

    def update_frame(self, detail: DetailFrame) -> None:
        """Replace table values."""
        values = detail.features.to_display_dict()
        values.update(
            {
                "rate_short": f"{detail.smoothed.rate_short:.3f}",
                "rate_long": f"{detail.smoothed.rate_long:.3f}",
                "area_short": f"{detail.smoothed.area_short:.3f}",
                "speed_short": f"{detail.smoothed.speed_short:.3f}",
                "cell_short": f"{detail.smoothed.cell_short:.3f}",
                "rate_cv_10s": f"{detail.smoothed.rate_cv_10s:.3f}",
                "change_score": f"{detail.smoothed.change_score:.3f}",
                "elapsed_seconds": f"{detail.smoothed.elapsed_seconds:.3f}",
            }
        )
        self.table.setRowCount(len(values))
        for row, (name, value) in enumerate(values.items()):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(value))
