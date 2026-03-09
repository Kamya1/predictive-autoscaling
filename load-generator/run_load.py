import argparse
import csv
import datetime as dt
import time
from typing import Dict, Any

import httpx

from scenarios import Scenario, get_scenario_function


async def main() -> None:  # type: ignore[override]
    parser = argparse.ArgumentParser(description="Load generator for autoscaling experiments.")
    parser.add_argument("--scenario", type=str, required=True, choices=[s.value for s in Scenario])
    parser.add_argument("--duration-seconds", type=int, default=300)
    parser.add_argument("--base-url", type=str, default="http://localhost:30080")
    parser.add_argument("--output-csv", type=str, required=True)
    parser.add_argument("--sla-threshold", type=float, default=0.3)
    parser.add_argument("--max_concurrency", type=int, default=100)

    args = parser.parse_args()

    scenario = Scenario(args.scenario)
    workload_fn = get_scenario_function(scenario)

    start_time = time.time()
    records: list[Dict[str, Any]] = []

    client = httpx.Client(timeout=5.0)

    try:
        while True:
            now = time.time()
            elapsed = now - start_time
            if elapsed > args.duration_seconds:
                break

            target_rps = workload_fn(elapsed)
            interval = 1.0
            requests_this_interval = int(target_rps * interval)

            for _ in range(requests_this_interval):
                req_start = time.time()
                ts = dt.datetime.utcnow().isoformat()
                try:
                    resp = client.get(f"{args.base_url}/work")
                    latency = time.time() - req_start
                    sla_violated = latency > args.sla_threshold
                    records.append(
                        {
                            "timestamp": ts,
                            "scenario": scenario.value,
                            "target_rps": target_rps,
                            "latency_seconds": latency,
                            "status_code": resp.status_code,
                            "sla_violated": int(sla_violated),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    latency = time.time() - req_start
                    records.append(
                        {
                            "timestamp": ts,
                            "scenario": scenario.value,
                            "target_rps": target_rps,
                            "latency_seconds": latency,
                            "status_code": 0,
                            "sla_violated": 1,
                            "error": str(exc),
                        }
                    )

            sleep_time = start_time + (int(elapsed) + 1) - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        client.close()

    fieldnames = [
        "timestamp",
        "scenario",
        "target_rps",
        "latency_seconds",
        "status_code",
        "sla_violated",
        "error",
    ]
    with open(args.output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow(row)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

