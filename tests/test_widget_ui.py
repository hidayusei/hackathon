"""Main-window presentation tests."""

from datetime import datetime

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from conftest import FakeClock
from deskmate.config.loader import load_config
from deskmate.core.enums import AnimationId, DeskStatus, SourceStatus, SystemStatus
from deskmate.core.types import StatusSnapshot
from deskmate.pipeline.runner import PipelineRunner
from deskmate.ui.bridge import UiBridge
from deskmate.ui.theme import STATUS_COLORS, animation_color, status_color
from deskmate.ui.widget_window import WidgetWindow


def _snapshot(
    status: DeskStatus,
    duration: float = 10.0,
    system: SystemStatus = SystemStatus.RUNNING,
    break_due: bool = False,
):
    animation = AnimationId.BREAK if break_due else {
        DeskStatus.FOCUSED: AnimationId.RUNNING,
        DeskStatus.IDLE: AnimationId.SITTING,
        DeskStatus.AWAY: AnimationId.SLEEPING,
    }[status]
    return StatusSnapshot(
        status,
        system,
        status.value,
        animation,
        duration,
        0.8,
        duration,
        break_due,
        False,
        datetime.now().astimezone(),
    )


def _widget():
    config = load_config({"input": {"source": "dummy"}})
    bridge = UiBridge(PipelineRunner(config, FakeClock()), config)
    return config, WidgetWindow(bridge, config)


def test_widget_uses_configured_size(qt_app) -> None:
    config, widget = _widget()
    assert widget.size().width() == config.ui.widget.width
    assert widget.size().height() == config.ui.widget.height


def test_minimized_mode_shrinks_to_square(qt_app) -> None:
    config, widget = _widget()
    before = widget.character_view.size()
    widget.toggle_minimized()
    character_size = 30 * config.character.scale
    assert widget.character_view.size() == before
    assert widget.character_view.width() == character_size
    assert widget.character_view.height() == character_size
    assert widget.width() == character_size + 12
    assert widget.height() == character_size + 12
    assert widget.status_label.isHidden()


def test_main_window_moves_when_character_is_dragged(qtbot) -> None:
    _, widget = _widget()
    widget.show()
    widget.move(40, 40)
    qtbot.wait(10)

    start = widget.pos()
    center = widget.character_view.rect().center()
    QTest.mousePress(widget.character_view, Qt.MouseButton.LeftButton, pos=center)
    QTest.mouseMove(widget.character_view, center + QPoint(30, 20))
    QTest.mouseRelease(
        widget.character_view,
        Qt.MouseButton.LeftButton,
        pos=center + QPoint(30, 20),
    )

    assert widget.pos() == start + QPoint(30, 20)
    widget.close()


def test_widget_has_no_bottom_history_bar(qt_app) -> None:
    _, widget = _widget()
    assert not hasattr(widget, "stripe")
    assert not hasattr(widget, "separator")


def test_widget_shows_duration_without_confidence_bar(qt_app) -> None:
    _, widget = _widget()
    widget.apply_snapshot(_snapshot(DeskStatus.FOCUSED, duration=312))
    assert widget.duration_label.text() == "5分12秒"
    assert not hasattr(widget, "confidence_bar")


def test_input_mode_is_shown_in_context_menu(qt_app) -> None:
    _, widget = _widget()
    widget.apply_source(SourceStatus.STREAMING.value, "metavision(live)")
    assert widget._build_context_menu().actions()[0].text() == "LIVE"
    widget.apply_source(SourceStatus.STREAMING.value, "dummy(demo)")
    assert widget._build_context_menu().actions()[0].text() == "DUMMY MODE"
    widget.apply_source(SourceStatus.ERROR.value, "metavision(live)")
    assert widget._build_context_menu().actions()[0].text() == "CAMERA ERROR"


def test_header_has_no_mode_detail_or_pause_controls(qt_app) -> None:
    _, widget = _widget()
    assert not hasattr(widget, "source_badge")
    assert not hasattr(widget, "detail_button")
    assert not hasattr(widget, "pause_button")


