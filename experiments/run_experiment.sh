#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <reactive|predictive> <periodic|flash_crowd|permanent_step|pattern_drift>"
  exit 1
fi

STRATEGY="$1"
SCENARIO="$2"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
METRICS_DIR="$ROOT_DIR/metrics/runs"
mkdir -p "$METRICS_DIR"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
CSV_PATH="$METRICS_DIR/${TIMESTAMP}_${STRATEGY}_${SCENARIO}.csv"

NODE_IP=$(minikube ip)
BASE_URL="http://${NODE_IP}:30080"

echo "Running experiment: strategy=${STRATEGY}, scenario=${SCENARIO}"
echo "App base URL: ${BASE_URL}"

if [[ "$STRATEGY" == "reactive" ]]; then
  kubectl apply -f "$ROOT_DIR/k8s/hpa-reactive.yaml"
elif [[ "$STRATEGY" == "predictive" ]]; then
  kubectl delete hpa autoscaling-app-hpa -n autoscaling-experiments --ignore-not-found
  echo "Starting predictive scaler in background..."
  python "$ROOT_DIR/predictor/predictive_scaler.py" \
    --interval-seconds 20 \
    --history-minutes 10 \
    --forecast-horizon-seconds 60 \
    --target-rps-per-pod 20.0 \
    --min-replicas 2 \
    --max-replicas 10 \
    --uncertainty-threshold 30.0 &
  SCALER_PID=$!
else
  echo "Unknown strategy: $STRATEGY"
  exit 1
fi

python "$ROOT_DIR/load-generator/run_load.py" \
  --scenario "$SCENARIO" \
  --duration-seconds 300 \
  --base-url "$BASE_URL" \
  --output-csv "$CSV_PATH"

if [[ "${SCALER_PID:-}" != "" ]]; then
  echo "Stopping predictive scaler (pid=${SCALER_PID})..."
  kill "$SCALER_PID" || true
fi

echo "Experiment complete. Results written to: $CSV_PATH"

