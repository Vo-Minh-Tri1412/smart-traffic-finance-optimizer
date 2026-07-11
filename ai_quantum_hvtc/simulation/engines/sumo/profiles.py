"""Named SUMO execution profiles that do not change demand or rewards."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SumoSimulationProfile:
    profile_id: str
    step_length_seconds: float
    action_step_length_seconds: float
    fcd_period_seconds: float
    lateral_resolution_m: float | None = None

    @property
    def uses_sublane_model(self) -> bool:
        return self.lateral_resolution_m is not None

    def command_args(self) -> list[str]:
        args = [
            "--default.action-step-length",
            f"{self.action_step_length_seconds:g}",
            "--device.fcd.period",
            f"{self.fcd_period_seconds:g}",
        ]
        if self.lateral_resolution_m is not None:
            args.extend(["--lateral-resolution", f"{self.lateral_resolution_m:g}"])
        return args


DEFAULT_SUMO_PROFILE = SumoSimulationProfile(
    profile_id="standard",
    step_length_seconds=1.0,
    action_step_length_seconds=1.0,
    fcd_period_seconds=1.0,
)

GEOMETRY_SENSOR_SUMO_PROFILE = SumoSimulationProfile(
    profile_id="geometry_sensor",
    step_length_seconds=0.2,
    action_step_length_seconds=1.0,
    fcd_period_seconds=1.0,
    lateral_resolution_m=0.4,
)
