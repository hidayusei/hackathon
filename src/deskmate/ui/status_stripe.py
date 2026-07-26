"""Compact confirmed-state timeline for the resident widget.

Privacy note: this widget accumulates its own history from StatusSnapshot only, which is
level L3 (abstract state) in privacy-design.md 2. It never touches DetailFrame, features
or coordinates, so showing it does not require the detail subscription to be enabled.
"""

from collections import deque

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from deskmate.core.enums import DeskStatus, SystemStatus
from deskmate.core.types import StatusSnapshot

from .theme import Theme, status_color


class StatusStripe(QWidget):
    """Draw the recent confirmed states as proportional colored segments."""

    def __init__(
        self,
        theme: Theme,
        window_seconds: float = 300.0,
        parent: QWidget | None = None,
        height: int = 10,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._window_seconds = max(1.0, window_seconds)
        self._samples: deque[tuple[float, DeskStatus, bool]] = deque(maxlen=2048)
        self._elapsed = 0.0
        self.setFixedHeight(height)
        self.setToolTip("直近の状態の推移")

    def apply_snapshot(self, snapshot: StatusSnapshot) -> None:
        """Append one sample, using the snapshot's own duration as the time base."""
        # duration_seconds restarts at 0 on every confirmed change, so it gives a
        # monotonic time base without reading any clock the pipeline does not own.
        if snapshot.changed or not self._samples:
            self._elapsed += 1.0
        else:
            self._elapsed = max(self._elapsed, snapshot.duration_seconds)
        live = snapshot.system_status in (SystemStatus.RUNNING, SystemStatus.SHARING_OFF)
        self._samples.append((self._elapsed, snapshot.status, live))
        self._trim()
        self.update()

    def _trim(self) -> None:
        cutoff = self._elapsed - self._window_seconds
        while len(self._samples) > 2 and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def clear(self) -> None:
        """Drop the retained history, e.g. when the pipeline restarts."""
        self._samples.clear()
        self._elapsed = 0.0
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the track, then one rounded segment run per state."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        area = QRectF(self.rect())
        radius = area.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._theme.track))
        painter.drawRoundedRect(area, radius, radius)

        if len(self._samples) < 2:
            return

        start = self._samples[0][0]
        span = max(1e-6, self._samples[-1][0] - start)
        painter.setClipPath(self._rounded_clip(area, radius))
        # Merge neighbouring samples that share a state, otherwise every 200 ms sample
        # becomes its own rect and the antialiased seams read as noise.
        for run_start, run_end, status, live in self._runs():
            x0 = area.left() + (run_start - start) / span * area.width()
            x1 = area.left() + (run_end - start) / span * area.width()
            color = QColor(status_color(status))
            if not live:
                color.setAlpha(70)
            painter.setBrush(color)
            painter.drawRect(QRectF(x0, area.top(), max(1.0, x1 - x0), area.height()))

    def _runs(self) -> list[tuple[float, float, DeskStatus, bool]]:
        """Collapse the sample list into (start, end, status, live) runs."""
        runs: list[tuple[float, float, DeskStatus, bool]] = []
        run_start, run_status, run_live = self._samples[0]
        previous = run_start
        for at, status, live in list(self._samples)[1:]:
            if status is not run_status or live is not run_live:
                runs.append((run_start, at, run_status, run_live))
                run_start, run_status, run_live = at, status, live
            previous = at
        runs.append((run_start, previous, run_status, run_live))
        return runs

    def _rounded_clip(self, area: QRectF, radius: float):
        from PySide6.QtGui import QPainterPath

        path = QPainterPath()
        path.addRoundedRect(area, radius, radius)
        return path
