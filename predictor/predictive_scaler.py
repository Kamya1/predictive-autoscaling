import argparse
import datetime as dt
import os
import subprocess
import sys
import time
from typing import Tuple

import numpy as np
import pandas as pd
import requests
from statsmodels.tsa.arima.model import ARIMA


PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus.autoscaling-experiments.svc.cluster.local:9090")
NAMESPACE = os.getenv("NAMESPACE", "autoscaling-experiments")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME", "autoscaling-app")


def query_prometheus_range(
    metric: str,
    start: dt.datetime,
    end: dt.datetime,
    step: str = "5s",
) -> pd.Series:
    query = metric
    url = f"{PROMETHEUS_URL}/api/v1/query_range"
    params = {
        "query": query,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "step": step,
    }
    resp = requests.get(url, params=params, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    if data["status"] != "success" or not data["data"]["result"]:
        raise RuntimeError(f"No Prometheus data for query={query}")

    # Assume a single time series: use first result
    values = data["data"]["result"][0]["values"]
    timestamps = [dt.datetime.fromtimestamp(float(ts)) for ts, _ in values]
    series_values = [float(v) for _, v in values]
    return pd.Series(data=series_values, index=pd.to_datetime(timestamps))


def compute_request_rate(series: pd.Series) -> pd.Series:
    # Prometheus counter -> per-second rate approximation
    diffs = series.diff()
    secs = series.index.to_series().diff().dt.total_seconds()
    rate = diffs / secs
    rate = rate.fillna(0).clip(lower=0)
    return rate


def fit_arima_forecast(
    series: pd.Series,
    horizon_steps: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    model = ARIMA(series, order=(2, 0, 2))
    fitted = model.fit()
    forecast_res = fitted.get_forecast(steps=horizon_steps)
    mean = forecast_res.predicted_mean.values
    conf_int = forecast_res.conf_int(alpha=0.2)  # 80% interval
    lower = conf_int.iloc[:, 0].values
    upper = conf_int.iloc[:, 1].values
    return mean, lower, upper


def infer_replicas_from_rate(current_rate: float, target_per_pod: float, min_replicas: int, max_replicas: int) -> int:
    replicas = int(np.ceil(current_rate / target_per_pod)) if target_per_pod > 0 else min_replicas
    replicas = max(min_replicas, min(max_replicas, replicas))
    return replicas


def scale_deployment(replicas: int) -> None:
    cmd = [
        "kubectl",
        "scale",
        f"--namespace={NAMESPACE}",
        f"deployment/{DEPLOYMENT_NAME}",
        f"--replicas={replicas}",
    ]
    subprocess.run(cmd, check=True)


def run_loop(
    interval_seconds: int,
    history_minutes: int,
    forecast_horizon_seconds: int,
    target_rps_per_pod: float,
    min_replicas: int,
    max_replicas: int,
    uncertainty_threshold: float,
):
    print("Starting predictive scaler loop...", file=sys.stderr)
    horizon_steps = max(1, int(forecast_horizon_seconds / 5))

    while True:
        try:
            end = dt.datetime.utcnow()
            start = end - dt.timedelta(minutes=history_minutes)

            counter = query_prometheus_range(
                'rate(http_requests_total{endpoint="/work"}[30s])',
                start=start,
                end=end,
                step="5s",
            )

            # counter is already a rate() query; treat as rate samples
            rate_series = counter

            if len(rate_series) < 5:
                time.sleep(interval_seconds)
                continue

            mean, lower, upper = fit_arima_forecast(rate_series, horizon_steps=horizon_steps)
            mean_rate = float(np.mean(mean))
            lower_rate = float(np.min(lower))
            upper_rate = float(np.max(upper))

            spread = upper_rate - lower_rate
            print(
                f"[predictive] mean_rate={mean_rate:.2f} rps, "
                f"interval=[{lower_rate:.2f}, {upper_rate:.2f}], spread={spread:.2f}",
                file=sys.stderr,
            )

            if spread > uncertainty_threshold:
                current_rate = float(rate_series.iloc[-1])
                desired_replicas = infer_replicas_from_rate(
                    current_rate, target_rps_per_pod, min_replicas, max_replicas
                )
                print(
                    f"[fallback-reactive] current_rate={current_rate:.2f}, replicas={desired_replicas}",
                    file=sys.stderr,
                )
            else:
                desired_replicas = infer_replicas_from_rate(
                    mean_rate, target_rps_per_pod, min_replicas, max_replicas
                )
                print(f"[predictive-scale] replicas={desired_replicas}", file=sys.stderr)

            scale_deployment(desired_replicas)

        except Exception as exc:  # noqa: BLE001
            print(f"Predictive scaler error: {exc}", file=sys.stderr)

        time.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="ARIMA-based predictive scaler for autoscaling-app.")
    parser.add_argument("--interval-seconds", type=int, default=20)
    parser.add_argument("--history-minutes", type=int, default=10)
    parser.add_argument("--forecast-horizon-seconds", type=int, default=60)
    parser.add_argument("--target-rps-per-pod", type=float, default=20.0)
    parser.add_argument("--min-replicas", type=int, default=2)
    parser.add_argument("--max-replicas", type=int, default=10)
    parser.add_argument("--uncertainty-threshold", type=float, default=30.0)

    args = parser.parse_args()
    run_loop(
        interval_seconds=args.interval_seconds,
        history_minutes=args.history_minutes,
        forecast_horizon_seconds=args.forecast_horizon_seconds,
        target_rps_per_pod=args.target_rps_per_pod,
        min_replicas=args.min_replicas,
        max_replicas=args.max_replicas,
        uncertainty_threshold=args.uncertainty_threshold,
    )


if __name__ == "__main__":
    main()

