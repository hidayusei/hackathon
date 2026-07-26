"""Canonical state-to-animation mapping."""

from dataclasses import dataclass

from deskmate.core.enums import AnimationId, DeskStatus, SystemStatus


@dataclass(frozen=True, slots=True)
class AnimationRule:
    """One duration-sensitive animation rule."""

    status: DeskStatus
    min_duration_s: float
    animation: AnimationId


ANIMATION_RULES: tuple[AnimationRule, ...] = (
    AnimationRule(DeskStatus.FOCUSED, 0, AnimationId.TYPING),
    AnimationRule(DeskStatus.FOCUSED, 600, AnimationId.WORKING_AT_DESK),
    AnimationRule(DeskStatus.WORKING, 0, AnimationId.WORKING_AT_DESK),
    AnimationRule(DeskStatus.ORGANIZING, 0, AnimationId.ORGANIZING_DESK),
    AnimationRule(DeskStatus.SHORT_BREAK, 0, AnimationId.DRINKING_TEA),
    AnimationRule(DeskStatus.SHORT_BREAK, 60, AnimationId.RESTING),
    AnimationRule(DeskStatus.TRANSITION, 0, AnimationId.TRANSITIONING),
    AnimationRule(DeskStatus.NO_MOTION, 0, AnimationId.LOOKING_AROUND),
    AnimationRule(DeskStatus.NO_MOTION, 120, AnimationId.SLEEPING),
    AnimationRule(DeskStatus.UNKNOWN, 0, AnimationId.UNKNOWN),
)

SYSTEM_ANIMATION: dict[SystemStatus, AnimationId] = {
    SystemStatus.STARTING: AnimationId.UNKNOWN,
    SystemStatus.NO_SIGNAL: AnimationId.UNKNOWN,
    SystemStatus.PAUSED: AnimationId.RESTING,
    SystemStatus.ERROR: AnimationId.UNKNOWN,
}


def resolve_animation(
    status: DeskStatus,
    duration_seconds: float,
    system_status: SystemStatus = SystemStatus.RUNNING,
) -> AnimationId:
    """Resolve the highest matching duration rule, with system overrides."""
    if system_status not in {SystemStatus.RUNNING, SystemStatus.SHARING_OFF}:
        return SYSTEM_ANIMATION.get(system_status, AnimationId.UNKNOWN)
    matches = [
        rule
        for rule in ANIMATION_RULES
        if rule.status is status and rule.min_duration_s <= duration_seconds
    ]
    if not matches:
        return AnimationId.UNKNOWN
    return max(matches, key=lambda rule: rule.min_duration_s).animation
