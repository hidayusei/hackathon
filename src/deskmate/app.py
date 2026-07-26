"""Application lifecycle composition."""

from PySide6.QtCore import QMetaObject, QThread, Qt
from PySide6.QtWidgets import QApplication

from deskmate.config.schema import AppConfig
from deskmate.pipeline.runner import PipelineRunner
from deskmate.ui.bridge import UiBridge
from deskmate.ui.widget_window import WidgetWindow
from deskmate.ui.share_window import ShareWindow
from deskmate.ui.detail_window import DetailWindow
from deskmate.ui.tray import TrayIcon


class DeskMateApp:
    """Create the Qt application and worker pipeline."""

    def __init__(self, config: AppConfig, headless: bool = False) -> None:
        self.qt_app = QApplication.instance() or QApplication([])
        self.runner = PipelineRunner(config)
        self.bridge = UiBridge(self.runner, config)
        self.widget = None if headless else WidgetWindow(self.bridge, config)
        self.share_window = None if headless else ShareWindow(self.bridge, config)
        self.detail_window = None
        self._headless = headless
        self.tray = None
        self.thread = QThread()
        self.runner.moveToThread(self.thread)
        self.thread.started.connect(self.runner.start)

    def run(self) -> int:
        """Start the worker and enter the Qt event loop."""
        if self.widget is not None:
            self.widget.quit_requested.connect(self.qt_app.quit)
            self.widget.share_requested.connect(self.share_window.show)
            self.widget.detail_requested.connect(self._show_detail)
            self.widget.show()
            self.tray = TrayIcon(
                self.bridge,
                self.widget,
                self._show_detail,
                self.share_window.show,
                self.qt_app.quit,
            )
            self.tray.show()
            if self.runner.config.app.show_share_window:
                self.share_window.show()
        self.thread.start()
        return self.qt_app.exec()

    def _show_detail(self) -> None:
        if self._headless:
            return
        if self.detail_window is None:
            self.detail_window = DetailWindow(self.bridge, self.runner.config)
            self.detail_window.destroyed.connect(self._detail_destroyed)
        self.detail_window.show()
        self.detail_window.raise_()

    def _detail_destroyed(self, *_args: object) -> None:
        self.detail_window = None

    def shutdown(self) -> None:
        """Stop worker and thread."""
        if self.thread.isRunning():
            QMetaObject.invokeMethod(
                self.runner,
                "stop",
                Qt.ConnectionType.BlockingQueuedConnection,
            )
        else:
            self.runner.stop()
        self.thread.quit()
        self.thread.wait(3000)
