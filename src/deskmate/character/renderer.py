"""Painter-based character renderers."""

import abc
import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient

from deskmate.config.schema import CharacterConfig
from deskmate.core.enums import AnimationId

# Emoji stand-ins defined by status-definition.md 7.2. Replaced by real artwork via
# ImageCharacterRenderer once assets exist.
_GLYPHS: dict[AnimationId, str] = {
    AnimationId.WORKING_AT_DESK: "💻",
    AnimationId.TYPING: "⌨️",
    AnimationId.ORGANIZING_DESK: "🧹",
    AnimationId.DRINKING_TEA: "🍵",
    AnimationId.RESTING: "😌",
    AnimationId.LOOKING_AROUND: "👀",
    AnimationId.SLEEPING: "😴",
    AnimationId.TRANSITIONING: "🔄",
    AnimationId.UNKNOWN: "❔",
}

# Motion styles from status-definition.md 7.4: how each animation moves while looping.
_BOB = "bob"
_SWAY = "sway"
_SPIN = "spin"
_PULSE = "pulse"
_STILL = "still"

_MOTION: dict[AnimationId, str] = {
    AnimationId.TYPING: _BOB,
    AnimationId.WORKING_AT_DESK: _BOB,
    AnimationId.ORGANIZING_DESK: _SWAY,
    AnimationId.DRINKING_TEA: _STILL,
    AnimationId.RESTING: _PULSE,
    AnimationId.LOOKING_AROUND: _SWAY,
    AnimationId.SLEEPING: _PULSE,
    AnimationId.TRANSITIONING: _SPIN,
    AnimationId.UNKNOWN: _STILL,
}


class CharacterRenderer(abc.ABC):
    """Render a character into a caller-provided QPainter."""

    @abc.abstractmethod
    def set_animation(self, animation: AnimationId, changed: bool) -> None:
        """Select the current animation."""

    @abc.abstractmethod
    def advance(self, dt_seconds: float) -> None:
        """Advance animation phase."""

    @abc.abstractmethod
    def paint(self, painter: QPainter, rect: QRect) -> None:
        """Paint into rect."""

    @property
    @abc.abstractmethod
    def available_animations(self) -> frozenset[AnimationId]:
        """Return supported animation identifiers."""


class ShapeCharacterRenderer(CharacterRenderer):
    """Draw all states using shapes and compact glyphs."""

    def __init__(self, theme: object, config: CharacterConfig) -> None:
        self._theme = theme
        self._period = config.loop_period_seconds
        self._phase = 0.0
        self._animation = AnimationId.UNKNOWN
        self._changed = False

    def set_animation(self, animation: AnimationId, changed: bool) -> None:
        """Select an animation and reset phase only on change."""
        if animation is not self._animation or changed:
            self._phase = 0.0
        self._animation = animation
        self._changed = changed

    def advance(self, dt_seconds: float) -> None:
        """Advance the looping phase."""
        self._phase = (self._phase + dt_seconds / max(self._period, 0.001)) % 1.0

    def _accent(self) -> QColor:
        """Return the accent for the current animation, falling back to the theme."""
        from deskmate.ui.theme import animation_color

        try:
            return QColor(animation_color(self._animation))
        except Exception:  # noqa: BLE001 - never let styling break rendering
            fallback = getattr(self._theme, "character", "#5B8DEF")
            return QColor(fallback if isinstance(fallback, str) else "#5B8DEF")

    def paint(self, painter: QPainter, rect: QRect) -> None:
        """Paint the animated placeholder character: halo, body, glyph."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        wave = math.sin(self._phase * math.tau)
        motion = _MOTION.get(self._animation, _STILL)
        span = min(rect.width(), rect.height())
        dx = dy = 0.0
        scale = 1.0
        spin = 0.0
        if motion == _BOB:
            dy = wave * span * 0.035
        elif motion == _SWAY:
            dx = wave * span * 0.075
        elif motion == _PULSE:
            scale = 1.0 + wave * 0.05
        elif motion == _SPIN:
            spin = self._phase * 360.0

        accent = self._accent()
        centre = QPointF(rect.center().x() + 1 + dx, rect.center().y() + 1 + dy)
        radius = span * 0.42 * scale

        # Soft halo so the character reads against any wallpaper.
        halo = QRadialGradient(centre, radius * 1.55)
        glow = QColor(accent)
        glow.setAlpha(110)
        halo.setColorAt(0.55, glow)
        glow_edge = QColor(accent)
        glow_edge.setAlpha(0)
        halo.setColorAt(1.0, glow_edge)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(centre, radius * 1.55, radius * 1.55)

        # Body with a lighter rim for depth.
        body = QRadialGradient(
            QPointF(centre.x() - radius * 0.3, centre.y() - radius * 0.35), radius * 1.8
        )
        body.setColorAt(0.0, accent.lighter(135))
        body.setColorAt(1.0, accent.darker(125))
        painter.setBrush(body)
        painter.setPen(QPen(accent.lighter(160), max(1.0, span * 0.018)))
        painter.drawEllipse(centre, radius, radius)

        # Glyph, rotated only for the transition spin.
        painter.save()
        if spin:
            painter.translate(centre)
            painter.rotate(spin)
            painter.translate(-centre)
        glyph_font = QFont(painter.font())
        for family in ("Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"):
            glyph_font.setFamily(family)
            if glyph_font.exactMatch():
                break
        glyph_font.setPixelSize(max(10, int(radius * 0.95)))
        painter.setFont(glyph_font)
        painter.setPen(QColor("#FFFFFF"))
        box = QRect(
            int(centre.x() - radius), int(centre.y() - radius),
            int(radius * 2), int(radius * 2),
        )
        painter.drawText(box, int(Qt.AlignmentFlag.AlignCenter), _GLYPHS[self._animation])
        painter.restore()
        painter.restore()

    @property
    def available_animations(self) -> frozenset[AnimationId]:
        """Return all canonical animations."""
        return frozenset(AnimationId)


class ImageCharacterRenderer(CharacterRenderer):
    """Image renderer skeleton that delegates missing assets to shape rendering."""

    def __init__(self, theme: object, config: CharacterConfig) -> None:
        self._fallback = ShapeCharacterRenderer(theme, config)
        root = Path(config.assets_dir)
        self._assets = {
            animation
            for animation in AnimationId
            if (root / f"{animation.value}.gif").exists()
            or (root / f"{animation.value}.png").exists()
        }
        self.use_fallback = not bool(self._assets)

    def set_animation(self, animation: AnimationId, changed: bool) -> None:
        self._fallback.set_animation(animation, changed)

    def advance(self, dt_seconds: float) -> None:
        self._fallback.advance(dt_seconds)

    def paint(self, painter: QPainter, rect: QRect) -> None:
        self._fallback.paint(painter, rect)

    @property
    def available_animations(self) -> frozenset[AnimationId]:
        return self._fallback.available_animations


def create_renderer(config: CharacterConfig, theme: object) -> CharacterRenderer:
    """Create the configured renderer."""
    if config.renderer == "image":
        return ImageCharacterRenderer(theme, config)
    return ShapeCharacterRenderer(theme, config)
