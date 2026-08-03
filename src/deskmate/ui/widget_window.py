"""Always-on-top main and shared DeskMate window."""

from dataclasses import replace
from datetime import datetime
from functools import partial
from time import monotonic

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QContextMenuEvent,
    QFont,
    QKeySequence,
    QMouseEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from deskmate.character.mapping import resolve_animation
from deskmate.character.renderer import create_renderer
from deskmate.config.schema import AppConfig
from deskmate.core.enums import DeskStatus, SourceStatus, SystemStatus
from deskmate.core.types import StatusSnapshot

from .break_banner import BreakBanner
from .bridge import UiBridge
from .character_view import CharacterView
from .labels import (
    DETAIL_BUTTON_JA,
    PAUSE_BUTTON_JA,
    QUIT_BUTTON_JA,
    RESUME_BUTTON_JA,
    UI_DEBUG_AUTO_JA,
    UI_DEBUG_AWAY_JA,
    UI_DEBUG_BREAK_JA,
    UI_DEBUG_BREAK_STATUS_JA,
    UI_DEBUG_FOCUSED_JA,
    UI_DEBUG_IDLE_JA,
    UI_DEBUG_MENU_JA,
    WINDOW_TITLE_JA,
    format_duration,
    input_mode_text,
    resolve_label,
)
from .theme import resolve_theme, status_color


