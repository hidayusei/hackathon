"""Resident widget presentation tests."""

from datetime import datetime

from conftest import FakeClock
from deskmate.character.renderer import _GLYPHS, _MOTION, ShapeCharacterRenderer
from deskmate.config.loader import load_config
from deskmate.core.enums import AnimationId, Approachability, DeskStatus, SystemStatus
from deskmate.core.types import StatusSnapshot
from deskmate.pipeline.runner import PipelineRunner
from deskmate.ui.bridge import UiBridge
from deskmate.ui.status_stripe import StatusStripe
from deskmate.ui.theme import STATUS_COLORS, animation_color, resolve_theme, status_color
from deskmate.ui.widget_window import WidgetWindow


def _snapshot(status, duration=10.0, confidence=0.8,
              system=SystemStatus.RUNNING, changed=False):
    return StatusSnapshot(
        status, system, status.value, AnimationId.UNKNOWN, duration, confidence,
        Approachability.UNDETERMINED, "", changed, datetime.now().astimezone(),
    )


def _widget():
    config = load_config()
    bridge = UiBridge(PipelineRunner(config, FakeClock()), config)
    return config, WidgetWindow(bridge, config)


# ------------------------------------------------------------------ sizing
def test_widget_uses_configured_size(qt_app) -> None:
    config, widget = _widget()
    assert widget.width() == config.ui.widget.width
    assert widget.height() == config.ui.widget.height
    widget.deleteLater()


def test_widget_default_size_is_readable_at_a_glance(qt_app) -> None:
    """The resident widget must stay large enough for its four text rows."""
    config = load_config()
    assert config.ui.widget.width >= 400
    assert config.ui.widget.height >= 220
    assert config.ui.widget.character_size >= 120


def test_minimized_mode_shrinks_to_the_configured_square(qt_app) -> None:
    config, widget = _widget()
    widget.toggle_minimized()
    assert widget.width() == config.ui.widget.minimized_size
    assert widget.height() == config.ui.widget.minimized_size
    assert widget.status_label.isHidden()
    widget.toggle_minimized()
    assert widget.width() == config.ui.widget.width
    assert not widget.status_label.isHidden()
    widget.deleteLater()


# ------------------------------------------------------------------ content
def test_widget_shows_duration_and_confidence_percent(qt_app) -> None:
    _, widget = _widget()
    widget.apply_snapshot(_snapshot(DeskStatus.FOCUSED, duration=312.0, confidence=0.78))
    assert widget.duration_label.text() == "5分12秒"
    assert widget.confidence_value.text() == "78%"
    assert widget.confidence_bar.value() == 78
    widget.deleteLater()


def test_pause_button_glyph_has_no_emoji_presentation(qt_app) -> None:
    """Control glyphs must not fall back to the colour emoji font."""
    from deskmate.ui.widget_window import GLYPH_DETAIL, GLYPH_PAUSE, GLYPH_RESUME, GLYPH_SHARE

    emoji_controls = {"⏸", "▶", "⏹", "⏯"}
    for glyph in (GLYPH_DETAIL, GLYPH_SHARE, GLYPH_PAUSE, GLYPH_RESUME):
        assert glyph not in emoji_controls
        assert "️" not in glyph


def test_pause_button_toggles_glyph_on_pause(qt_app) -> None:
    from deskmate.ui.widget_window import GLYPH_PAUSE, GLYPH_RESUME

    _, widget = _widget()
    widget.apply_snapshot(_snapshot(DeskStatus.FOCUSED))
    assert widget.pause_button.text() == GLYPH_PAUSE
    widget.apply_snapshot(_snapshot(DeskStatus.UNKNOWN, system=SystemStatus.PAUSED))
    assert widget.pause_button.text() == GLYPH_RESUME
    widget.deleteLater()


def test_widget_renders_every_status_without_exception(qt_app) -> None:
    _, widget = _widget()
    for status in DeskStatus:
        for system in SystemStatus:
            widget.apply_snapshot(_snapshot(status, system=system))
    widget.deleteLater()


# ------------------------------------------------------------------ character
def test_every_animation_has_a_glyph_and_motion() -> None:
    for animation in AnimationId:
        assert animation in _GLYPHS
        assert animation in _MOTION


def test_glyphs_are_emoji_placeholders_not_ascii() -> None:
    """status-definition.md 7.2 specifies emoji stand-ins until artwork exists."""
    for animation, glyph in _GLYPHS.items():
        assert any(ord(ch) > 0x2000 for ch in glyph), (animation, glyph)


def test_shape_renderer_supports_all_animations() -> None:
    config = load_config()
    renderer = ShapeCharacterRenderer(resolve_theme(config.ui.theme), config.character)
    assert renderer.available_animations == frozenset(AnimationId)


def test_every_animation_maps_to_a_colour() -> None:
    for animation in AnimationId:
        assert animation_color(animation).startswith("#")


def test_every_status_maps_to_a_distinct_colour() -> None:
    for status in DeskStatus:
        assert status in STATUS_COLORS
        assert status_color(status).startswith("#")
    assert len(set(STATUS_COLORS.values())) == len(DeskStatus)


# ------------------------------------------------------------------ history stripe
def test_stripe_merges_contiguous_runs(qt_app) -> None:
    theme = resolve_theme("dark")
    stripe = StatusStripe(theme, window_seconds=300.0)
    for index in range(1, 6):
        stripe.apply_snapshot(_snapshot(DeskStatus.FOCUSED, duration=float(index)))
    for index in range(1, 4):
        stripe.apply_snapshot(
            _snapshot(DeskStatus.SHORT_BREAK, duration=float(index), changed=(index == 1))
        )
    runs = stripe._runs()
    assert [run[2] for run in runs] == [DeskStatus.FOCUSED, DeskStatus.SHORT_BREAK]
    stripe.deleteLater()


def test_stripe_drops_samples_outside_its_window(qt_app) -> None:
    stripe = StatusStripe(resolve_theme("dark"), window_seconds=5.0)
    for index in range(1, 60):
        stripe.apply_snapshot(
            _snapshot(DeskStatus.WORKING, duration=float(index), changed=True)
        )
    assert len(stripe._samples) < 59
    stripe.deleteLater()


def test_stripe_clear_empties_history(qt_app) -> None:
    stripe = StatusStripe(resolve_theme("dark"))
    stripe.apply_snapshot(_snapshot(DeskStatus.FOCUSED))
    stripe.clear()
    assert not stripe._samples
    stripe.deleteLater()


def test_stripe_never_reads_feature_data() -> None:
    """The stripe is fed StatusSnapshot only, so it needs no detail subscription.

    Checked against identifiers rather than raw text: the module docstring names the
    forbidden types on purpose to explain why they are absent.
    """
    import ast
    import inspect

    import deskmate.ui.status_stripe as module

    tree = ast.parse(inspect.getsource(module))
    identifiers = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    } | {
        alias.name for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    for forbidden in ("FeatureFrame", "DetailFrame", "EventWindow", "detail_updated"):
        assert forbidden not in identifiers
