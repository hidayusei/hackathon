"""Offscreen smoke tests for the two-screen UI."""

from datetime import datetime

from PySide6.QtCore import Qt

from conftest import FakeClock
from deskmate.app import DeskMateApp
from deskmate.config.loader import load_config
from deskmate.core.enums import AnimationId, DeskStatus, SystemStatus
from deskmate.core.types import StatusSnapshot
from deskmate.pipeline.runner import PipelineRunner
from deskmate.ui.bridge import UiBridge
from deskmate.ui.detail_window import DetailWindow
from deskmate.ui.widget_window import WidgetWindow


def _snapshot(status: DeskStatus, system: SystemStatus = SystemStatus.RUNNING):
    animation = {
        DeskStatus.FOCUSED: AnimationId.RUNNING,
        DeskStatus.IDLE: AnimationId.SITTING,
        DeskStatus.AWAY: AnimationId.SLEEPING,
    }[status]
    return StatusSnapshot(
        status,
        system,
        status.value,
        animation,
        10,
        0.8,
        10,
        False,
        True,
        datetime.now().astimezone(),
    )


def _windows():
    config = load_config({"input": {"source": "dummy"}})
    bridge = UiBridge(PipelineRunner(config, FakeClock()), config)
    return bridge, WidgetWindow(bridge, config), DetailWindow(bridge, config)


def test_two_windows_construct_offscreen(qt_app) -> None:
    _, widget, detail = _windows()
    assert widget and detail
    widget.deleteLater()
    detail.deleteLater()


def test_all_statuses_render_without_exception(qt_app) -> None:
    _, widget, detail = _windows()
    for status in DeskStatus:
        widget.apply_snapshot(_snapshot(status))
    widget.deleteLater()
    detail.deleteLater()


def test_widget_has_required_flags(qt_app) -> None:
    _, widget, _ = _windows()
    assert widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert widget.windowFlags() & Qt.WindowType.FramelessWindowHint


def test_context_menu_requests_detail(qtbot) -> None:
    _, widget, _ = _windows()
    detail_action = next(
        action for action in widget._build_context_menu().actions()
        if action.text() == "詳細"
    )
    with qtbot.waitSignal(widget.detail_requested):
        detail_action.trigger()


def test_detail_open_close_controls_subscription(qt_app) -> None:
    bridge, _, detail = _windows()
    detail.show()
    qt_app.processEvents()
    assert bridge._runner._detail_subscription
    detail.close()
    qt_app.processEvents()
    assert not bridge._runner._detail_subscription


def test_event_camera_mode_opens_detail_with_character(qt_app) -> None:
    config = load_config({"input": {"source": "dummy"}})
    app = DeskMateApp(config, show_event_camera=True)

    app.widget.show()
    app._show_detail()
    qt_app.processEvents()

    assert app.detail_window is not None
    assert app.detail_window.event_panel.isVisible()
    assert app.detail_window.character.isVisible()
    assert not hasattr(app.detail_window, "motion_panel")
    assert not hasattr(app.detail_window, "region_panel")
    assert not hasattr(app.detail_window, "feature_panel")
    assert not hasattr(app.detail_window, "history_panel")

    app.detail_window.close()
    app.widget.close()


def test_ui_debug_preview_is_shared_with_detail_character(qt_app) -> None:
    _, widget, detail = _windows()
    widget.apply_snapshot(_snapshot(DeskStatus.IDLE))

    widget._set_debug_preview(DeskStatus.FOCUSED, True)
    qt_app.processEvents()

    assert detail.character._renderer._animation is AnimationId.BREAK
    assert detail._debug_snapshot is not None

    widget._clear_debug_preview()
    qt_app.processEvents()
    assert detail._debug_snapshot is None
