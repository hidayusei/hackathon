"""The sole UI-side bridge to PipelineRunner."""

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt, Signal

from deskmate.config.schema import AppConfig
from deskmate.core.enums import DeskStatus
from deskmate.core.types import StatusSnapshot
from deskmate.pipeline.runner import PipelineRunner


class UiBridge(QObject):
    """Cache and redistribute immutable pipeline results and controls."""

    snapshot_updated = Signal(object)
    status_changed = Signal(object)
    detail_updated = Signal(object)
    stats_updated = Signal(object)
    notice_changed = Signal(str)
    source_updated = Signal(str, str)

    def __init__(self, runner: PipelineRunner, config: AppConfig) -> None:
        super().__init__()
        self._runner = runner
        self._config = config
        self._last_snapshot: StatusSnapshot | None = None
        runner.snapshot_ready.connect(self._on_snapshot)
        runner.status_changed.connect(self.status_changed)
        runner.detail_ready.connect(self.detail_updated)
        runner.stats_updated.connect(self.stats_updated)
        runner.source_state.connect(self.source_updated)
        runner.error_occurred.connect(self._on_error)

    def _on_snapshot(self, snapshot: StatusSnapshot) -> None:
        self._last_snapshot = snapshot
        self.snapshot_updated.emit(snapshot)

    def _invoke(self, slot: str, *args: object) -> None:
        """Queue a runner slot call onto the pipeline thread.

        The UI must never touch runner state directly: the worker thread may be inside
        EventSource.read() at the time, and mutating the source from here would race.
        """
        QMetaObject.invokeMethod(
            self._runner,
            slot,
            Qt.ConnectionType.QueuedConnection,
            *[Q_ARG(type(value), value) for value in args],
        )

    def set_paused(self, paused: bool) -> None:
        """Request pipeline pause or resume."""
        self._invoke("set_paused", paused)

    def _on_error(self, kind: str, message: str) -> None:
        self.notice_changed.emit(f"{kind}: {message}")

    def open_detail(self) -> None:
        """Enable private detail subscription."""
        self._invoke("set_detail_subscription", True)

    def close_detail(self) -> None:
        """Disable private detail subscription."""
        self._invoke("set_detail_subscription", False)

    def set_scenario(self, scenario_id: str) -> None:
        """Change dummy scenario."""
        self._invoke("set_scenario", scenario_id)

    def force_status(self, status: DeskStatus | None) -> None:
        """Change debug-only forced status."""
        self._invoke("force_status", status.value if status else "")

    def request_reconnect(self) -> None:
        """Ask the pipeline to reopen its input source."""
        self._invoke("request_reconnect")

    def snooze_break(self) -> None:
        """Snooze the current break prompt."""

        self._invoke("snooze_break")

    def acknowledge_break(self) -> None:
        """Acknowledge a break and reset the focus streak."""

        self._invoke("acknowledge_break")

    @property
    def last_snapshot(self) -> StatusSnapshot | None:
        """Return the last immutable snapshot."""
        return self._last_snapshot
