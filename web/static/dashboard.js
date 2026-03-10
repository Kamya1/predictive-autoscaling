(() => {
  const scenarioSelect = document.getElementById("scenario-select");
  const strategySelect = document.getElementById("strategy-select");
  const runBtn = document.getElementById("run-btn");
  const demoBtn = document.getElementById("demo-btn");

  const runContextEl = document.getElementById("run-context");
  const statusEl = document.getElementById("status-text");

  const metricEls = {
    sla: document.getElementById("metric-sla"),
    latency: document.getElementById("metric-latency"),
    over: document.getElementById("metric-over"),
    under: document.getElementById("metric-under"),
    latencySteps: document.getElementById("metric-latency-steps"),
    config: document.getElementById("metric-config"),
  };

  const ctxWorkload = document.getElementById("workloadChart").getContext("2d");
  const ctxPods = document.getElementById("podsChart").getContext("2d");
  const ctxLatency = document.getElementById("latencyChart").getContext("2d");
  const ctxSla = document.getElementById("slaChart").getContext("2d");

  let workloadChart;
  let podsChart;
  let latencyChart;
  let slaChart;

  let isAnimating = false;
  let currentAnimation = null;

  function createCharts() {
    const commonOptions = {
      responsive: true,
      animation: false,
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        legend: {
          labels: {
            color: "#e5e7eb",
            boxWidth: 10,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "#9ca3af" },
          grid: { color: "rgba(55, 65, 81, 0.3)" },
        },
        y: {
          ticks: { color: "#9ca3af" },
          grid: { color: "rgba(55, 65, 81, 0.35)" },
        },
      },
    };

    workloadChart = new Chart(ctxWorkload, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Actual workload",
            data: [],
            borderColor: "rgba(96, 165, 250, 1)",
            backgroundColor: "rgba(96, 165, 250, 0.2)",
            tension: 0.25,
            borderWidth: 2,
          },
          {
            label: "Predicted workload",
            data: [],
            borderColor: "rgba(249, 115, 22, 1)",
            backgroundColor: "rgba(249, 115, 22, 0.2)",
            borderDash: [4, 4],
            tension: 0.25,
            borderWidth: 2,
          },
        ],
      },
      options: commonOptions,
    });

    podsChart = new Chart(ctxPods, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Pods",
            data: [],
            borderColor: "rgba(52, 211, 153, 1)",
            backgroundColor: "rgba(52, 211, 153, 0.2)",
            tension: 0.1,
            borderWidth: 2,
            stepped: true,
          },
        ],
      },
      options: commonOptions,
    });

    latencyChart = new Chart(ctxLatency, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Latency (ms)",
            data: [],
            borderColor: "rgba(244, 114, 182, 1)",
            backgroundColor: "rgba(244, 114, 182, 0.2)",
            tension: 0.2,
            borderWidth: 2,
          },
        ],
      },
      options: commonOptions,
    });

    slaChart = new Chart(ctxSla, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "SLA violation (1=yes, 0=no)",
            data: [],
            borderColor: "rgba(248, 113, 113, 1)",
            backgroundColor: "rgba(248, 113, 113, 0.25)",
            borderWidth: 2,
            stepped: true,
          },
        ],
      },
      options: {
        ...commonOptions,
        scales: {
          x: commonOptions.scales.x,
          y: {
            ...commonOptions.scales.y,
            suggestedMin: -0.05,
            suggestedMax: 1.05,
          },
        },
      },
    });
  }

  function setButtonsEnabled(enabled) {
    runBtn.disabled = !enabled;
    demoBtn.disabled = !enabled;
  }

  function describeScenario(id) {
    switch (id) {
      case "normal":
        return "Normal workload (smooth sinusoidal traffic).";
      case "flash_crowd":
        return "Flash crowd spike (short, intense surge).";
      case "sudden_permanent_increase":
        return "Sudden permanent increase (step-change to a higher level).";
      case "pattern_drift":
        return "Pattern drift (slowly increasing baseline).";
      default:
        return id;
    }
  }

  function describeStrategy(id) {
    switch (id) {
      case "reactive":
        return "Reactive autoscaling driven by current load.";
      case "predictive":
        return "Predictive autoscaling using short-horizon forecasts.";
      case "predictive_with_fallback":
        return "Predictive autoscaling with a confidence-aware reactive fallback.";
      default:
        return id;
    }
  }

  function updateMetrics(result) {
    if (!result || !result.metrics) return;
    const m = result.metrics;
    metricEls.sla.textContent = m.total_sla_violations.toFixed(0);
    metricEls.latency.textContent = `${m.average_latency_ms.toFixed(1)} ms`;
    metricEls.over.textContent = `${m.over_provisioning_pct.toFixed(1)}%`;
    metricEls.under.textContent = `${m.under_provisioning_pct.toFixed(1)}%`;
    metricEls.latencySteps.textContent = `${m.average_scaling_latency_steps.toFixed(
      2
    )} steps`;

    if (result.config) {
      metricEls.config.textContent = `T = ${
        result.time.length
      } steps, cap ≈ ${result.config.capacity_per_pod.toFixed(0)} req/step/pod`;
    }
  }

  function animateTimeSeries(result, speedMs = 80) {
    if (!workloadChart) return;

    if (currentAnimation) {
      clearInterval(currentAnimation);
      currentAnimation = null;
    }

    workloadChart.data.labels = [];
    workloadChart.data.datasets[0].data = [];
    workloadChart.data.datasets[1].data = [];

    podsChart.data.labels = [];
    podsChart.data.datasets[0].data = [];

    latencyChart.data.labels = [];
    latencyChart.data.datasets[0].data = [];

    slaChart.data.labels = [];
    slaChart.data.datasets[0].data = [];

    workloadChart.update();
    podsChart.update();
    latencyChart.update();
    slaChart.update();

    const { time, workload, predicted_workload, pods, latency_ms, sla_violations } =
      result;

    let idx = 0;
    isAnimating = true;

    return new Promise((resolve) => {
      currentAnimation = setInterval(() => {
        if (idx >= time.length) {
          clearInterval(currentAnimation);
          currentAnimation = null;
          isAnimating = false;
          resolve();
          return;
        }

        const t = time[idx];
        workloadChart.data.labels.push(t);
        workloadChart.data.datasets[0].data.push(workload[idx]);
        workloadChart.data.datasets[1].data.push(predicted_workload[idx]);
        workloadChart.update("none");

        podsChart.data.labels.push(t);
        podsChart.data.datasets[0].data.push(pods[idx]);
        podsChart.update("none");

        latencyChart.data.labels.push(t);
        latencyChart.data.datasets[0].data.push(latency_ms[idx]);
        latencyChart.update("none");

        slaChart.data.labels.push(t);
        slaChart.data.datasets[0].data.push(sla_violations[idx]);
        slaChart.update("none");

        idx += 1;
      }, speedMs);
    });
  }

  async function runSingleSimulation(scenarioId, strategyId) {
    if (isAnimating) return;

    setButtonsEnabled(false);
    statusEl.textContent = "Running simulation…";

    try {
      const res = await fetch("/simulate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          scenario: scenarioId,
          strategy: strategyId,
        }),
      });

      if (!res.ok) {
        const errPayload = await res.json().catch(() => ({}));
        throw new Error(errPayload.error || `Simulation failed with ${res.status}`);
      }

      const result = await res.json();

      const scenarioDesc = describeScenario(scenarioId);
      const strategyDesc = describeStrategy(strategyId);
      runContextEl.innerHTML = `
        Scenario: <span class="pill">${scenarioDesc}</span>
        <br/>
        Strategy: <span class="pill">${strategyDesc}</span>
      `;

      updateMetrics(result);
      await animateTimeSeries(result);

      statusEl.textContent = "Simulation complete.";
    } catch (err) {
      console.error(err);
      statusEl.textContent =
        "Error running simulation. See browser console for details.";
    } finally {
      setButtonsEnabled(true);
    }
  }

  async function runDemo(strategyId) {
    if (isAnimating) return;

    const scenarios = [
      "normal",
      "flash_crowd",
      "sudden_permanent_increase",
      "pattern_drift",
    ];

    setButtonsEnabled(false);
    statusEl.textContent =
      "Demo mode: running all scenarios sequentially for the selected strategy…";

    for (let i = 0; i < scenarios.length; i += 1) {
      const scenarioId = scenarios[i];
      scenarioSelect.value = scenarioId;

      const res = await fetch("/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: scenarioId, strategy: strategyId }),
      });

      if (!res.ok) {
        statusEl.textContent = "Demo mode failed during one of the scenarios.";
        setButtonsEnabled(true);
        return;
      }

      const result = await res.json();

      const scenarioDesc = describeScenario(scenarioId);
      const strategyDesc = describeStrategy(strategyId);
      runContextEl.innerHTML = `
        Demo mode – run ${i + 1} of ${scenarios.length}
        <br/>
        Scenario: <span class="pill">${scenarioDesc}</span>
        <br/>
        Strategy: <span class="pill">${strategyDesc}</span>
      `;

      updateMetrics(result);
      // Run animation slightly faster in demo mode
      // eslint-disable-next-line no-await-in-loop
      await animateTimeSeries(result, 55);

      // brief pause between scenarios
      // eslint-disable-next-line no-await-in-loop
      await new Promise((resolve) => setTimeout(resolve, 350));
    }

    statusEl.textContent = "Demo mode complete.";
    setButtonsEnabled(true);
  }

  function init() {
    createCharts();

    runBtn.addEventListener("click", () => {
      const scenarioId = scenarioSelect.value;
      const strategyId = strategySelect.value;
      runSingleSimulation(scenarioId, strategyId);
    });

    demoBtn.addEventListener("click", () => {
      const strategyId = strategySelect.value;
      runDemo(strategyId);
    });
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    init();
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
})();

