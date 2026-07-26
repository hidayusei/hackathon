"""Step 1 core contract tests."""

from dataclasses import fields

import numpy as np
import pytest

from deskmate.core.clock import seconds_to_us, us_to_seconds
from deskmate.core.enums import DeskStatus
from deskmate.core.errors import DecodeError
from deskmate.core.types import EVENT_DTYPE, EventBatch, StatusSnapshot


def test_all_seven_desk_statuses_exist() -> None:
    assert len(DeskStatus) == 7


def test_event_dtype_matches_wire_contract() -> None:
    assert EVENT_DTYPE.names == ("x", "y", "t", "p")
    assert EVENT_DTYPE["x"] == np.dtype("<u2")
    assert EVENT_DTYPE["t"] == np.dtype("<i8")


def test_event_batch_from_records_validates_timestamp_order() -> None:
    with pytest.raises(DecodeError):
        EventBatch.from_records(
            [{"x": 1, "y": 2, "t": 2, "p": 1}, {"x": 1, "y": 2, "t": 1, "p": 0}],
            0,
        )


def test_event_batch_from_records_validates_required_fields() -> None:
    with pytest.raises(DecodeError):
        EventBatch.from_records([{"x": 1, "y": 2, "t": 1}], 0)


def test_status_snapshot_has_only_ten_safe_fields() -> None:
    assert {field.name for field in fields(StatusSnapshot)} == {
        "status",
        "system_status",
        "label",
        "animation",
        "duration_seconds",
        "confidence",
        "approachability",
        "approachability_label",
        "changed",
        "updated_at",
    }


def test_clock_unit_conversion() -> None:
    assert us_to_seconds(1_250_000) == pytest.approx(1.25)
    assert seconds_to_us(1.25) == 1_250_000
