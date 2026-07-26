"""Step 13 offscreen UI smoke and privacy tests."""

from datetime import datetime

from PySide6.QtCore import Qt

from conftest import FakeClock
from deskmate.config.loader import load_config
from deskmate.core.enums import AnimationId, Approachability, DeskStatus, SystemStatus
from deskmate.core.types import StatusSnapshot
from deskmate.pipeline.runner import PipelineRunner
from deskmate.ui.bridge import UiBridge
from deskmate.ui.detail_window import DetailWindow
from deskmate.ui.share_window import ShareWindow
from deskmate.ui.widget_window import WidgetWindow


def _snapshot(status: DeskStatus, system: SystemStatus = SystemStatus.RUNNING):
    return StatusSnapshot(
        status, system, status.value, AnimationId.UNKNOWN, 10, 0.8,
        Approachability.UNDETERMINED, "", True, datetime.now().astimezone(),
    )


def _windows():
    config = load_config()
    bridge = UiBridge(PipelineRunner(config, FakeClock()), config)
    return bridge, WidgetWindow(bridge, config), ShareWindow(bridge, config), DetailWindow(bridge, config)


def test_three_windows_construct_offscreen(qt_app) -> None:
    _, widget, share, detail = _windows()
    assert widget and share and detail
    widget.deleteLater(); share.deleteLater(); detail.deleteLater()


def test_all_statuses_render_without_exception(qt_app) -> None:
    _, widget, share, detail = _windows()
    for status in DeskStatus:
        snapshot = _snapshot(status)
        widget.apply_snapshot(snapshot)
        share.apply_snapshot(snapshot)
    widget.deleteLater(); share.deleteLater(); detail.deleteLater()


def test_share_has_no_detail_signal_connection(qt_app) -> None:
    _, _, share, _ = _windows()
    assert "detail_updated" not in share.received_signals


def test_widget_has_required_flags(qt_app) -> None:
    _, widget, _, _ = _windows()
    assert widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert widget.windowFlags() & Qt.WindowType.FramelessWindowHint


def test_share_stop_hides_previous_state(qt_app) -> None:
    bridge, _, share, _ = _windows()
    bridge.set_sharing_enabled(False)
    share.apply_snapshot(_snapshot(DeskStatus.FOCUSED, SystemStatus.SHARING_OFF))
    assert share.stopped_label.isVisible() or not share.stopped_label.isHidden()
    assert share.status_label.isHidden()


def test_detail_open_close_controls_subscription(qt_app) -> None:
    bridge, _, _, detail = _windows()
    detail.show()
    qt_app.processEvents()
    assert bridge._runner._detail_subscription
    detail.close()
    qt_app.processEvents()
    assert not bridge._runner._detail_subscription
