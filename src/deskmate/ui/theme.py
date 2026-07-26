"""UI color themes and per-state accent colors."""

from dataclasses import dataclass

from deskmate.core.enums import AnimationId, DeskStatus


@dataclass(frozen=True, slots=True)
class Theme:
    """Colors shared by DeskMate windows and renderers."""

    background: str
    surface: str
    text: str
    muted: str
    character: str
    accent_ok: str
    accent_busy: str
    accent_muted: str
    surface_alt: str = "#374151"
    border: str = "#374151"
    track: str = "#111827"


DARK_THEME = Theme(
    "#111827", "#1F2937", "#F9FAFB", "#9CA3AF", "#5B8DEF",
    "#3FA96B", "#C97B2B", "#6B7280",
    surface_alt="#273244", border="#374151", track="#111827",
)
LIGHT_THEME = Theme(
    "#F9FAFB", "#FFFFFF", "#111827", "#6B7280", "#5B8DEF",
    "#3FA96B", "#C97B2B", "#6B7280",
    surface_alt="#F3F4F6", border="#D1D5DB", track="#E5E7EB",
)

# One accent per abstract state. Shared by both themes so that the state a viewer
# learns to recognise by colour never changes meaning. Defined here rather than in
# each widget so the widget, share window and history stripe always agree.
STATUS_COLORS: dict[DeskStatus, str] = {
    DeskStatus.FOCUSED: "#5B8DEF",
    DeskStatus.WORKING: "#4FB3A9",
    DeskStatus.ORGANIZING: "#C97B2B",
    DeskStatus.SHORT_BREAK: "#3FA96B",
    DeskStatus.TRANSITION: "#A78BFA",
    DeskStatus.NO_MOTION: "#6B7280",
    DeskStatus.UNKNOWN: "#4B5563",
}

# The renderer only knows the AnimationId, so it needs its own mapping.
ANIMATION_COLORS: dict[AnimationId, str] = {
    AnimationId.TYPING: STATUS_COLORS[DeskStatus.FOCUSED],
    AnimationId.WORKING_AT_DESK: STATUS_COLORS[DeskStatus.WORKING],
    AnimationId.ORGANIZING_DESK: STATUS_COLORS[DeskStatus.ORGANIZING],
    AnimationId.DRINKING_TEA: STATUS_COLORS[DeskStatus.SHORT_BREAK],
    AnimationId.RESTING: STATUS_COLORS[DeskStatus.SHORT_BREAK],
    AnimationId.TRANSITIONING: STATUS_COLORS[DeskStatus.TRANSITION],
    AnimationId.LOOKING_AROUND: STATUS_COLORS[DeskStatus.NO_MOTION],
    AnimationId.SLEEPING: STATUS_COLORS[DeskStatus.NO_MOTION],
    AnimationId.UNKNOWN: STATUS_COLORS[DeskStatus.UNKNOWN],
}


def status_color(status: DeskStatus) -> str:
    """Return the accent for one abstract state."""
    return STATUS_COLORS.get(status, STATUS_COLORS[DeskStatus.UNKNOWN])


def animation_color(animation: AnimationId) -> str:
    """Return the accent for one animation."""
    return ANIMATION_COLORS.get(animation, STATUS_COLORS[DeskStatus.UNKNOWN])


def resolve_theme(name: str) -> Theme:
    """Return the selected theme."""
    return LIGHT_THEME if name == "light" else DARK_THEME
