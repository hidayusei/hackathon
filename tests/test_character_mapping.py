"""Three-state and break animation mapping tests."""

import pytest
from PySide6.QtGui import QMovie

from deskmate.character.mapping import resolve_animation
from deskmate.character.renderer import GifCharacterRenderer, ShapeCharacterRenderer
from deskmate.config.loader import load_config
from deskmate.core.enums import AnimationId, DeskStatus, SystemStatus
from deskmate.ui.theme import resolve_theme


@pytest.mark.parametrize(
    ("status", "break_due", "expected"),
    (
        (DeskStatus.FOCUSED, False, AnimationId.RUNNING),
        (DeskStatus.IDLE, False, AnimationId.SITTING),
        (DeskStatus.AWAY, False, AnimationId.SLEEPING),
        (DeskStatus.FOCUSED, True, AnimationId.BREAK),
    ),
)
def test_mapping(status, break_due, expected) -> None:
    assert resolve_animation(status, break_due) is expected


def test_system_status_overrides_break_prompt() -> None:
    assert resolve_animation(
        DeskStatus.FOCUSED, True, SystemStatus.PAUSED
    ) is AnimationId.SITTING


def test_gif_renderer_loads_all_four_assets(qt_app) -> None:
    renderer = GifCharacterRenderer(load_config().character)
    assert renderer.available_animations == frozenset(AnimationId)


def test_supplied_gifs_are_30px_ten_frame_infinite_loops(qt_app) -> None:
    root = load_config().character.assets_dir
    for animation in AnimationId:
        movie = QMovie(str(root / f"{animation.value}.gif"))
        assert movie.isValid()
        assert movie.frameCount() == 10
        assert movie.loopCount() == -1
        assert movie.jumpToFrame(0)
        assert movie.currentPixmap().size().width() == 30
        assert movie.currentPixmap().size().height() == 30


def test_shape_renderer_supports_all_animations(qt_app) -> None:
    config = load_config()
    renderer = ShapeCharacterRenderer(resolve_theme("dark"), config.character)
    assert renderer.available_animations == frozenset(AnimationId)
