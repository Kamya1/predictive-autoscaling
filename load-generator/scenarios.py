import math
from enum import Enum
from typing import Callable


class Scenario(str, Enum):
    PERIODIC = "periodic"
    FLASH_CROWD = "flash_crowd"
    PERMANENT_STEP = "permanent_step"
    PATTERN_DRIFT = "pattern_drift"


def periodic_workload(t: float, base: float = 10.0, amplitude: float = 5.0, period: float = 120.0) -> float:
    return max(0.0, base + amplitude * math.sin(2 * math.pi * t / period))


def flash_crowd_workload(t: float, base: float = 5.0, spike_factor: float = 10.0, spike_start: float = 120.0, spike_end: float = 180.0) -> float:
    if spike_start <= t <= spike_end:
        return base * spike_factor
    return base


def permanent_step_workload(t: float, base: float = 5.0, step_factor: float = 4.0, step_time: float = 150.0) -> float:
    if t >= step_time:
        return base * step_factor
    return base


def pattern_drift_workload(t: float, base: float = 5.0, drift_rate: float = 0.02) -> float:
    return max(0.0, base + drift_rate * t)


def get_scenario_function(scenario: Scenario) -> Callable[[float], float]:
    if scenario == Scenario.PERIODIC:
        return periodic_workload
    if scenario == Scenario.FLASH_CROWD:
        return flash_crowd_workload
    if scenario == Scenario.PERMANENT_STEP:
        return permanent_step_workload
    if scenario == Scenario.PATTERN_DRIFT:
        return pattern_drift_workload
    raise ValueError(f"Unknown scenario: {scenario}")

