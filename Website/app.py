from flask import Flask, render_template
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

STATIONS = {
    "overall": "Overall",
    "gemini": "Gemini",
    "borssele_12": "Borssele 1&2",
    "borssele_34": "Borssele 3&4",
    "hollandse_kust_zuid": "Hollandse Kust Zuid",
    "hollandse_kust_noord": "Hollandse Kust Noord",
}

# Maps our internal station keys to the API's naming convention
API_STATION_NAMES = {
    "overall": "TOTAL",
    "gemini": "Gemini",
    "borssele_12": "Borssele_12",
    "borssele_34": "Borssele_34",
    "hollandse_kust_zuid": "Hollandse_Kust_Zuid",
    "hollandse_kust_noord": "Hollandse_Kust_Noord",
}

API_BASE = "https://offshore-wind-api.azurewebsites.net/api"


def get_forecast_data(station):
    """
    Fetches timeseries data from the REST API for the given station.
    Returns parsed data ready for the dashboard template.
    On API failure, returns an error state with empty charts.
    """
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    future_end = now + timedelta(hours=24)
    past_start = now - timedelta(hours=48)  # request up to 48h back as buffer

    # Pass wide date range to API, we'll trim after
    start = past_start.strftime("%Y-%m-%d")
    end = (future_end + timedelta(days=1)).strftime("%Y-%m-%d")
    api_name = API_STATION_NAMES[station]

    try:
        response = requests.get(
            f"{API_BASE}/windfarms/{api_name}/timeseries",
            params={"start": start, "end": end, "limit": 100},
            timeout=10
        )
        response.raise_for_status()
        raw = response.json()

        # Cap future at now + 24h
        all_readings = [r for r in raw.get("readings", [])
                        if datetime.fromisoformat(r["timestamp"]) <= future_end]

        # Split into past and future
        future_readings = sorted(
            [r for r in all_readings if datetime.fromisoformat(r["timestamp"]) > now],
            key=lambda r: r["timestamp"]
        )
        past_readings = sorted(
            [r for r in all_readings if datetime.fromisoformat(r["timestamp"]) <= now],
            key=lambda r: r["timestamp"]
        )

        # Fill remaining slots with past data to reach 48 total
        past_needed = 48 - len(future_readings)
        past_readings = past_readings[-past_needed:] if len(past_readings) > past_needed else past_readings

        readings = sorted(past_readings + future_readings, key=lambda r: r["timestamp"])
    except Exception as e:
        return {
            "labels": [],
            "knowledge_driven": [],
            "neural_network": [],
            "decision_tree": [],
            "actual": [],
            "wind_speed": [],
            "now_index": 0,
            "has_knowledge_driven": False,
            "has_neural_network": False,
            "has_decision_tree": False,
            "has_actual": False,
            "has_wind_speed": False,
            "metrics_kd": {"mae": "N/A", "rmse": "N/A", "r2": "N/A"},
            "metrics_nn": {"mae": "N/A", "rmse": "N/A", "r2": "N/A"},
            "metrics_dt": {"mae": "N/A", "rmse": "N/A", "r2": "N/A"},
            "last_updated": now.strftime("%d %b %Y, %H:%M"),
            "data_source": f"API error: {str(e)}",
            "station_name": STATIONS[station],
            "error": True,
        }

    # Parse readings
    labels = []
    timestamps = []
    knowledge_driven = []
    neural_network = []
    decision_tree = []
    actual = []
    wind_speed = []

    for i, r in enumerate(readings):
        ts = datetime.fromisoformat(r["timestamp"])
        timestamps.append(ts)
        labels.append(ts.strftime("%d %b %H:%M"))

        preds = r.get("predictions", {})
        knowledge_driven.append(round(preds["knowledge_based_mw"], 2) if "knowledge_based_mw" in preds else None)
        neural_network.append(round(preds["neural_network_mw"], 2) if "neural_network_mw" in preds else None)
        decision_tree.append(round(preds["decision_tree_mw"], 2) if "decision_tree_mw" in preds else None)

        actual.append(round(r["actual_mw"], 2) if "actual_mw" in r else None)

        weather = r.get("weather_data", r.get("weather", {}))
        wind_speed.append(round(weather["wind_speed_ms"], 2) if "wind_speed_ms" in weather else None)

    # now_index: find exact match for now, or last timestamp <= now
    now_index = -1
    if timestamps:
        for i, ts in enumerate(timestamps):
            if ts <= now:
                now_index = i
        # If now is after all data, don't show line
        if timestamps[-1] < now - timedelta(hours=1):
            now_index = -1

    # Check which models actually have data
    has_knowledge_driven = any(v is not None for v in knowledge_driven)
    has_neural_network = any(v is not None for v in neural_network)
    has_decision_tree = any(v is not None for v in decision_tree)
    has_actual = any(v is not None for v in actual)

    # Calculate live accuracy metrics where both prediction and actual exist
    def calc_metrics(predictions, actuals):
        pairs = [(p, a) for p, a in zip(predictions, actuals) if p is not None and a is not None]
        if len(pairs) < 2:
            return {"mae": "N/A", "rmse": "N/A", "r2": "N/A"}
        import math
        n = len(pairs)
        mae = round(sum(abs(p - a) for p, a in pairs) / n, 2)
        rmse = round(math.sqrt(sum((p - a) ** 2 for p, a in pairs) / n), 2)
        mean_a = sum(a for _, a in pairs) / n
        ss_res = sum((p - a) ** 2 for p, a in pairs)
        ss_tot = sum((a - mean_a) ** 2 for _, a in pairs)
        r2 = round(1 - ss_res / ss_tot, 3) if ss_tot > 0 else "N/A"
        return {"mae": mae, "rmse": rmse, "r2": r2, "n": n}

    metrics_kd = calc_metrics(knowledge_driven, actual) if has_knowledge_driven and has_actual else {"mae": "N/A", "rmse": "N/A", "r2": "N/A"}
    metrics_nn = calc_metrics(neural_network, actual) if has_neural_network and has_actual else {"mae": "N/A", "rmse": "N/A", "r2": "N/A"}
    metrics_dt = calc_metrics(decision_tree, actual) if has_decision_tree and has_actual else {"mae": "N/A", "rmse": "N/A", "r2": "N/A"}

    return {
        "labels": labels,
        "knowledge_driven": knowledge_driven,
        "neural_network": neural_network,
        "decision_tree": decision_tree,
        "actual": actual,
        "wind_speed": wind_speed,
        "now_index": now_index,
        "has_knowledge_driven": has_knowledge_driven,
        "has_neural_network": has_neural_network,
        "has_decision_tree": has_decision_tree,
        "has_wind_speed": any(v is not None for v in wind_speed),
        "metrics_kd": metrics_kd,
        "metrics_nn": metrics_nn,
        "metrics_dt": metrics_dt,
        "has_actual": has_actual,
        "last_updated": now.strftime("%d %b %Y, %H:%M"),
        "data_source": "Live data from REST API",
        "station_name": STATIONS[station],
        "error": False,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard/<station>")
def dashboard(station):
    if station not in STATIONS:
        return "Station not found", 404
    data = get_forecast_data(station)
    return render_template("dashboard.html", data=data, station=station)


if __name__ == "__main__":
    app.run(debug=True)
