#!/usr/bin/env python3

from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory
from bms_calculator import calculate_api
from adv_calculator import compute_advanced

app = Flask(__name__, static_folder=Path(__file__).resolve().parent)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    try:
        data = request.get_json() or {}
        period = float(data.get("period", 0))
        eclipse = float(data.get("eclipse", 0))
        power = float(data.get("power", 0))
        voltage = float(data.get("voltage", 0))
    except (TypeError, ValueError) as e:
        return jsonify({"error": "Invalid inputs", "detail": str(e)}), 400

    if period <= 0 or eclipse <= 0 or power <= 0 or voltage <= 0:
        return jsonify({"error": "All inputs must be positive numbers"}), 400

    result = calculate_api(
        orbital_period_min=period,
        eclipse_duration_min=eclipse,
        average_payload_power_W=power,
        nominal_battery_voltage_V=voltage,
    )
    return jsonify(result)


@app.route("/api/advanced", methods=["POST"])
def api_advanced():
    try:
        data = request.get_json() or {}
        period = float(data.get("period", 0))
        eclipse = float(data.get("eclipse", 0))
        power = float(data.get("power", 0))
        voltage = float(data.get("voltage", 0))
    except (TypeError, ValueError) as e:
        return jsonify({"error": "Invalid main inputs", "detail": str(e)}), 400

    if period <= 0 or eclipse <= 0 or power <= 0 or voltage <= 0:
        return jsonify({"error": "Period, eclipse, power, and voltage must be positive"}), 400

    # Base capacity for advanced sizing (same as UI: E * 1.15)
    energy_wh = power * (eclipse / 60.0)
    base_capacity_wh = energy_wh * 1.15

    def get_float(key: str, default: float) -> float:
        try:
            v = data.get(key)
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    def get_int(key: str, default: int) -> int:
        try:
            v = data.get(key)
            return int(float(v)) if v is not None else default
        except (TypeError, ValueError):
            return default

    result = compute_advanced(
        base_capacity_wh=base_capacity_wh,
        v_nom=voltage,
        pack_loss_pct=get_float("pack_loss_pct", 2.0),
        divergence_pct=get_float("divergence_pct", 3.0),
        redundancy_n=get_float("redundancy_n", 1.0),
        ageing_pct=get_float("ageing_pct", 10.0),
        temp_pct=get_float("temp_pct", 5.0),
        anomaly_wh=get_float("anomaly_wh", 20.0),
        cell_ah=get_float("cell_ah", 5.0),
        series=get_int("series", 8),
        parallel=get_int("parallel", 1),
        eol_factor=get_float("eol_factor", 0.8),
        eocv_per_cell_v=get_float("eocv_per_cell_v", 4.2),
        eodv_per_cell_v=get_float("eodv_per_cell_v", 3.0),
        c_rate_charge=get_float("c_rate_charge", 0.5),
        c_rate_discharge=get_float("c_rate_discharge", 2.0),
    )
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
