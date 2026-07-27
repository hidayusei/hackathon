"""All Japanese user-facing strings and their formatters."""

from deskmate.core.enums import DeskStatus, SourceStatus, SystemStatus


STATUS_LABELS_JA: dict[DeskStatus, str] = {
    DeskStatus.FOCUSED: "集中",
    DeskStatus.IDLE: "非集中",
    DeskStatus.AWAY: "離席中",
}
SYSTEM_LABELS_JA: dict[SystemStatus, str] = {
    SystemStatus.STARTING: "起動中です",
    SystemStatus.RUNNING: "",
    SystemStatus.NO_SIGNAL: "入力が途切れています",
    SystemStatus.PAUSED: "推定を停止しています",
    SystemStatus.ERROR: "エラーが発生しています",
}
SOURCE_LABELS_JA: dict[SourceStatus, str] = {
    SourceStatus.IDLE: "待機中",
    SourceStatus.CONNECTING: "接続中",
    SourceStatus.STREAMING: "入力中",
    SourceStatus.STALLED: "入力待機中",
    SourceStatus.DISCONNECTED: "切断",
    SourceStatus.ERROR: "エラー",
    SourceStatus.CLOSED: "終了",
}

AWAY_NOTE_JA = "動きを検出していません（静止との区別はできません）"
BREAK_TITLE_JA = "そろそろ休憩しませんか"
BREAK_BODY_JA = "{duration} 集中しています"
BREAK_SNOOZE_JA = "あとで"
BREAK_TAKEN_JA = "休憩する"

PRIVACY_NOTICE_JA = "RGB映像は使用していません / データはこの端末の外に出ません"
PRIVACY_CAVEAT_JA = "イベントデータからも動きの形状が推測される可能性があります"
DETAIL_CAVEAT_JA = "この画面には机上の動きの情報が含まれます"
DETAIL_BUTTON_JA = "詳細"
PAUSE_BUTTON_JA = "停止"
RESUME_BUTTON_JA = "再開"
QUIT_BUTTON_JA = "終了"
UI_DEBUG_MENU_JA = "UIデバッグ"
UI_DEBUG_AUTO_JA = "自動判定に戻す"
UI_DEBUG_FOCUSED_JA = "集中を表示"
UI_DEBUG_IDLE_JA = "非集中を表示"
UI_DEBUG_AWAY_JA = "離席中を表示"
UI_DEBUG_BREAK_JA = "休憩促しを表示"
WINDOW_TITLE_JA = "DeskMate"
DETAIL_TITLE_JA = "DeskMate 詳細"
CONFIDENCE_JA = "信頼度"
DURATION_JA = "継続時間"
EVENTS_PANEL_JA = "イベント点群 / 時間窓"
MOTION_PANEL_JA = "動きの範囲・重心・変化量"
REGION_PANEL_JA = "領域別活動量"
FEATURE_PANEL_JA = "特徴量"
HISTORY_PANEL_JA = "状態履歴 / 活動量"
HISTORY_TOOLTIP_JA = "直近の状態の推移"
CURRENT_STATUS_JA = "現在の状態"
RULE_JA = "推定理由"
CANDIDATE_JA = "候補状態"
SOURCE_JA = "入力ソース"
PIPELINE_STATS_JA = "処理統計"
WINDOW_JA = "窓"
EVENT_COUNT_JA = "イベント数"
TRUNCATED_JA = "間引きあり"
SAVE_ENABLED_JA = "保存が有効です"
DEBUG_FIXED_JA = "デバッグ: 状態固定中"
HDF5_NOT_IMPLEMENTED_JA = "EXT-1: HDF5 入力は未実装です"

SCENARIO_LABELS_JA: dict[str, str] = {
    "keyboard_focus": "キーボード付近で一定した細かな動き",
    "mouse_intermittent": "マウス付近で断続的な動き",
    "desk_wide": "机上の広い範囲で活発な動き",
    "quiet": "一定時間動きがない",
    "dropout": "入力が途切れる",
}


def resolve_label(
    status: DeskStatus,
    system_status: SystemStatus = SystemStatus.RUNNING,
) -> str:
    """Return a system label or the confirmed three-state label."""

    if system_status is not SystemStatus.RUNNING:
        return SYSTEM_LABELS_JA[system_status]
    return STATUS_LABELS_JA[status]


def format_duration(seconds: float) -> str:
    """Format non-negative seconds using compact Japanese units."""

    total = max(0, int(seconds))
    if total < 60:
        return f"{total}秒"
    minutes, remaining = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}分{remaining}秒"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}時間{minutes:02d}分"


def input_mode_text(source_name: str, status: SourceStatus) -> str:
    """Return an unambiguous input-mode badge."""

    lowered = source_name.lower()
    if status in {SourceStatus.ERROR, SourceStatus.DISCONNECTED}:
        return "CAMERA ERROR" if "metavision" in lowered else "INPUT ERROR"
    if "metavision(live)" in lowered:
        return "LIVE"
    if "metavision(raw)" in lowered or "file" in lowered or "replay" in lowered:
        return "REPLAY"
    if "dummy" in lowered:
        return "DUMMY MODE"
    return "INPUT"
