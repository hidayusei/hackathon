"""AUTO resolution and delayed Metavision import tests."""

import builtins
import importlib
import sys
import types

import numpy as np
import pytest

from deskmate.config.loader import load_config
from deskmate.config.schema import InputConfig, MetavisionInputConfig, SensorConfig
from deskmate.core.enums import SourceKind
from deskmate.core.errors import SourceOpenError
from deskmate.input.dummy_source import DummyEventSource
from deskmate.input.file_source import FileEventSource
from deskmate.input.factory import create_event_source, resolve_source_kind
from deskmate.input.metavision_source import MetavisionEventSource


def test_auto_selects_metavision_when_sdk_is_detected(monkeypatch) -> None:
    monkeypatch.setattr(
        "deskmate.input.factory.importlib.util.find_spec", lambda _name: object()
    )
    assert resolve_source_kind(SourceKind.AUTO)[0] is SourceKind.METAVISION


def test_auto_selects_visible_dummy_mode_without_sdk(monkeypatch) -> None:
    monkeypatch.setattr(
        "deskmate.input.factory.importlib.util.find_spec", lambda _name: None
    )
    kind, reason = resolve_source_kind(SourceKind.AUTO)
    assert kind is SourceKind.DUMMY
    assert "DUMMY MODE" in reason


def test_explicit_metavision_is_never_silently_replaced(monkeypatch) -> None:
    monkeypatch.setattr(
        "deskmate.input.factory.importlib.util.find_spec", lambda _name: None
    )
    assert resolve_source_kind(SourceKind.METAVISION)[0] is SourceKind.METAVISION


def test_windows_auto_factory_returns_dummy(monkeypatch) -> None:
    monkeypatch.setattr(
        "deskmate.input.factory.importlib.util.find_spec", lambda _name: None
    )
    source = create_event_source(InputConfig(source="auto"), SensorConfig())
    assert isinstance(source, DummyEventSource)
    assert "DUMMY MODE" in source.resolution_reason


def test_replay_factory_uses_portable_file_source(tmp_path) -> None:
    source = create_event_source(
        InputConfig(source="replay", file={"path": tmp_path / "events.npz"}),
        SensorConfig(),
    )
    assert isinstance(source, FileEventSource)


def test_metavision_module_import_does_not_import_sdk(monkeypatch) -> None:
    imported: list[str] = []
    original = builtins.__import__

    def tracking(name, *args, **kwargs):
        if name.startswith("metavision_core"):
            imported.append(name)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", tracking)
    importlib.reload(sys.modules["deskmate.input.metavision_source"])
    assert imported == []


def test_metavision_open_error_contains_pi_setup(monkeypatch) -> None:
    source = MetavisionEventSource(MetavisionInputConfig(), SensorConfig())
    monkeypatch.setitem(sys.modules, "metavision_core", None)
    with pytest.raises(SourceOpenError, match="rp5_setup_v4l.sh"):
        source.open()


def test_metavision_converts_structured_events(monkeypatch) -> None:
    dtype = np.dtype([("x", "<u2"), ("y", "<u2"), ("p", "<i2"), ("t", "<i8")])
    events = np.array([(1, 2, 1, 10), (3, 4, 0, 20)], dtype=dtype)

    class FakeIterator:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __iter__(self):
            return iter((events,))

        def get_size(self):
            return (320, 320)

    event_io = types.ModuleType("metavision_core.event_io")
    event_io.EventsIterator = FakeIterator
    package = types.ModuleType("metavision_core")
    package.event_io = event_io
    monkeypatch.setitem(sys.modules, "metavision_core", package)
    monkeypatch.setitem(sys.modules, "metavision_core.event_io", event_io)
    source = MetavisionEventSource(MetavisionInputConfig(), SensorConfig())
    source.open()
    batch = source.read(0)
    assert batch is not None
    assert batch.size == 2
    assert batch.p.tolist() == [1, 0]


def test_metavision_empty_batches_advance_sensor_time(monkeypatch) -> None:
    dtype = np.dtype([("x", "<u2"), ("y", "<u2"), ("p", "<i2"), ("t", "<i8")])

    class FakeIterator:
        def __init__(self, **kwargs):
            pass

        def __iter__(self):
            empty = np.empty(0, dtype=dtype)
            return iter((empty, empty))

        def get_size(self):
            return (320, 320)

    event_io = types.ModuleType("metavision_core.event_io")
    event_io.EventsIterator = FakeIterator
    package = types.ModuleType("metavision_core")
    package.event_io = event_io
    monkeypatch.setitem(sys.modules, "metavision_core", package)
    monkeypatch.setitem(sys.modules, "metavision_core.event_io", event_io)
    source = MetavisionEventSource(
        MetavisionInputConfig(delta_t_us=20_000), SensorConfig()
    )
    source.open()
    first = source.read(0)
    second = source.read(0)
    assert first is not None and second is not None
    assert (first.t_start_us, first.t_end_us) == (0, 20_000)
    assert (second.t_start_us, second.t_end_us) == (20_000, 40_000)
