"""Step 4 region map tests."""

import numpy as np
import pytest

from deskmate.core.enums import RegionId
from deskmate.core.errors import ConfigError
from deskmate.pipeline.regions import REGION_ORDER, RegionMap, RegionRect


def _map() -> RegionMap:
    return RegionMap(
        [RegionRect(RegionId.KEYBOARD, 0.25, 0.62, 0.75, 1.0)], 320, 320
    )


def test_keyboard_center_assignment() -> None:
    assert _map().assign(np.array([160]), np.array([260]))[0] == REGION_ORDER.index(RegionId.KEYBOARD)


def test_unmatched_coordinate_is_other() -> None:
    assert _map().assign(np.array([1]), np.array([1]))[0] == REGION_ORDER.index(RegionId.OTHER)


def test_first_overlapping_rectangle_wins() -> None:
    mapping = RegionMap(
        [
            RegionRect(RegionId.KEYBOARD, 0, 0, 1, 1),
            RegionRect(RegionId.MOUSE, 0, 0, 1, 1),
        ], 10, 10,
    )
    assert mapping.assign(np.array([5]), np.array([5]))[0] == 0


@pytest.mark.parametrize(
    "rects",
    (
        [RegionRect(RegionId.KEYBOARD, -1, 0, 1, 1)],
        [RegionRect(RegionId.KEYBOARD, 1, 0, 1, 1)],
        [RegionRect(RegionId.OTHER, 0, 0, 1, 1)],
        [RegionRect(RegionId.KEYBOARD, 0, 0, 1, 1), RegionRect(RegionId.KEYBOARD, 0, 0, 1, 1)],
    ),
)
def test_invalid_region_definition_raises(rects: list[RegionRect]) -> None:
    with pytest.raises(ConfigError):
        RegionMap(rects, 10, 10)


def test_lookup_shape_and_dtype() -> None:
    assert _map().lookup_table.shape == (320, 320)
    assert _map().lookup_table.dtype == np.int8
