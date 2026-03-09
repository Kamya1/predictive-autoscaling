import glob
import os
from dataclasses import dataclass
from typing import List

import matplotlib.pyplot as plt
import pandas as pd


SLA_THRESHOLD = 0.3


@dataclass
class RunSummary:
    path: str
    strategy: str
    scenario: str
    sla_violation_rate: float
    avg_latency: float
    request_count: int


def parse_run_filename(path: str) -> tuple[str, str]:
    base = os.path.basename(path)
    parts = base.split("_")
    if len(parts) < 3:
        return "unknown", "unknown"
    strategy = parts[1]
    scenario = parts[2].split(".")[0]
    return strategy, scenario


def summarize_run(path: str) -> RunSummary:
    df = pd.read_csv(path)
    total = len(df)
    violations = df["sla_violated"].sum()
    violation_rate = violations / total if total > 0 else 0.0
    avg_latency = df["latency_seconds"].mean()
    strategy, scenario = parse_run_filename(path)
    return RunSummary(
        path=path,
        strategy=strategy,
        scenario=scenario,
        sla_violation_rate=violation_rate,
        avg_latency=avg_latency,
        request_count=total,
    )


def plot_latency_over_time(df: pd.DataFrame, out_path: str) -> None:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")
    plt.figure(figsize=(10, 4))
    plt.plot(df["timestamp"], df["latency_seconds"], label="Latency (s)")
    plt.axhline(SLA_THRESHOLD, color="red", linestyle="--", label="SLA threshold")
    plt.xlabel("Time")
    plt.ylabel("Latency (s)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def main() -> None:
    runs_dir = os.path.join(os.path.dirname(__file__), "runs")
    os.makedirs(os.path.join(os.path.dirname(__file__), "plots"), exist_ok=True)

    run_files = glob.glob(os.path.join(runs_dir, "*.csv"))
    summaries: List[RunSummary] = []

    for path in run_files:
        summary = summarize_run(path)
        summaries.append(summary)

        df = pd.read_csv(path)
        plot_name = os.path.basename(path).replace(".csv", "_latency.png")
        plot_path = os.path.join(os.path.dirname(__file__), "plots", plot_name)
        plot_latency_over_time(df, plot_path)
        print(f"Wrote latency plot: {plot_path}")

    if not summaries:
        print("No runs found.")
        return

    summary_df = pd.DataFrame([s.__dict__ for s in summaries])
    pivot = summary_df.pivot_table(
        index="scenario",
        columns="strategy",
        values="sla_violation_rate",
    )
    print("SLA violation rate by scenario/strategy:")
    print(pivot.to_string())

    out_csv = os.path.join(os.path.dirname(__file__), "summary.csv")
    summary_df.to_csv(out_csv, index=False)
    print(f"Wrote summary table: {out_csv}")


if __name__ == "__main__":
    main()

