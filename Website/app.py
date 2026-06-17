from flask import Flask, render_template
import random
from datetime import datetime, timedelta

app = Flask(__name__)

def get_forecast_data():
    """
    Returns mock hourly forecast data for the dashboard.
    Replace the body of this function with a REST API call when ready.
    """
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    hours = [now + timedelta(hours=i) for i in range(24)]

    random.seed(42)
    power_output = [round(random.uniform(50, 500), 2) for _ in hours]
    actual_output = [round(v + random.uniform(-30, 30), 2) for v in power_output]

    return {
        "labels": [h.strftime("%H:%M") for h in hours],
        "predicted": power_output,
        "actual": actual_output,
        "metrics": {
            "mae": 24.3,
            "rmse": 31.7,
            "r2": 0.91,
        },
        "last_updated": now.strftime("%d %b %Y, %H:%M"),
        "data_source": "Placeholder (REST API not yet connected)",
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    data = get_forecast_data()
    return render_template("dashboard.html", data=data)


if __name__ == "__main__":
    app.run(debug=True)
