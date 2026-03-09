from flask import Flask, jsonify
import os
import random
import time

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST


APP_NAME = os.getenv("APP_NAME", "autoscaling-app")
SLA_THRESHOLD_SECONDS = float(os.getenv("SLA_THRESHOLD_SECONDS", "0.3"))

app = Flask(__name__)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint"],
)

REQUEST_LATENCY = Histogram(
    "http_request_latency_seconds",
    "HTTP request latency",
    ["endpoint"],
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0),
)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": APP_NAME})


@app.route("/work")
def work():
    start = time.time()

    # Simulate variable CPU work
    target_ms = random.randint(20, 150)
    end_time = start + target_ms / 1000.0
    x = 0.0
    while time.time() < end_time:
        x += random.random() * random.random()

    latency = time.time() - start
    REQUEST_COUNT.labels(method="GET", endpoint="/work").inc()
    REQUEST_LATENCY.labels(endpoint="/work").observe(latency)

    sla_violated = latency > SLA_THRESHOLD_SECONDS
    return jsonify(
        {
            "app": APP_NAME,
            "latency_seconds": latency,
            "sla_violated": sla_violated,
            "work_result": x,
        }
    )


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

