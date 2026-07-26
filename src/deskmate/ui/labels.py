"""All Japanese user-facing strings and their formatters."""

from deskmate.core.enums import Approachability, DeskStatus, SourceStatus, SystemStatus


STATUS_LABELS_JA: dict[DeskStatus, str] = {
    DeskStatus.FOCUSED: "集中傾向",
    DeskStatus.WORKING: "作業中",
    DeskStatus.ORGANIZING: "机上整理中",
    DeskStatus.SHORT_BREAK: "小休止",
    DeskStatus.TRANSITION: "状態が変化中",
    DeskStatus.NO_MOTION: "一定時間、動きを検出していません",
    DeskStatus.UNKNOWN: "状態不明",
}
STATUS_LABELS_SHORT_JA: dict[DeskStatus, str] = {
    DeskStatus.FOCUSED: "集中傾向",
    DeskStatus.WORKING: "作業中",
    DeskStatus.ORGANIZING: "机上整理中",
    DeskStatus.SHORT_BREAK: "小休止",
    DeskStatus.TRANSITION: "変化中",
    DeskStatus.NO_MOTION: "動きを検出していません",
    DeskStatus.UNKNOWN: "状態不明",
}
QUIET_VARIANTS_JA = [
    "一定時間、動きを検出していません",
    "静かな状態が続いています",
]
APPROACHABILITY_LABELS_JA: dict[Approachability, str] = {
    Approachability.LIKELY_OK: "話しかけやすそう",
    Approachability.PREFER_LATER: "集中しているようです",
    Approachability.UNDETERMINED: "判断できません",
}
SYSTEM_LABELS_JA: dict[SystemStatus, str] = {
    SystemStatus.STARTING: "起動中です（推定準備中）",
    SystemStatus.RUNNING: "",
    SystemStatus.NO_SIGNAL: "入力が途切れています",
    SystemStatus.PAUSED: "推定を停止しています",
    SystemStatus.SHARING_OFF: "",
    SystemStatus.ERROR: "エラーが発生しています",
}
SHARE_SYSTEM_LABELS_JA: dict[SystemStatus, str] = {
    SystemStatus.STARTING: "準備中です",
    SystemStatus.RUNNING: "",
    SystemStatus.NO_SIGNAL: "現在の状態を判定できません",
    SystemStatus.PAUSED: "共有を停止しています",
    SystemStatus.SHARING_OFF: "共有を停止しています",
    SystemStatus.ERROR: "現在の状態を判定できません",
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
PRIVACY_NOTICE_JA = "RGB映像は使用していません / 生データは外部送信していません"
PRIVACY_CAVEAT_JA = "イベントデータからも動きの形状が推測される可能性があります"
DETAIL_CAVEAT_JA = "この画面には机上の動きの情報が含まれます"
SHARING_STOPPED_JA = "共有を停止しています"
DETAIL_BUTTON_JA = "詳細"
SHARE_BUTTON_JA = "共有"
PAUSE_BUTTON_JA = "停止"
RESUME_BUTTON_JA = "再開"
QUIT_BUTTON_JA = "終了"
WINDOW_TITLE_JA = "DeskMate"
DETAIL_TITLE_JA = "DeskMate 詳細"
SHARE_TITLE_JA = "DeskMate 共有"
LAST_UPDATED_JA = "最終更新"
CONFIDENCE_JA = "信頼度"
DURATION_JA = "継続時間"
APPROACHABILITY_JA = "話しかけやすさの目安"
EVENTS_PANEL_JA = "イベント点群 / 時間窓"
MOTION_PANEL_JA = "動きの範囲・重心・変化量"
REGION_PANEL_JA = "領域別活動量"
FEATURE_PANEL_JA = "特徴量"
HISTORY_PANEL_JA = "状態履歴 / 活動量"
CURRENT_STATUS_JA = "現在の状態"
RULE_JA = "適用ルール"
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
    "keyboard_steady": "キーボード付近で一定した細かな動き",
    "mouse_intermittent": "マウス付近で断続的な動き",
    "desk_wide_active": "机上の広い範囲で活発な動き",
    "activity_decay": "活動量が徐々に減少",
    "quiet": "一定時間動きがない",
    "rapid_change": "状態が短時間で変化する",
    "noise_burst": "ノイズが大量に発生する",
    "dropout": "入力が途切れる",
}


def resolve_label(
    status: DeskStatus,
    confidence: float,
    duration_seconds: float = 0.0,
    system_status: SystemStatus = SystemStatus.RUNNING,
    short: bool = False,
    floor: float = 0.45,
) -> str:
    """Resolve the canonical, uncertainty-aware display label."""
    if system_status not in {SystemStatus.RUNNING, SystemStatus.SHARING_OFF}:
        return SYSTEM_LABELS_JA[system_status]
    if status is DeskStatus.NO_MOTION:
        if duration_seconds >= 120:
            return QUIET_VARIANTS_JA[1]
        return STATUS_LABELS_SHORT_JA[status] if short else QUIET_VARIANTS_JA[0]
    if confidence < floor:
        return STATUS_LABELS_JA[DeskStatus.UNKNOWN]
    labels = STATUS_LABELS_SHORT_JA if short else STATUS_LABELS_JA
    return labels[status]


def resolve_share_label(
    status: DeskStatus,
    confidence: float,
    duration_seconds: float,
    system_status: SystemStatus,
    floor: float = 0.45,
) -> str:
    """Resolve a label using the stricter shared-system wording."""
    if system_status is not SystemStatus.RUNNING:
        return SHARE_SYSTEM_LABELS_JA[system_status]
    return resolve_label(status, confidence, duration_seconds, floor=floor)


def format_duration(seconds: float) -> str:
    """Format non-negative seconds using the canonical compact forms."""
    total = max(0, int(seconds))
    if total < 60:
        return f"{total}秒"
    minutes, remaining = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}分{remaining}秒"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}時間{minutes:02d}分"
