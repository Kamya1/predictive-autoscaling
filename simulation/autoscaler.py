from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ScalingStrategy(str, Enum):
    """High-level scaling strategies exposed to the web UI."""

    REACTIVE = "reactive"
    PREDICTIVE = "predictive"
    PREDICTIVE_WITH_FALLBACK = "predictive_with_fallback"


@dataclass
class SimulationConfig:
    """Configuration values for the simplified simulation model."""

    time_steps: int = 100
    capacity_per_pod: float = 50.0  # requests per timestep at healthy utilization
    sla_threshold_ms: float = 200.0
    base_latency_ms: float = 50.0
    utilization_knee: float = 0.7  # utilization above which latency grows quickly
    latency_slope: float = 4.0
    min_pods: int = 1
    max_pods: int = 50
    prediction_lookahead: int = 5  # timesteps to "peek" into the future for predictive scaling
    prediction_error_threshold: float = 0.3  # relative error above which we fall back to reactive


DEFAULT_CONFIG = SimulationConfig()

