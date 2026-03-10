Predictive Auto-Scaling Robustness under Abrupt Workload Changes
================================================================

This project provides a **reproducible experimental framework** to study how predictive auto-scaling behaves under sudden workload changes (traffic spikes, regime shifts, and pattern drift) in a Kubernetes-based microservice setup.

### 1. High-Level Architecture

- **App (`app/`)**: Python Flask microservice exposing a simple HTTP endpoint and Prometheus metrics.
- **Kubernetes (`k8s/`)**: Manifests for the app Deployment/Service, Horizontal Pod Autoscaler (reactive), Prometheus, and Grafana.
- **Predictor (`predictor/`)**: ARIMA-based scaling controller that forecasts request rate and adjusts replicas via the Kubernetes API/CLI, with a confidence-aware fallback to reactive logic.
- **Load generator (`load-generator/`)**: Python script that drives the app with different workload patterns (periodic, flash crowd, permanent step increase, pattern drift).
- **Experiments (`experiments/`)**: Scripts to deploy the stack, run scenarios under reactive vs predictive scaling, and collect metrics.
- **Metrics & analysis (`metrics/`, `notebooks/`)**: CSV logs and plotting/analysis scripts for SLA violations, over/under-provisioning, scaling latency, and utilization.
- **Simulation dashboard (`web/`, `simulation/`)**: Lightweight, self-contained web UI to demonstrate predictive vs reactive auto-scaling behavior without Kubernetes.

Project layout:

```text
predictive-autoscaling/
├── app/                # Flask microservice
├── docker/             # Dockerfiles
├── k8s/                # Kubernetes YAML configs
├── load-generator/     # Workload drivers
├── predictor/          # Predictive scaler
├── experiments/        # Orchestration scripts
├── metrics/            # Collected metrics and plots
├── notebooks/          # Optional Jupyter analysis
├── simulation/         # In-memory simulation + auto-scaling logic for the dashboard
├── web/                # Flask+Chart.js simulation dashboard (no Kubernetes required)
└── README.md
```

### 2. Prerequisites

- **OS**: Linux, macOS, or Windows with WSL2 (recommended for Kubernetes tooling).
- **Kubernetes**: Minikube or Kind (examples below use Minikube).
- **kubectl** and **Helm** (optional, if you prefer Helm for Prometheus/Grafana).
- **Python 3.9+** with `pip`.
- **Docker** (or compatible container runtime).

### 3. Quick Start (Reactive vs Predictive)

1. **Start Minikube and enable metrics-server**:

```bash
minikube start --cpus=4 --memory=6144
minikube addons enable metrics-server
```

2. **Build images using Minikube Docker daemon**:

```bash
eval $(minikube docker-env)
cd predictive-autoscaling
docker build -t autoscaling-app:latest -f docker/app.Dockerfile .
docker build -t autoscaling-predictor:latest -f docker/predictor.Dockerfile .
docker build -t autoscaling-loadgen:latest -f docker/loadgen.Dockerfile .
```

3. **Deploy the stack (app + Prometheus + Grafana + HPA)**:

```bash
cd predictive-autoscaling/experiments
./deploy.sh
```

4. **Run an experiment**:

Reactive baseline, flash-crowd spike:

```bash
./run_experiment.sh reactive flash_crowd
```

Predictive scaling, flash-crowd spike:

```bash
./run_experiment.sh predictive flash_crowd
```

Each run will:

- Start the chosen scaling strategy (HPA or predictive scaler).
- Run the specified workload scenario via the load generator.
- Save request-level logs and summary metrics under `metrics/`.

5. **Analyze results**:

```bash
cd predictive-autoscaling/metrics
python analyze_results.py
```

This generates:

- **Workload vs replicas** over time.
- **SLA violation rate** comparison between reactive and predictive.
- **Over/under-provisioning** and resource utilization plots.

You can also open the example notebook in `notebooks/` for interactive analysis.

### 4. Auto-Scaling Strategies

- **Reactive (baseline)**:
  - Kubernetes HPA on CPU utilization.
  - Configured via `k8s/hpa-reactive.yaml`.

- **Predictive**:
  - Python ARIMA model on recent request-rate time series (from Prometheus).
  - Predicts short-horizon future load and sets Deployment replicas accordingly.
  - **Confidence-aware fallback**:
    - If prediction interval is wide (high uncertainty), fall back to a simple reactive rule based on current observed load.

### 5. Workload Scenarios

Implemented in `load-generator/scenarios.py`:

- **Normal periodic workload**: sinusoidal / diurnal pattern.
- **Flash crowd spike**: sudden 10× traffic spike for a short window.
- **Sudden permanent increase**: step-change to a higher level that persists.
- **Pattern drift**: slow change in baseline and/or variance over time.

### 6. Metrics and Logging

The framework collects:

- **Per-request logs**: timestamps, response times, HTTP status codes, SLA violation flag.
- **Replica counts** over time (via `kubectl` or the Kubernetes API).
- **Resource utilization** (CPU) via Prometheus.

Outputs:

- CSV files under `metrics/` (e.g. `runs/<timestamp>_<strategy>_<scenario>.csv`).
- Plots saved as PNGs under `metrics/plots/`.

### 7. Failure Mode & Mitigation

The analysis scripts and notebook help diagnose:

- **Prediction lag** relative to workload shifts.
- **Model overconfidence** (narrow intervals yet high SLA violations).
- **Delayed scaling decisions** (slow adjustment of replicas).
- **Workload drift** causing model mismatch.

The provided predictive scaler implements a **confidence-aware fallback**: when forecast uncertainty is high, it reverts to a simple reactive estimate of replicas based on current request rate.

### 8. Interactive Simulation Dashboard (No Kubernetes Required)

For presentations or quick experimentation without spinning up Kubernetes, this repository includes a **self-contained web-based simulation dashboard** that mimics the behavior of reactive vs predictive auto-scaling under abrupt workload changes.

#### Run the dashboard

```bash
cd predictive-autoscaling
python web/app.py
```

This will start a local Flask server at `http://localhost:5000` and automatically open the dashboard in your default browser.

#### Dashboard features

- **Scenario selector**:
  - *Normal workload* (smooth sinusoidal traffic)
  - *Flash crowd spike* (short, intense spike)
  - *Sudden permanent increase* (step-change to a higher level)
  - *Pattern drift* (gradually increasing baseline)
- **Scaling strategy selector**:
  - Reactive autoscaling (baseline)
  - Predictive autoscaling
  - Predictive + confidence-aware fallback (revert to reactive on high prediction error)
- **Start simulation**: runs a 100-timestep in-memory simulation and streams results to the UI.
- **Demo mode**: automatically runs all four scenarios sequentially for the selected strategy—useful for live research demos.

The dashboard visualizes:

- Workload vs predicted workload over time.
- Number of pods over time.
- Response latency vs a fixed SLA threshold.
- SLA violation indicator (per timestep).

It also summarizes:

- Total SLA-violating timesteps.
- Average latency.
- Over- and under-provisioning percentages (fraction of timesteps with too many / too few pods).
- Average scaling latency in timesteps (how long it takes to reach a new required replica level after a jump in true load).

Under the hood, the dashboard uses `simulation/` for a simplified, in-memory model of request rate, predictions, and scaling decisions, and `web/` for a small Flask backend plus an HTML/JavaScript frontend built with Chart.js.

### 9. Next Steps

- Swap ARIMA for LSTM or Prophet in `predictor/` to study model class impact.
- Extend the app complexity (e.g., database calls) to study end-to-end latency.
- Plug in production-grade Prometheus/Grafana stacks via Helm charts.