class WidgetWindow(QWidget):
    """Frameless main window suitable for the Pi display and screen sharing."""

    detail_requested = Signal()
    quit_requested = Signal()

    def __init__(self, bridge: UiBridge, config: AppConfig) -> None:
        super().__init__()
        self.bridge = bridge
        self.config = config
        self._drag_origin: QPoint | None = None
        self._system_move_active = False
        self._minimized = config.ui.widget.minimized
        self._paused = False
        self._last_live_snapshot: StatusSnapshot | None = None
        self._debug_status: DeskStatus | None = None
        self._debug_break = False
        self._debug_started_monotonic: float | None = None
        self._source_text = "INPUT"
        self._theme = resolve_theme(config.ui.theme)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(config.ui.widget.opacity)
        self._build_widgets()
        self._build_layout()
        self._apply_style()
        bridge.snapshot_updated.connect(self.apply_snapshot)
        bridge.source_updated.connect(self.apply_source)
        self._apply_size()
        self.restore_position()

    def _build_widgets(self) -> None:
        renderer = create_renderer(self.config.character, self._theme)
        size = 30 * self.config.character.scale
        self.character_view = CharacterView(renderer, size, self)
        self.title_label = QLabel(WINDOW_TITLE_JA)
        self.title_label.setObjectName("title")
        self.state_dot = QLabel("●")
        self.state_dot.setObjectName("dot")
        self.status_label = QLabel()
        self.status_label.setObjectName("status")
        self.duration_label = QLabel()
        self.duration_label.setObjectName("duration")
        self.break_banner = BreakBanner(self.bridge, self)
        for draggable in (
            self.character_view,
            self.title_label,
            self.state_dot,
            self.status_label,
            self.duration_label,
        ):
            draggable.installEventFilter(self)
        previews = (
            (Qt.Key.Key_1, DeskStatus.FOCUSED, False),
            (Qt.Key.Key_2, DeskStatus.IDLE, False),
            (Qt.Key.Key_3, DeskStatus.AWAY, False),
            (Qt.Key.Key_4, DeskStatus.FOCUSED, True),
        )
        self._debug_shortcuts: list[QShortcut] = []
        for key, status, break_due in previews:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(
                partial(self._set_debug_preview, status, break_due)
            )
            self._debug_shortcuts.append(shortcut)

    def _build_layout(self) -> None:
        header = QHBoxLayout()
        header.setSpacing(6)
        header.addWidget(self.state_dot)
        header.addWidget(self.title_label)
        header.addStretch(1)

        text = QVBoxLayout()
        text.addStretch(1)
        text.addWidget(self.status_label)
        text.addWidget(self.duration_label)
        text.addStretch(1)

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(self.character_view, 0, Qt.AlignmentFlag.AlignVCenter)
        body.addLayout(text, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)
        root.addLayout(header)
        root.addLayout(body, 1)
        root.addWidget(self.break_banner)
        self._root_layout = root
        self._chrome: tuple[QWidget, ...] = (
            self.title_label,
            self.state_dot,
            self.status_label,
            self.duration_label,
            self.break_banner,
        )

    def _apply_style(self) -> None:
        theme = self._theme
        self.setStyleSheet(
            f"""
            WidgetWindow {{
                background: {theme.surface};
                border: 1px solid {theme.border};
                border-radius: 16px;
            }}
            QLabel {{ color: {theme.text}; background: transparent; }}
            QLabel#title {{ color: {theme.muted}; font-size: 11px; font-weight: 600; }}
            QLabel#dot {{ color: {theme.character}; font-size: 13px; }}
            QLabel#status {{ font-size: 24px; font-weight: 700; }}
            QLabel#duration {{ color: {theme.muted}; font-size: 16px; }}
            QWidget#breakBanner {{
                background: #4A3520; border: 1px solid #E8A33D; border-radius: 8px;
            }}
            QLabel#breakTitle {{ color: #FFD18A; font-weight: 700; }}
            """
        )
        font = QFont(self.duration_label.font())
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.duration_label.setFont(font)

    def _apply_size(self) -> None:
        widget = self.config.ui.widget
        if self._minimized:
            for item in self._chrome:
                item.hide()
            self._root_layout.setContentsMargins(6, 6, 6, 6)
            character_size = 30 * self.config.character.scale
            self.character_view.setFixedSize(character_size, character_size)
            self.setFixedSize(character_size + 12, character_size + 12)
            return
        for item in self._chrome:
            item.show()
        self.break_banner.hide()
        self._root_layout.setContentsMargins(16, 12, 16, 12)
        size = 30 * self.config.character.scale
        self.character_view.setFixedSize(size, size)
        self.setFixedSize(widget.width, widget.height)

    def apply_snapshot(self, snapshot: StatusSnapshot) -> None:
        """Apply status, duration, character, and break-prompt updates."""

        self._last_live_snapshot = snapshot
        if self._debug_status is not None:
            snapshot = self._debug_snapshot(snapshot)
            self.bridge.set_debug_preview(snapshot)
        self._render_snapshot(snapshot)

    def _render_snapshot(self, snapshot: StatusSnapshot) -> None:
        """Render one live or UI-debug snapshot."""

        self.character_view.apply_snapshot(snapshot)
        self.status_label.setText(snapshot.label)
        self.duration_label.setText(format_duration(snapshot.duration_seconds))
        accent = status_color(snapshot.status)
        self.state_dot.setStyleSheet(f"color:{accent};font-size:13px;")
        self.break_banner.apply(
            not self._minimized and snapshot.break_due,
            snapshot.focus_streak_seconds,
        )
        if not self._minimized:
            extra = 100 if snapshot.break_due else 0
            self.setFixedHeight(self.config.ui.widget.height + extra)
        self._paused = snapshot.system_status is SystemStatus.PAUSED

    def apply_source(self, status_value: str, source_name: str) -> None:
        """Cache the input mode for the context menu."""

        status = SourceStatus(status_value)
        self._source_text = input_mode_text(source_name, status)

    def _toggle_pause(self) -> None:
        self.bridge.set_paused(not self._paused)

    def toggle_minimized(self) -> None:
        """Toggle character-only mode."""

        self._minimized = not self._minimized
        self.config.ui.widget.minimized = self._minimized
        self._apply_size()

    def restore_position(self) -> None:
        """Restore a visible position or use the lower-right corner."""

        position = self.config.ui.widget.last_position
        screen = self.screen() or (
            self.windowHandle().screen() if self.windowHandle() else None
        )
        geometry = screen.availableGeometry() if screen else None
        if position is not None and geometry and geometry.contains(QPoint(*position)):
            self.move(*position)
        elif geometry:
            self.move(
                geometry.right() - self.width() - 16,
                geometry.bottom() - self.height() - 16,
            )

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.toggle_minimized()
        event.accept()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Forward drags from display children to the frameless main window."""

        if isinstance(event, QMouseEvent):
            if event.type() is QEvent.Type.MouseButtonPress:
                self.mousePressEvent(event)
                return event.isAccepted()
            if event.type() is QEvent.Type.MouseMove:
                self.mouseMoveEvent(event)
                return event.isAccepted()
            if event.type() is QEvent.Type.MouseButtonRelease:
                self.mouseReleaseEvent(event)
                return event.isAccepted()
            if event.type() is QEvent.Type.MouseButtonDblClick:
                self.mouseDoubleClickEvent(event)
                return event.isAccepted()
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            handle = self.windowHandle()
            if handle is not None and handle.startSystemMove():
                self._system_move_active = True
                self._drag_origin = None
                event.accept()
                return
            self._system_move_active = False
            self._drag_origin = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_origin is not None and (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self._drag_origin)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            self._system_move_active = False
            self._drag_origin = None
            self.config.ui.widget.last_position = (self.x(), self.y())
            event.accept()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = self._build_context_menu()
        menu.exec(event.globalPos())

    def _build_context_menu(self) -> QMenu:
        """Build the right-click menu, including presentation-only UI previews."""

        menu = QMenu(self)
        source = QAction(self._source_text, menu)
        source.setEnabled(False)
        detail = QAction(DETAIL_BUTTON_JA, menu)
        pause = QAction(
            RESUME_BUTTON_JA if self._paused else PAUSE_BUTTON_JA, menu
        )
        quit_action = QAction(QUIT_BUTTON_JA, menu)
        detail.triggered.connect(self.detail_requested)
        pause.triggered.connect(self._toggle_pause)
        quit_action.triggered.connect(self.quit_requested)
        menu.addAction(source)
        menu.addSeparator()
        menu.addAction(detail)
        menu.addAction(pause)

        debug_menu = menu.addMenu(UI_DEBUG_MENU_JA)
        preview_actions = (
            (UI_DEBUG_FOCUSED_JA, DeskStatus.FOCUSED, False),
            (UI_DEBUG_IDLE_JA, DeskStatus.IDLE, False),
            (UI_DEBUG_AWAY_JA, DeskStatus.AWAY, False),
            (UI_DEBUG_BREAK_JA, DeskStatus.FOCUSED, True),
        )
        for label, status, break_due in preview_actions:
            action = debug_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(
                self._debug_status is status and self._debug_break is break_due
            )
            action.triggered.connect(partial(self._set_debug_preview, status, break_due))
        debug_menu.addSeparator()
        automatic = debug_menu.addAction(UI_DEBUG_AUTO_JA)
        automatic.setCheckable(True)
        automatic.setChecked(self._debug_status is None)
        automatic.triggered.connect(self._clear_debug_preview)

        menu.addSeparator()
        menu.addAction(quit_action)
        return menu

    def _set_debug_preview(
        self,
        status: DeskStatus,
        break_due: bool,
        _checked: bool = False,
    ) -> None:
        """Hold a selected state on screen without changing inference state."""

        self._debug_status = status
        self._debug_break = break_due
        self._debug_started_monotonic = monotonic()
        base = self._last_live_snapshot or self._initial_snapshot()
        snapshot = self._debug_snapshot(base)
        self._render_snapshot(snapshot)
        self.bridge.set_debug_preview(snapshot)

    def _clear_debug_preview(self, _checked: bool = False) -> None:
        """Return the main window to the latest live pipeline result."""

        self._debug_status = None
        self._debug_break = False
        self._debug_started_monotonic = None
        self.bridge.set_debug_preview(None)
        if self._last_live_snapshot is not None:
            self._render_snapshot(self._last_live_snapshot)

    def _debug_snapshot(self, base: StatusSnapshot) -> StatusSnapshot:
        """Create a UI-only snapshot for deterministic visual inspection."""

        status = self._debug_status or base.status
        duration_seconds = 0.0
        if self._debug_started_monotonic is not None:
            duration_seconds = max(
                0.0,
                monotonic() - self._debug_started_monotonic,
            )
        if self._debug_break:
            duration_seconds += self.config.debug.break_start_seconds
        return replace(
            base,
            status=status,
            system_status=SystemStatus.RUNNING,
            label=(
                UI_DEBUG_BREAK_STATUS_JA
                if self._debug_break
                else resolve_label(status)
            ),
            animation=resolve_animation(status, self._debug_break, SystemStatus.RUNNING),
            duration_seconds=duration_seconds,
            confidence=1.0,
            focus_streak_seconds=duration_seconds,
            break_due=self._debug_break,
            changed=True,
        )

    def _initial_snapshot(self) -> StatusSnapshot:
        """Return a safe base before the first pipeline result arrives."""

        status = DeskStatus.IDLE
        return StatusSnapshot(
            status,
            SystemStatus.RUNNING,
            resolve_label(status),
            resolve_animation(status, False, SystemStatus.RUNNING),
            0.0,
            1.0,
            0.0,
            False,
            True,
            datetime.now().astimezone(),
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        """Hide the window while the tray process remains active."""

        self.hide()
        event.ignore()
