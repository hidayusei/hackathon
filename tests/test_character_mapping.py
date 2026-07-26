"""Step 7 animation mapping tests."""

import pytest

from deskmate.character.mapping import resolve_animation
from deskmate.character.renderer import ShapeCharacterRenderer
from deskmate.config.loader import load_config
from deskmate.core.enums import AnimationId, DeskStatus, SystemStatus


@pytest.mark.parametrize(
    ("status", "duration", "expected"),
    (
        (DeskStatus.FOCUSED, 10, AnimationId.TYPING),
        (DeskStatus.FOCUSED, 700, AnimationId.WORKING_AT_DESK),
        (DeskStatus.SHORT_BREAK, 5, AnimationId.DRINKING_TEA),
        (DeskStatus.SHORT_BREAK, 90, AnimationId.RESTING),
        (DeskStatus.NO_MOTION, 10, AnimationId.LOOKING_AROUND),
        (DeskStatus.NO_MOTION, 200, AnimationId.SLEEPING),
        (DeskStatus.ORGANIZING, 0, AnimationId.ORGANIZING_DESK),
        (DeskStatus.TRANSITION, 0, AnimationId.TRANSITIONING),
        (DeskStatus.UNKNOWN, 0, AnimationId.UNKNOWN),
    ),
)
def test_duration_mapping(status, duration, expected) -> None:
    assert resolve_animation(status, duration) is expected


def test_paused_overrides_desk_status() -> None:
    assert resolve_animation(DeskStatus.FOCUSED, 10, SystemStatus.PAUSED) is AnimationId.RESTING


def test_no_signal_overrides_desk_status() -> None:
    assert resolve_animation(DeskStatus.FOCUSED, 10, SystemStatus.NO_SIGNAL) is AnimationId.UNKNOWN


def test_every_status_maps_at_zero_duration() -> None:
    assert all(isinstance(resolve_animation(status, 0), AnimationId) for status in DeskStatus)


def test_shape_renderer_supports_all_animations() -> None:
    renderer = ShapeCharacterRenderer(object(), load_config().character)
    assert renderer.available_animations == frozenset(AnimationId)
