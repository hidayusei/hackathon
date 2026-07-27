"""Deterministic dummy-source scenario definitions."""

from dataclasses import dataclass

from deskmate.ui.labels import SCENARIO_LABELS_JA


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    """Parameters controlling one synthetic event pattern."""

    scenario_id: str
    label: str
    base_rate_eps: float
    rate_jitter: float
    burst_period_s: float | None
    burst_duty: float
    centers: tuple[tuple[float, float], ...]
    center_switch_s: float
    sigma_px: float
    drift_px_per_s: float
    positive_ratio: float
    uniform_noise_ratio: float
    rate_decay_per_s: float
    dropout: bool


def _scenario(
    scenario_id: str,
    rate: float,
    jitter: float,
    centers: tuple[tuple[float, float], ...],
    sigma: float,
    **values: object,
) -> ScenarioSpec:
    return ScenarioSpec(
        scenario_id=scenario_id,
        label=SCENARIO_LABELS_JA[scenario_id],
        base_rate_eps=rate,
        rate_jitter=jitter,
        burst_period_s=values.get("burst_period_s"),  # type: ignore[arg-type]
        burst_duty=float(values.get("burst_duty", 1.0)),
        centers=centers,
        center_switch_s=float(values.get("center_switch_s", 0.0)),
        sigma_px=sigma,
        drift_px_per_s=float(values.get("drift_px_per_s", 0.0)),
        positive_ratio=float(values.get("positive_ratio", 0.5)),
        uniform_noise_ratio=float(values.get("uniform_noise_ratio", 0.0)),
        rate_decay_per_s=float(values.get("rate_decay_per_s", 1.0)),
        dropout=bool(values.get("dropout", False)),
    )


SCENARIOS: dict[str, ScenarioSpec] = {
    "keyboard_focus": _scenario(
        "keyboard_focus",
        1400.0,
        0.15,
        ((0.50, 0.82),),
        22.0,
        drift_px_per_s=1.0,
        uniform_noise_ratio=0.03,
    ),
    "mouse_intermittent": _scenario(
        "mouse_intermittent",
        2000.0,
        0.25,
        ((0.86, 0.80),),
        17.0,
        burst_period_s=1.0,
        burst_duty=0.60,
        drift_px_per_s=3.0,
        positive_ratio=0.52,
        uniform_noise_ratio=0.03,
    ),
    "desk_wide": _scenario(
        "desk_wide",
        4000.0,
        0.30,
        ((0.20, 0.35), (0.50, 0.45), (0.80, 0.30), (0.45, 0.75)),
        60.0,
        center_switch_s=1.2,
        drift_px_per_s=22.0,
        uniform_noise_ratio=0.06,
    ),
    "quiet": _scenario(
        "quiet",
        20.0,
        0.50,
        ((0.50, 0.50),),
        110.0,
        uniform_noise_ratio=1.0,
    ),
    "dropout": _scenario(
        "dropout",
        0.0,
        0.0,
        ((0.50, 0.50),),
        0.0,
        dropout=True,
    ),
}


@dataclass(frozen=True, slots=True)
class DemoStep:
    """One timed section of the automatic demo."""

    scenario_id: str
    duration_s: float


DEMO_SEQUENCE: tuple[DemoStep, ...] = (
    DemoStep("keyboard_focus", 50.0),
    DemoStep("mouse_intermittent", 35.0),
    DemoStep("desk_wide", 30.0),
    DemoStep("quiet", 55.0),
    DemoStep("keyboard_focus", 25.0),
    DemoStep("dropout", 15.0),
)
