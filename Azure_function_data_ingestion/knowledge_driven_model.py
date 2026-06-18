import json
from pathlib import Path
import numpy as np

_PARAMS_PATH = Path(__file__).resolve().parent / "knowledge_driven_model_params.json"
_FITTED_PARAMS = None

def _load_params() -> dict:
    global _FITTED_PARAMS
    if _FITTED_PARAMS is None:
        with open(_PARAMS_PATH) as f:
            _FITTED_PARAMS = json.load(f)
    return _FITTED_PARAMS


def logistic_piece(v, alpha, beta, gamma, delta):
    return alpha / (1 + np.exp(-gamma * (v - delta))) ** (1 / beta)

def double_logistic(v, alpha1, beta1, gamma1, delta1, alpha2, beta2, gamma2, delta2):
    return (logistic_piece(v, alpha1, beta1, gamma1, delta1) +
            logistic_piece(v, alpha2, beta2, gamma2, delta2))

def predict_power_knowledge_model(wind_speed, wind_farm_name: str):
    """
    Predict offshore wind farm power output from wind speed using the
    fitted double-logistic knowledge-driven model.

    Parameters
    ----------
    wind_speed : float, list, or array-like
        Wind speed(s) in m/s, already scaled to platform/hub height.
    wind_farm_name : str
        Farm id matching a key in fitted_params.json (e.g. "Borssele_12").

    Returns
    -------
    numpy.ndarray
        Predicted power in MW, same shape as the input wind_speed.
    """
    WINDSPEED_SCALING_FOR_PLATFORM_HEIGHT = 1.034
    params = _load_params()

    if wind_farm_name not in params:
        raise ValueError(
            f"Unknown wind farm '{wind_farm_name}'. "
            f"Available farms: {list(params.keys())}"
        )

    farm_data = params[wind_farm_name]
    popt = farm_data["params"]
    cut_in = farm_data["cut_in"]
    cut_out = farm_data["cut_out"]

    wind_speed = np.asarray(wind_speed, dtype=float)
    wind_speed = wind_speed * WINDSPEED_SCALING_FOR_PLATFORM_HEIGHT

    p = double_logistic(wind_speed, *popt)
    p = np.where(wind_speed >= cut_out, 0, p)   # cut-out
    p = np.where(wind_speed < cut_in, 0, p)     # cut-in
    p = np.maximum(p, 0)

    return p


if __name__ == "__main__":
    # sanity check
    sample_speeds = [2, 5, 8, 11, 15, 25, 30]
    prediction = predict_power_knowledge_model(sample_speeds, "Borssele_12")
    for v, p in zip(sample_speeds, prediction):
        print(f"wind_speed={v} m/s -> power={p:.2f} MW")