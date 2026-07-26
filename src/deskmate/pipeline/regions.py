"""Fast coordinate-to-region lookup."""

from dataclasses import dataclass

import numpy as np

from deskmate.core.enums import RegionId
from deskmate.core.errors import ConfigError


REGION_ORDER: tuple[RegionId, ...] = (
    RegionId.KEYBOARD,
    RegionId.MOUSE,
    RegionId.CENTER,
    RegionId.LEFT,
    RegionId.RIGHT,
    RegionId.OTHER,
)


@dataclass(frozen=True, slots=True)
class RegionRect:
    """One normalized desk region rectangle."""

    region_id: RegionId
    x0: float
    y0: float
    x1: float
    y1: float


class RegionMap:
    """Precompute a compact region lookup table."""

    def __init__(self, rects: list[RegionRect], width: int, height: int) -> None:
        ids = [rect.region_id for rect in rects]
        if len(ids) != len(set(ids)):
            raise ConfigError("region ids must be unique")
        if RegionId.OTHER in ids:
            raise ConfigError("other region is implicit")
        for rect in rects:
            if not all(0 <= value <= 1 for value in (rect.x0, rect.y0, rect.x1, rect.y1)):
                raise ConfigError("region rectangle is outside [0, 1]")
            if rect.x0 >= rect.x1 or rect.y0 >= rect.y1:
                raise ConfigError("region rectangle has no area")
        self.width = width
        self.height = height
        self.rects = tuple(rects)
        other = REGION_ORDER.index(RegionId.OTHER)
        table = np.full((height, width), other, dtype=np.int8)
        for rect in reversed(rects):
            x0, x1 = int(rect.x0 * width), int(np.ceil(rect.x1 * width))
            y0, y1 = int(rect.y0 * height), int(np.ceil(rect.y1 * height))
            table[y0:min(y1, height), x0:min(x1, width)] = REGION_ORDER.index(rect.region_id)
        table.setflags(write=False)
        self._lookup = table
        self._centers = {
            rect.region_id: (
                (rect.x0 + rect.x1) * width / 2,
                (rect.y0 + rect.y1) * height / 2,
            )
            for rect in rects
        }
        self._centers[RegionId.OTHER] = (width / 2, height / 2)

    def assign(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Return REGION_ORDER indexes for coordinate arrays."""
        return self._lookup[y, x]

    @property
    def lookup_table(self) -> np.ndarray:
        """Return the immutable (height, width) int8 lookup."""
        return self._lookup

    def center_px(self, region_id: RegionId) -> tuple[float, float]:
        """Return the configured rectangle center in sensor pixels."""
        return self._centers[region_id]
