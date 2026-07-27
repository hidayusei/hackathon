"""GIF and fallback character renderers."""

import abc
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QMovie, QPainter, QPen

from deskmate.config.schema import CharacterConfig
from deskmate.core.enums import AnimationId
from deskmate.core.errors import ConfigError


class CharacterRenderer(abc.ABC):
    """Paint a character into a caller-provided widget."""

    @abc.abstractmethod
    def set_animation(self, animation: AnimationId, changed: bool = False) -> None:
        """Select the current animation without restarting an unchanged GIF."""

    @abc.abstractmethod
    def advance(self, dt_seconds: float) -> None:
        """Advance renderer state when required."""

    @abc.abstractmethod
    def paint(self, painter: QPainter, rect: QRect) -> None:
        """Paint into the supplied rectangle."""

    @property
    @abc.abstractmethod
    def available_animations(self) -> frozenset[AnimationId]:
        """Return supported animations."""


class GifCharacterRenderer(CharacterRenderer):
    """Play the four supplied GIFs with integer nearest-neighbour scaling."""

    def __init__(self, config: CharacterConfig) -> None:
        root = Path(config.assets_dir)
        self._scale = config.scale
        self._movies: dict[AnimationId, QMovie] = {}
        for animation in AnimationId:
            path = root / f"{animation.value}.gif"
            if not path.is_file():
                raise ConfigError(f"missing character asset: {path}")
            movie = QMovie(str(path))
            movie.setCacheMode(QMovie.CacheMode.CacheAll)
            if not movie.isValid():
                raise ConfigError(f"invalid character GIF: {path}")
            movie.jumpToFrame(0)
            self._movies[animation] = movie
        self._animation = AnimationId.SITTING
        self._movies[self._animation].start()

    def set_animation(self, animation: AnimationId, changed: bool = False) -> None:
        """Switch GIF immediately while preserving unchanged playback."""

        del changed
        if animation is self._animation:
            return
        self._movies[self._animation].stop()
        self._animation = animation
        movie = self._movies[animation]
        movie.jumpToFrame(0)
        movie.start()

    def advance(self, dt_seconds: float) -> None:
        """QMovie advances from the Qt event loop."""

        del dt_seconds

    def paint(self, painter: QPainter, rect: QRect) -> None:
        """Paint the current frame at an integer scale with no smoothing."""

        frame = self._movies[self._animation].currentPixmap()
        if frame.isNull():
            self._movies[self._animation].jumpToFrame(0)
            frame = self._movies[self._animation].currentPixmap()
        available_scale = max(1, min(rect.width(), rect.height()) // 30)
        scale = min(self._scale, available_scale)
        target = 30 * scale
        scaled = frame.scaled(
            target,
            target,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        x = rect.x() + (rect.width() - target) // 2
        y = rect.y() + (rect.height() - target) // 2
        painter.drawPixmap(x, y, scaled)

    @property
    def available_animations(self) -> frozenset[AnimationId]:
        """Return all supplied animations."""

        return frozenset(self._movies)


class ShapeCharacterRenderer(CharacterRenderer):
    """Draw a compact non-image fallback."""

    def __init__(self, theme: object, config: CharacterConfig) -> None:
        del config
        self._theme = theme
        self._animation = AnimationId.SITTING

    def set_animation(self, animation: AnimationId, changed: bool = False) -> None:
        """Select the fallback colour and letter."""

        del changed
        self._animation = animation

    def advance(self, dt_seconds: float) -> None:
        """The fallback is intentionally static."""

        del dt_seconds

    def paint(self, painter: QPainter, rect: QRect) -> None:
        """Paint a coloured circle and ASCII status initial."""

        from deskmate.ui.theme import animation_color

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(animation_color(self._animation))
        painter.setPen(QPen(color.lighter(150), 2))
        painter.setBrush(color)
        inset = max(4, min(rect.width(), rect.height()) // 12)
        painter.drawEllipse(rect.adjusted(inset, inset, -inset, -inset))
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignCenter),
            {
                AnimationId.RUNNING: "F",
                AnimationId.SITTING: "I",
                AnimationId.SLEEPING: "N",
                AnimationId.BREAK: "!",
            }[self._animation],
        )
        painter.restore()

    @property
    def available_animations(self) -> frozenset[AnimationId]:
        """Return all canonical animations."""

        return frozenset(AnimationId)


def create_renderer(config: CharacterConfig, theme: object) -> CharacterRenderer:
    """Create the configured GIF or fallback renderer."""

    if config.renderer == "gif":
        return GifCharacterRenderer(config)
    return ShapeCharacterRenderer(theme, config)
