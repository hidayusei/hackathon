"""Always-on-top resident DeskMate widget."""

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QContextMenuEvent, QFont, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from deskmate.character.renderer import create_renderer
from deskmate.config.schema import AppConfig
from deskmate.core.enums import SystemStatus
from deskmate.core.types import StatusSnapshot

from .bridge import UiBridge
from .character_view import CharacterView
from .labels import (
    CONFIDENCE_JA,
    DETAIL_BUTTON_JA,
    PAUSE_BUTTON_JA,
    PRIVACY_NOTICE_JA,
    QUIT_BUTTON_JA,
    RESUME_BUTTON_JA,
    SHARE_BUTTON_JA,
    WINDOW_TITLE_JA,
    format_duration,
    resolve_label,
)
from .status_stripe import StatusStripe
from .theme import resolve_theme, status_color

# Text-presentation glyphs only. Characters such as U+23F8 PAUSE or U+25B6 PLAY have
# emoji presentations that Segoe UI Emoji would render in full colour.
GLYPH_DETAIL = "⋯"   # ⋯ midline horizontal ellipsis
GLYPH_SHARE = "⧉"    # ⧉ two joined squares
GLYPH_PAUSE = "‖"    # ‖ double vertical line
GLYPH_RESUME = "►"   # ► black right-pointing pointer
_UI_FONT_FAMILY = "Segoe UI"


