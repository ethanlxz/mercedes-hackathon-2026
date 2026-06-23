from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor


WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


COLUMN_MAP = {
    "Day": "day",
    "Driving Distance (km)": "distance_km",
    "Driving Efficiency (Wh/km)": "efficiency_wh_km",
    "Battery Usage (kWh)": "battery_usage_kwh",
    "Battery Percentage Start (%)": "battery_start_percent",
    "Battery Percentage End (%)": "battery_end_percent",
    "Charging Behavior (kWh)": "charging_kwh",
    "Day of Week": "day_of_week",
}


@dataclass
class ModelArtifacts:
    version: int
    trip_model: XGBRegressor
    distance_model: XGBRegressor
    usage_model: XGBRegressor
    metrics: dict[str, Any]
    weekday_stats: list[dict[str, Any]]
    battery_capacity_kwh: float
    row_count: int


class ModelService:
    ARTIFACT_VERSION = 2

    def __init__(self, dataset_path: Path, model_dir: Path) -> None:
        self.dataset_path = dataset_path
        self.model_dir = model_dir
        self.artifact_path = model_dir / "ev_battery_models.joblib"
        self.artifacts: ModelArtifacts | None = None

    @property
    def ready(self) -> bool:
        return self.artifacts is not None

    def load_or_train(self) -> None:
        self.model_dir.mkdir(parents=True, exist_ok=True)
        if self.artifact_path.exists():
            artifacts = joblib.load(self.artifact_path)
            if getattr(artifacts, "version", None) == self.ARTIFACT_VERSION:
                self.artifacts = artifacts
                return

        self.artifacts = self.train()
        joblib.dump(self.artifacts, self.artifact_path)

    def train(self) -> ModelArtifacts:
        df = self._load_dataset()
        df = self._prepare_features(df)

        trip_model, trip_metrics = self._train_trip_model(df)
        distance_model, distance_metrics = self._train_weekday_model(
            df,
            target="distance_km",
        )
        usage_model, usage_metrics = self._train_weekday_model(
            df,
            target="battery_used_percent",
        )

        weekday_stats = (
            df.groupby("day_of_week", observed=True)
            .agg(
                expected_distance_km=("distance_km", "mean"),
                expected_battery_used_percent=("battery_used_percent", "mean"),
                average_efficiency_wh_km=("efficiency_wh_km", "mean"),
            )
            .reindex(WEEKDAYS)
            .reset_index()
            .round(2)
            .to_dict(orient="records")
        )

        return ModelArtifacts(
            version=self.ARTIFACT_VERSION,
            trip_model=trip_model,
            distance_model=distance_model,
            usage_model=usage_model,
            metrics={
                "trip_required_battery_percent": trip_metrics,
                "daily_distance_km": distance_metrics,
                "daily_battery_used_percent": usage_metrics,
            },
            weekday_stats=weekday_stats,
            battery_capacity_kwh=round(float(df["battery_capacity_estimate"].median()), 2),
            row_count=int(len(df)),
        )

    def predict_trip(
        self,
        distance_km: float,
    ) -> dict[str, Any]:
        artifacts = self._require_artifacts()
        features = pd.DataFrame(
            [
                {
                    "distance_km": distance_km,
                }
            ]
        )
        required = float(artifacts.trip_model.predict(features)[0])
        required = float(np.clip(required, 0, 100))

        return {
            "required_battery_percent": round(required, 1),
            "distance_km": round(float(distance_km), 1),
            "message": "Estimated battery required based on your historical driving data.",
        }

    def predict_daily(self, day_of_week: str) -> dict[str, Any]:
        artifacts = self._require_artifacts()
        features = pd.DataFrame([{"day_of_week": day_of_week}])
        encoded = self._encode_weekday(features)
        distance = float(artifacts.distance_model.predict(encoded)[0])
        usage = float(artifacts.usage_model.predict(encoded)[0])
        distance = max(distance, 0)
        usage = float(np.clip(usage, 0, 100))

        return {
            "day_of_week": day_of_week,
            "expected_distance_km": round(distance, 1),
            "expected_battery_used_percent": round(usage, 1),
        }

    def summary(self) -> dict[str, Any]:
        artifacts = self._require_artifacts()
        return {
            "row_count": artifacts.row_count,
            "battery_capacity_kwh": artifacts.battery_capacity_kwh,
            "weekdays": WEEKDAYS,
            "weekday_stats": artifacts.weekday_stats,
            "metrics": artifacts.metrics,
        }

    def _require_artifacts(self) -> ModelArtifacts:
        if self.artifacts is None:
            raise RuntimeError("Models are not ready yet.")
        return self.artifacts

    def _load_dataset(self) -> pd.DataFrame:
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Dataset not found at {self.dataset_path}. Copy the Excel file into data/."
            )

        df = pd.read_excel(self.dataset_path)
        missing = [col for col in COLUMN_MAP if col not in df.columns]
        if missing:
            raise ValueError(f"Dataset is missing expected columns: {missing}")

        df = df.rename(columns=COLUMN_MAP)
        return df[list(COLUMN_MAP.values())].copy()

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df["day_of_week"] = pd.Categorical(df["day_of_week"], categories=WEEKDAYS, ordered=True)
        df["battery_delta_percent"] = (
            df["battery_start_percent"] - df["battery_end_percent"]
        ) + (df["charging_kwh"] / self._estimate_capacity(df) * 100)
        df["battery_delta_percent"] = df["battery_delta_percent"].clip(lower=0.1)

        df["battery_capacity_estimate"] = (
            df["battery_usage_kwh"] / (df["battery_delta_percent"] / 100)
        ).replace([np.inf, -np.inf], np.nan)
        capacity = float(df["battery_capacity_estimate"].median())

        df["required_battery_percent"] = (
            df["distance_km"] * df["efficiency_wh_km"] / 1000 / capacity * 100
        ).clip(lower=0, upper=100)
        df["battery_used_percent"] = (
            df["battery_usage_kwh"] / capacity * 100
        ).clip(lower=0, upper=100)
        df["battery_capacity_estimate"] = df["battery_capacity_estimate"].fillna(capacity)

        return df.dropna(
            subset=[
                "distance_km",
                "efficiency_wh_km",
                "required_battery_percent",
                "battery_used_percent",
                "day_of_week",
            ]
        )

    def _estimate_capacity(self, df: pd.DataFrame) -> float:
        discharge = df["battery_start_percent"] - df["battery_end_percent"]
        valid = (df["charging_kwh"] == 0) & (discharge > 0)
        estimates = df.loc[valid, "battery_usage_kwh"] / (discharge.loc[valid] / 100)
        capacity = float(estimates.replace([np.inf, -np.inf], np.nan).dropna().median())
        return capacity if np.isfinite(capacity) and capacity > 0 else 90.0

    def _base_regressor(self) -> XGBRegressor:
        return XGBRegressor(
            objective="reg:squarederror",
            n_estimators=80,
            max_depth=3,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
        )

    def _train_trip_model(self, df: pd.DataFrame) -> tuple[XGBRegressor, dict[str, float]]:
        features = ["distance_km"]
        target = "required_battery_percent"
        train_x, test_x, train_y, test_y = train_test_split(
            df[features],
            df[target],
            test_size=0.2,
            random_state=42,
        )
        model = self._base_regressor()
        model.fit(train_x, train_y)
        return model, self._metrics(model, test_x, test_y)

    def _train_weekday_model(self, df: pd.DataFrame, target: str) -> tuple[XGBRegressor, dict[str, float]]:
        features = self._encode_weekday(df[["day_of_week"]])
        train_x, test_x, train_y, test_y = train_test_split(
            features,
            df[target],
            test_size=0.2,
            random_state=42,
        )
        model = self._base_regressor()
        model.fit(train_x, train_y)
        return model, self._metrics(model, test_x, test_y)

    def _encode_weekday(self, df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            {
                f"day_{weekday.lower()}": (df["day_of_week"] == weekday).astype(int)
                for weekday in WEEKDAYS
            },
            index=df.index,
        )

    def _metrics(self, model: XGBRegressor, test_x: pd.DataFrame, test_y: pd.Series) -> dict[str, float]:
        predictions = model.predict(test_x)
        return {
            "mae": round(float(mean_absolute_error(test_y, predictions)), 3),
            "r2": round(float(r2_score(test_y, predictions)), 3),
        }
