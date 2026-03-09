#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

kubectl apply -f "$ROOT_DIR/k8s/namespace.yaml"
kubectl apply -f "$ROOT_DIR/k8s/app-deployment.yaml"
kubectl apply -f "$ROOT_DIR/k8s/app-service.yaml"
kubectl apply -f "$ROOT_DIR/k8s/prometheus-config.yaml"
kubectl apply -f "$ROOT_DIR/k8s/prometheus-deployment.yaml"
kubectl apply -f "$ROOT_DIR/k8s/grafana-deployment.yaml"
kubectl apply -f "$ROOT_DIR/k8s/hpa-reactive.yaml"

echo "Deployment complete. Use 'minikube service -n autoscaling-experiments autoscaling-app-nodeport' to get app URL."