class WidgetWindow(QWidget):
    """Frameless, translucent, movable always-on-top status widget."""

    detail_requested = Signal()
    share_requested = Signal()
    quit_requested = Signal()

    def __init__(self, bridge: UiBridge, config: AppConfig) -> None:
        super().__init__()
        self.bridge = bridge
        self.config = config
        self._drag_origin: QPoint | None = None
        self._minimized = config.ui.widget.minimized
        self._paused = False
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

        self.detail_button.clicked.connect(self.detail_requested)
        self.share_button.clicked.connect(self.share_requested)
        self.pause_button.clicked.connect(self._toggle_pause)
        bridge.snapshot_updated.connect(self.apply_snapshot)
        self._apply_size()
        self.restore_position()

    # ---------------------------------------------------------------- construction
    def _build_widgets(self) -> None:
        theme = self._theme
        widget_config = self.config.ui.widget

        renderer = create_renderer(self.config.character, theme)
        self.character_view = CharacterView(
            renderer, widget_config.character_size, self, self.config.character.fps
        )

        self.title_label = QLabel(WINDOW_TITLE_JA)
        self.title_label.setObjectName("title")
        self.state_dot = QLabel("●")
        self.state_dot.setObjectName("dot")

        self.status_label = QLabel()
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        self.duration_label = QLabel()
        self.duration_label.setObjectName("duration")

        self.confidence_caption = QLabel(CONFIDENCE_JA)
        self.confidence_caption.setObjectName("caption")
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setObjectName("confidence")
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setTextVisible(False)
        self.confidence_bar.setFixedHeight(8)
        self.confidence_value = QLabel("--")
        self.confidence_value.setObjectName("caption")
        self.confidence_value.setFixedWidth(38)
        self.confidence_value.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.stripe = StatusStripe(theme, float(self.config.ui.detail.history_seconds), self)
        self.privacy_label = QLabel(PRIVACY_NOTICE_JA)
        self.privacy_label.setObjectName("privacy")
        self.share_state_label = QLabel()
        self.share_state_label.setObjectName("caption")

        self.detail_button = self._tool_button(GLYPH_DETAIL, DETAIL_BUTTON_JA)
        self.share_button = self._tool_button(GLYPH_SHARE, SHARE_BUTTON_JA)
        self.pause_button = self._tool_button(GLYPH_PAUSE, PAUSE_BUTTON_JA)

    def _tool_button(self, glyph: str, name: str) -> QPushButton:
        button = QPushButton(glyph)
        button.setObjectName("tool")
        button.setAccessibleName(name)
        button.setToolTip(name)
        button.setFixedSize(30, 26)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Force a UI font: several control glyphs also exist as emoji, and the emoji
        # font would render them full-colour and inconsistently sized.
        font = QFont(_UI_FONT_FAMILY)
        font.setPixelSize(13)
        button.setFont(font)
        return button

    def _build_layout(self) -> None:
        header = QHBoxLayout()
        header.setSpacing(6)
        header.addWidget(self.state_dot)
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.share_state_label)
        header.addWidget(self.detail_button)
        header.addWidget(self.share_button)
        header.addWidget(self.pause_button)

        confidence_row = QHBoxLayout()
        confidence_row.setSpacing(8)
        confidence_row.addWidget(self.confidence_caption)
        confidence_row.addWidget(self.confidence_bar, 1)
        confidence_row.addWidget(self.confidence_value)
        self.confidence_row = confidence_row

        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.addStretch(1)
        text_column.addWidget(self.status_label)
        text_column.addWidget(self.duration_label)
        text_column.addSpacing(10)
        text_column.addLayout(confidence_row)
        text_column.addStretch(1)

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(self.character_view, 0, Qt.AlignmentFlag.AlignVCenter)
        body.addLayout(text_column, 1)

        self.separator = QFrame()
        self.separator.setObjectName("separator")
        self.separator.setFrameShape(QFrame.Shape.HLine)
        self.separator.setFixedHeight(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)
        root.addLayout(header)
        root.addLayout(body, 1)
        root.addWidget(self.separator)
        root.addWidget(self.stripe)
        root.addWidget(self.privacy_label)
        self._root_layout = root

        # Minimized mode swaps to a bare character, so keep a flat list to toggle.
        self._chrome: tuple[QWidget, ...] = (
            self.title_label,
            self.state_dot,
            self.status_label,
            self.duration_label,
            self.confidence_caption,
            self.confidence_bar,
            self.confidence_value,
            self.detail_button,
            self.share_button,
            self.pause_button,
            self.privacy_label,
            self.share_state_label,
            self.separator,
            self.stripe,
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
            QLabel#title {{ color: {theme.muted}; font-size: 11px; font-weight: 600;
                            letter-spacing: 1px; }}
            QLabel#dot {{ color: {theme.character}; font-size: 13px; }}
            QLabel#status {{ font-size: 21px; font-weight: 700; }}
            QLabel#duration {{ color: {theme.muted}; font-size: 15px; }}
            QLabel#caption {{ color: {theme.muted}; font-size: 11px; }}
            QLabel#privacy {{ color: {theme.muted}; font-size: 10px; }}
            QFrame#separator {{ background: {theme.border}; border: none; }}
            QProgressBar#confidence {{
                background: {theme.track};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar#confidence::chunk {{
                background: {theme.character};
                border-radius: 4px;
            }}
            QPushButton#tool {{
                background: {theme.surface_alt};
                color: {theme.text};
                border: none;
                border-radius: 7px;
                font-size: 13px;
            }}
            QPushButton#tool:hover {{ background: {theme.character}; color: #FFFFFF; }}
            QPushButton#tool:pressed {{ background: {theme.border}; }}
            """
        )
        # Tabular figures keep the duration from shifting as digits change.
        duration_font = QFont(self.duration_label.font())
        duration_font.setStyleHint(QFont.StyleHint.Monospace)
        self.duration_label.setFont(duration_font)

    # ------------------------------------------------------------------- behaviour
    def _apply_size(self) -> None:
        widget_config = self.config.ui.widget
        if self._minimized:
            for widget in self._chrome:
                widget.hide()
            self._root_layout.setContentsMargins(6, 6, 6, 6)
            size = widget_config.minimized_size
            self.character_view.setFixedSize(size - 12, size - 12)
            self.setFixedSize(size, size)
            return
        for widget in self._chrome:
            widget.show()
        self.confidence_caption.setVisible(widget_config.show_confidence)
        self.confidence_bar.setVisible(widget_config.show_confidence)
        self.confidence_value.setVisible(widget_config.show_confidence)
        self.stripe.setVisible(widget_config.show_history)
        self.privacy_label.setVisible(widget_config.show_privacy_notice)
        self._root_layout.setContentsMargins(16, 12, 16, 12)
        self.character_view.setFixedSize(
            widget_config.character_size, widget_config.character_size
        )
        self.setFixedSize(widget_config.width, widget_config.height)

    def apply_snapshot(self, snapshot: StatusSnapshot) -> None:
        """Update all abstract status elements."""
        self.character_view.apply_snapshot(snapshot)
        self.status_label.setText(
            resolve_label(
                snapshot.status,
                snapshot.confidence,
                snapshot.duration_seconds,
                snapshot.system_status,
                short=True,
                floor=self.config.smoothing.display_confidence_floor,
            )
        )
        self.duration_label.setText(format_duration(snapshot.duration_seconds))
        percent = round(snapshot.confidence * 100)
        self.confidence_bar.setValue(percent)
        self.confidence_value.setText(f"{percent}%")
        accent = status_color(snapshot.status)
        self.state_dot.setStyleSheet(f"color:{accent};font-size:13px;")
        self.confidence_bar.setStyleSheet(
            f"QProgressBar#confidence{{background:{self._theme.track};border:none;"
            f"border-radius:4px;}}"
            f"QProgressBar#confidence::chunk{{background:{accent};border-radius:4px;}}"
        )
        self.stripe.apply_snapshot(snapshot)
        self.share_state_label.setText("" if self.bridge.sharing_enabled else "共有停止中")
        self._paused = snapshot.system_status is SystemStatus.PAUSED
        self.pause_button.setText(GLYPH_RESUME if self._paused else GLYPH_PAUSE)
        self.pause_button.setToolTip(
            RESUME_BUTTON_JA if self._paused else PAUSE_BUTTON_JA
        )

    def _toggle_pause(self) -> None:
        self.bridge.set_paused(not self._paused)

    def toggle_minimized(self) -> None:
        """Toggle character-only mode."""
        self._minimized = not self._minimized
        self.config.ui.widget.minimized = self._minimized
        self._apply_size()

    def restore_position(self) -> None:
        """Restore configured position or place at the available screen bottom-right."""
        position = self.config.ui.widget.last_position
        screen = self.screen() or self.windowHandle().screen() if self.windowHandle() else None
        geometry = screen.availableGeometry() if screen else None
        if position is not None and geometry and geometry.contains(QPoint(*position)):
            self.move(*position)
        elif geometry:
            self.move(
                geometry.right() - self.width() - 16,
                geometry.bottom() - self.height() - 16,
            )

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Toggle minimized mode."""
        self.toggle_minimized()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Begin dragging on left click."""
        if event.button() is Qt.MouseButton.LeftButton:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Move while dragging."""
        if self._drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Finish dragging and retain the position in runtime configuration."""
        if event.button() is Qt.MouseButton.LeftButton:
            self._drag_origin = None
            self.config.ui.widget.last_position = (self.x(), self.y())
            event.accept()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Show compact widget actions."""
        menu = QMenu(self)
        detail = QAction(DETAIL_BUTTON_JA, menu)
        share = QAction(SHARE_BUTTON_JA, menu)
        pause = QAction(RESUME_BUTTON_JA if self._paused else PAUSE_BUTTON_JA, menu)
        quit_action = QAction(QUIT_BUTTON_JA, menu)
        detail.triggered.connect(self.detail_requested)
        share.triggered.connect(self.share_requested)
        pause.triggered.connect(self._toggle_pause)
        quit_action.triggered.connect(self.quit_requested)
        menu.addActions([detail, share, pause, quit_action])
        menu.exec(event.globalPos())

    def closeEvent(self, event: QCloseEvent) -> None:
        """Hide instead of terminating the tray-style application."""
        self.hide()
        event.ignore()
