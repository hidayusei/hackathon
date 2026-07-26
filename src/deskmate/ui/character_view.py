"""QWidget host for a CharacterRenderer."""

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPaintEvent, QPainter
from PySide6.QtWidgets import QWidget

from deskmate.character.renderer import CharacterRenderer
from deskmate.core.types import StatusSnapshot


class CharacterView(QWidget):
    """Advance and paint a replaceable character renderer."""

    def __init__(
        self,
        renderer: CharacterRenderer,
        size: int,
        parent: QWidget | None = None,
        fps: int = 20,
    ) -> None:
        super().__init__(parent)
        self._renderer = renderer
        self._interval_s = 1.0 / max(1, fps)
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(round(self._interval_s * 1000))
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        self._renderer.advance(self._interval_s)
        self.update()

    def apply_snapshot(self, snapshot: StatusSnapshot) -> None:
        """Apply the snapshot animation."""
        self._renderer.set_animation(snapshot.animation, snapshot.changed)
        self.update()

    def set_renderer(self, renderer: CharacterRenderer) -> None:
        """Replace the active renderer."""
        self._renderer = renderer
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the renderer into this widget."""
        painter = QPainter(self)
        self._renderer.paint(painter, self.rect())
