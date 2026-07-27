"""UI themes and three-state accent colours."""

from dataclasses import dataclass

from deskmate.core.enums import AnimationId, DeskStatus


@dataclass(frozen=True, slots=True)
class Theme:
    """Colours shared by both DeskMate windows."""

    background: str
    surface: str
    text: str
    muted: str
    character: str
    accent_ok: str
    accent_busy: str
    accent_muted: str
    surface_alt: str
    border: str
    track: str


DARK_THEME = Theme(
    "#111827", "#1F2937", "#F9FAFB", "#9CA3AF", "#5B8DEF",
    "#3FA96B", "#E8A33D", "#6B7280", "#273244", "#374151", "#111827",
)
LIGHT_THEME = Theme(
    "#F9FAFB", "#FFFFFF", "#111827", "#6B7280", "#5B8DEF",
    "#3FA96B", "#E8A33D", "#6B7280", "#F3F4F6", "#D1D5DB", "#E5E7EB",
)

STATUS_COLORS: dict[DeskStatus, str] = {
    DeskStatus.FOCUSED: "#5B8DEF",
    DeskStatus.IDLE: "#4FB3A9",
    DeskStatus.AWAY: "#6B7280",
}
ANIMATION_COLORS: dict[AnimationId, str] = {
    AnimationId.RUNNING: STATUS_COLORS[DeskStatus.FOCUSED],
    AnimationId.SITTING: STATUS_COLORS[DeskStatus.IDLE],
    AnimationId.SLEEPING: STATUS_COLORS[DeskStatus.AWAY],
    AnimationId.BREAK: "#E8A33D",
}


def status_color(status: DeskStatus) -> str:
    """Return a state accent."""

    return STATUS_COLORS[status]


def animation_color(animation: AnimationId) -> str:
    """Return an animation accent."""

    return ANIMATION_COLORS[animation]


def resolve_theme(name: str) -> Theme:
    """Return the selected theme."""

    return LIGHT_THEME if name == "light" else DARK_THEME
