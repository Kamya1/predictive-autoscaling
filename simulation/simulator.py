from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Dict, List, Literal, TypedDict

from .autoscaler import DEFAULT_CONFIG, ScalingStrategy, SimulationConfig


ScenarioName = Literal[
    "normal",
    "flash_crowd",
    "sudden_permanent_increase",
    "pattern_drift",
]


class SimulationResult(TypedDict):
    time: List[int]
    workload: List[float]
    predicted_workload: List[float]
    pods: List[int]
    latency_ms: List[float]
    sla_violations: List[int]
    metrics: Dict[str, float]
    config: Dict[str, float]
    scenario: str
    strategy: str


@dataclass
class WorkloadPattern:
    """Simple workload pattern functions for the four scenarios."""

    time_steps: int

    def normal(self) -> List[float]:
        # Smooth sinusoidal load between ~40 and ~80 requests
        return [
            60.0 + 20.0 * math.sin(2 * math.pi * t / 24.0)
            for t in range(self.time_steps)
        ]

    def flash_crowd(self) -> List[float]:
        # Low baseline with a sharp spike
        values: List[float] = []
        for t in range(self.time_steps):
            base = 30.0
            if 30 <= t <= 45:
                values.append(base * 6.0)
            else:
                values.append(base)
        return values

    def sudden_permanent_increase(self) -> List[float]:
        # Step function: permanent jump to a higher level
        values: List[float] = []
        for t in range(self.time_steps):
            if t < 40:
                values.append(30.0)
            else:
                values.append(80.0)
        return values

    def pattern_drift(self) -> List[float]:
        # Gradual linear increase over time
        values: List[float] = []
        for t in range(self.time_steps):
            values.append(20.0 + 0.8 * t)
        return values


def _build_workload(scenario: ScenarioName, time_steps: int) -> List[float]:
    pattern = WorkloadPattern(time_steps=time_steps)
    if scenario == "normal":
        return pattern.normal()
    if scenario == "flash_crowd":
        return pattern.flash_crowd()
    if scenario == "sudden_permanent_increase":
        return pattern.sudden_permanent_increase()
    if scenario == "pattern_drift":
        return pattern.pattern_drift()
    raise ValueError(f"Unknown scenario: {scenario}")


def _build_predictions(
    workload: List[float],
    strategy: ScalingStrategy,
    cfg: SimulationConfig,
) -> List[float]:
    """Very lightweight prediction model.

    - Reactive: 1-step lag (essentially no real prediction).
    - Predictive: peek ahead by `prediction_lookahead` steps.
    - Predictive with fallback: same predictions; fallback is applied in scaling logic.
    """
    n = len(workload)
    predicted = [workload[0]] * n

    if strategy == ScalingStrategy.REACTIVE:
        for t in range(1, n):
            predicted[t] = workload[t - 1]
        return predicted

    # Predictive variants "peek" into the future to simulate a better model
    lookahead = cfg.prediction_lookahead
    for t in range(n):
        future_idx = min(t + lookahead, n - 1)
        predicted[t] = workload[future_idx]
    return predicted


