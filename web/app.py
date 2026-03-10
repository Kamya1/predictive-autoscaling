from __future__ import annotations

import os
import sys
import threading
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request

# Ensure we can import from the project root (for simulation modules)
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from simulation.autoscaler import ScalingStrategy  # noqa: E402
from simulation.simulator import (  # noqa: E402
    ScenarioName,
    run_simulation,
)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    @app.route("/")
    def index() -> str:
        return render_template("index.html")

    @app.route("/simulate", methods=["POST"])
    def simulate() -> Any:
        payload: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        scenario_raw = str(payload.get("scenario", "normal"))
        strategy_raw = str(payload.get("strategy", "reactive"))

        # Normalize inputs from the UI to internal identifiers
        scenario_map: Dict[str, ScenarioName] = {
            "normal": "normal",
            "flash_crowd": "flash_crowd",
            "sudden_permanent_increase": "sudden_permanent_increase",
            "pattern_drift": "pattern_drift",
        }

        strategy_map: Dict[str, ScalingStrategy] = {
            "reactive": ScalingStrategy.REACTIVE,
            "predictive": ScalingStrategy.PREDICTIVE,
            "predictive_with_fallback": ScalingStrategy.PREDICTIVE_WITH_FALLBACK,
        }

        if scenario_raw not in scenario_map:
            return jsonify({"error": f"Unknown scenario: {scenario_raw}"}), 400
        if strategy_raw not in strategy_map:
            return jsonify({"error": f"Unknown strategy: {strategy_raw}"}), 400

        scenario = scenario_map[scenario_raw]
        strategy = strategy_map[strategy_raw]

        result = run_simulation(scenario=scenario, strategy=strategy)
        return jsonify(result)

    return app


def _open_browser() -> None:
    try:
        import webbrowser

        webbrowser.open_new("http://localhost:5000")
    except Exception:
        # Best-effort: failure to open a browser should not crash the app.
        pass


if __name__ == "__main__":
    app = create_app()
    # Open a browser tab shortly after the server starts for easy demos
    threading.Timer(1.0, _open_browser).start()
    app.run(host="127.0.0.1", port=5000, debug=True)