def test_ui_debug_menu_previews_each_state_and_break(qt_app) -> None:
    _, widget = _widget()
    widget.apply_snapshot(_snapshot(DeskStatus.IDLE))
    menu = widget._build_context_menu()
    debug_action = next(
        action for action in menu.actions() if action.text() == "UIデバッグ"
    )
    debug_menu = debug_action.menu()
    assert debug_menu is not None

    expected = {
        "集中を表示": ("集中", AnimationId.RUNNING, False),
        "非集中を表示": ("非集中", AnimationId.SITTING, False),
        "離席中を表示": ("離席中", AnimationId.SLEEPING, False),
        "休憩促しを表示": ("集中", AnimationId.BREAK, True),
    }
    for action in debug_menu.actions():
        if action.text() not in expected:
            continue
        action.trigger()
        label, animation, break_due = expected[action.text()]
        assert widget.status_label.text() == label
        assert widget.character_view._renderer._animation is animation
        assert widget.break_banner.isHidden() == (not break_due)


def test_ui_debug_preview_holds_until_automatic_mode(qt_app) -> None:
    _, widget = _widget()
    widget.apply_snapshot(_snapshot(DeskStatus.IDLE))
    widget._set_debug_preview(DeskStatus.AWAY, False)
    widget.apply_snapshot(_snapshot(DeskStatus.FOCUSED))
    assert widget.status_label.text() == "離席中"

    widget._clear_debug_preview()
    assert widget.status_label.text() == "focused"


def test_number_keys_select_ui_debug_previews(qtbot) -> None:
    _, widget = _widget()
    widget.apply_snapshot(_snapshot(DeskStatus.IDLE))
    widget.show()
    widget.activateWindow()
    widget.setFocus()
    qtbot.wait(10)

    expected = {
        Qt.Key.Key_1: (DeskStatus.FOCUSED, AnimationId.RUNNING, False),
        Qt.Key.Key_2: (DeskStatus.IDLE, AnimationId.SITTING, False),
        Qt.Key.Key_3: (DeskStatus.AWAY, AnimationId.SLEEPING, False),
        Qt.Key.Key_4: (DeskStatus.FOCUSED, AnimationId.BREAK, True),
    }
    for key, (status, animation, break_due) in expected.items():
        qtbot.keyClick(widget, key)
        assert widget._debug_status is status
        assert widget.character_view._renderer._animation is animation
        assert widget.break_banner.isHidden() == (not break_due)

    widget.close()


def test_break_prompt_changes_character_and_shows_banner(qt_app) -> None:
    _, widget = _widget()
    snapshot = _snapshot(DeskStatus.FOCUSED, duration=1500, break_due=True)
    widget.apply_snapshot(snapshot)
    assert snapshot.status is DeskStatus.FOCUSED
    assert snapshot.animation is AnimationId.BREAK
    assert not widget.break_banner.isHidden()


def test_main_window_has_no_away_caveat(qt_app) -> None:
    """The main window stays clean: the sensor-limitation note is not shown here."""
    _, widget = _widget()
    widget.apply_snapshot(_snapshot(DeskStatus.AWAY))
    assert not hasattr(widget, "note_label")
    from deskmate.ui.labels import AWAY_NOTE_JA

    labels = widget.findChildren(type(widget.status_label))
    assert all(label.text() != AWAY_NOTE_JA for label in labels)


def test_detail_status_header_shows_away_caveat_only_for_away(qt_app) -> None:
    """The sensor-limitation note lives on the detail screen and only for away."""
    from types import SimpleNamespace

    from deskmate.character.renderer import create_renderer
    from deskmate.core.enums import SystemStatus
    from deskmate.core.types import StatusEstimate
    from deskmate.ui.character_view import CharacterView
    from deskmate.ui.detail_window import StatusHeader
    from deskmate.ui.labels import AWAY_NOTE_JA
    from deskmate.ui.theme import resolve_theme

    config = load_config()
    header = StatusHeader(
        CharacterView(
            create_renderer(config.character, resolve_theme(config.ui.theme)), 60
        )
    )

    def frame(status: DeskStatus) -> SimpleNamespace:
        return SimpleNamespace(
            snapshot=_snapshot(status),
            estimate=StatusEstimate(status, 0.8, "R", "reason"),
        )

    header.update_frame(frame(DeskStatus.AWAY))
    assert header.note.text() == AWAY_NOTE_JA
    header.update_frame(frame(DeskStatus.FOCUSED))
    assert header.note.text() == ""


def test_all_states_and_animations_have_colours() -> None:
    assert set(STATUS_COLORS) == set(DeskStatus)
    assert len(set(STATUS_COLORS.values())) == len(DeskStatus)
    assert all(status_color(status).startswith("#") for status in DeskStatus)
    assert all(animation_color(animation).startswith("#") for animation in AnimationId)
