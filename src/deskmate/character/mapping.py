"""Canonical three-state animation mapping."""

from deskmate.core.enums import AnimationId, DeskStatus, SystemStatus


def resolve_animation(
    status: DeskStatus,
    break_due: bool,
    system_status: SystemStatus = SystemStatus.RUNNING,
) -> AnimationId:
    """Resolve system, break, and activity animation in priority order."""

    if system_status is not SystemStatus.RUNNING:
        return AnimationId.SITTING
    if break_due:
        return AnimationId.BREAK
    if status is DeskStatus.AWAY:
        return AnimationId.SLEEPING
    if status is DeskStatus.FOCUSED:
        return AnimationId.RUNNING
    return AnimationId.SITTING