def run_simulation(
    scenario: ScenarioName,
    strategy: ScalingStrategy,
    cfg: SimulationConfig | None = None,
) -> SimulationResult:
    """Run a single simulation and return time series plus summary metrics."""
    cfg = cfg or DEFAULT_CONFIG

    time_steps = cfg.time_steps
    time_axis = list(range(time_steps))

    workload = _build_workload(scenario, time_steps)
    predicted = _build_predictions(workload, strategy, cfg)

    pods: List[int] = []
    latency: List[float] = []
    sla_flags: List[int] = []

    required_pods_true: List[int] = []

    # For scaling latency: track how long it takes to hit new required pod levels
    scaling_latencies: List[int] = []
    pending_target: int | None = None
    pending_start_step: int | None = None

    current_pods = max(cfg.min_pods, 2)

    for t in range(time_steps):
        current_load = workload[t]
        predicted_load = predicted[t]

        # Required pods according to *true* load, used for metrics
        true_required = max(
            cfg.min_pods,
            min(
                cfg.max_pods,
                math.ceil(current_load / cfg.capacity_per_pod) if cfg.capacity_per_pod > 0 else cfg.min_pods,
            ),
        )
        required_pods_true.append(true_required)

        # Effective load used for scaling decision depends on strategy
        if strategy == ScalingStrategy.REACTIVE:
            effective_load = current_load
        else:
            # Predictive or predictive-with-fallback
            effective_load = predicted_load
            if strategy == ScalingStrategy.PREDICTIVE_WITH_FALLBACK:
                # Simple confidence-aware fallback based on instantaneous relative error
                denom = max(current_load, 1.0)
                rel_error = abs(predicted_load - current_load) / denom
                if rel_error > cfg.prediction_error_threshold:
                    effective_load = current_load

        desired_pods = max(
            cfg.min_pods,
            min(
                cfg.max_pods,
                math.ceil(effective_load / cfg.capacity_per_pod) if cfg.capacity_per_pod > 0 else cfg.min_pods,
            ),
        )

        # Simple step-wise scaling to capture scaling latency
        if desired_pods > current_pods:
            current_pods += 1
        elif desired_pods < current_pods:
            current_pods -= 1

        current_pods = max(cfg.min_pods, min(cfg.max_pods, current_pods))
        pods.append(current_pods)

        # Track scaling latency whenever the *true* required pod count jumps up
        if t > 0 and true_required > required_pods_true[t - 1]:
            pending_target = true_required
            pending_start_step = t
        if pending_target is not None and pending_start_step is not None:
            if current_pods >= pending_target:
                scaling_latencies.append(t - pending_start_step)
                pending_target = None
                pending_start_step = None

        # Latency model: grows quickly once utilization crosses the knee
        utilization = 0.0
        if current_pods * cfg.capacity_per_pod > 0:
            utilization = current_load / (current_pods * cfg.capacity_per_pod)

        if utilization <= cfg.utilization_knee:
            # Healthy region: latency stays close to base
            step_latency = cfg.base_latency_ms * (0.7 + 0.3 * (utilization / max(cfg.utilization_knee, 1e-6)))
        else:
            over = utilization - cfg.utilization_knee
            step_latency = cfg.base_latency_ms * (1.0 + cfg.latency_slope * over)

        latency.append(step_latency)
        sla_flags.append(1 if step_latency > cfg.sla_threshold_ms else 0)

    # Summary metrics
    total_sla_violations = sum(sla_flags)
    avg_latency = sum(latency) / len(latency) if latency else 0.0

    over_steps = 0
    under_steps = 0
    for t in range(time_steps):
        if pods[t] > required_pods_true[t]:
            over_steps += 1
        elif pods[t] < required_pods_true[t]:
            under_steps += 1

    over_provision_pct = (over_steps / time_steps) * 100.0 if time_steps else 0.0
    under_provision_pct = (under_steps / time_steps) * 100.0 if time_steps else 0.0

    avg_scaling_latency = (
        sum(scaling_latencies) / len(scaling_latencies) if scaling_latencies else 0.0
    )

    metrics = {
        "total_sla_violations": float(total_sla_violations),
        "average_latency_ms": float(round(avg_latency, 2)),
        "over_provisioning_pct": float(round(over_provision_pct, 2)),
        "under_provisioning_pct": float(round(under_provision_pct, 2)),
        "average_scaling_latency_steps": float(round(avg_scaling_latency, 2)),
    }

    return SimulationResult(
        time=time_axis,
        workload=workload,
        predicted_workload=predicted,
        pods=pods,
        latency_ms=latency,
        sla_violations=sla_flags,
        metrics=metrics,
        config=asdict(cfg),
        scenario=scenario,
        strategy=str(strategy.value),
    )
if __name__ == "__main__":
    scenario = "flash_crowd"
    strategy = ScalingStrategy.PREDICTIVE_WITH_FALLBACK

    result = run_simulation(scenario, strategy)

    print("\nSimulation Results")
    print("------------------")
    print("Scenario:", result["scenario"])
    print("Strategy:", result["strategy"])
    print("Metrics:", result["metrics"])   

