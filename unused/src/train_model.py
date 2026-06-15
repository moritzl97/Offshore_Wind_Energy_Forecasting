import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error

DATA_DIR = Path("../datasets")

df = pd.read_csv(DATA_DIR / "wind_turbine_train_clean.csv")

features = [
    "Temp_2m", "RelHum_2m", "DP_2m", "WS_10m", "WS_100m", "WG_10m",
    "wind_speed_difference_100m_10m", "wind_speed_100m_squared",
    "wind_speed_100m_cubed", "wind_direction_100m_sin",
    "wind_direction_100m_cos", "hour", "month", "Location"
]

model_df = df.dropna(subset=features + ["Power"]).copy()
X = model_df[features]
y = model_df["Power"]

X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.2, random_state=42
)

models = {
    "LinearRegression": LinearRegression(),
    "RandomForestRegressor": RandomForestRegressor(
        n_estimators=50, random_state=42, n_jobs=-1, max_depth=12
    )
}

results = []

for name, model in models.items():
    model.fit(X_train, y_train)
    pred = model.predict(X_val)

    results.append({
        "model": name,
        "MAE": mean_absolute_error(y_val, pred),
        "RMSE": mean_squared_error(y_val, pred) ** 0.5,
        "R2": r2_score(y_val, pred)
    })

    if name == "RandomForestRegressor":
        feature_importance = pd.DataFrame({
            "feature": features,
            "importance": model.feature_importances_
        }).sort_values("importance", ascending=False)

        feature_importance.to_csv(
            DATA_DIR / "random_forest_feature_importance.csv", index=False
        )

        test = pd.read_csv(DATA_DIR / "wind_turbine_test_clean.csv")
        test["predicted_power"] = model.predict(test[features])
        test.to_csv(DATA_DIR / "wind_turbine_test_with_predictions.csv", index=False)

pd.DataFrame(results).to_csv(DATA_DIR / "model_metrics.csv", index=False)
print(pd.DataFrame(results))