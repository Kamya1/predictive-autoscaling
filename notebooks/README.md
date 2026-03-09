This directory is intended for Jupyter notebooks that perform deeper analysis and visualization for the **Predictive Auto-Scaling Robustness under Abrupt Workload Changes** project.

Suggested notebook ideas:

- Compare **reactive vs predictive** SLA violation rates across all scenarios.
- Visualize **workload vs replicas vs latency** over time.
- Study **failure modes** (prediction lag, overconfidence, drift) by overlaying forecasts with actual load.

You can start with:

```bash
cd predictive-autoscaling
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt jupyter
jupyter notebook
```

