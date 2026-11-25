"""Save and reload the fitted primary-split models. Artifacts hold MOVER-derived rows and stay local."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Final

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
import xgboost as xgb

from pipeline.config import ROOT
from preopxai.calibration import calibration_status
from preopxai.preprocessing import FEATURES
from preopxai.train import ModelBundle

ARTIFACTS_VARIABLE: Final = "PREOPXAI_ARTIFACTS"
ENDPOINTS: Final = ("mortality", "icu")
MODELS: Final = ("lr", "xgboost")


@dataclass(frozen=True)
class EndpointArtifacts:
    """Everything needed to score and explain one endpoint exactly as in the study."""

    bundles: dict[str, ModelBundle]
    background: pd.DataFrame
    metadata: dict[str, object]


class SavedBooster:
    """Native XGBoost booster with the small classifier surface the project's scoring and SHAP code call.

    XGBClassifier.save_model fails under the pinned xgboost 2.1.4 and scikit-learn 1.8.
    """

    classes_: Final = np.array([0, 1])

    def __init__(self, booster: xgb.Booster) -> None:
        self._booster = booster

    def get_booster(self) -> xgb.Booster:
        return self._booster

    def predict(self, X: np.ndarray, output_margin: bool = False) -> np.ndarray:
        if not output_margin:
            raise ValueError("Saved boosters only return raw log-odds.")
        return np.asarray(self._booster.inplace_predict(X, predict_type="margin", missing=np.nan))


def artifacts_dir() -> Path:
    """Resolve the artifact folder, which is ignored by git."""
    value = os.environ.get(ARTIFACTS_VARIABLE)
    return Path(value).expanduser().resolve() if value else ROOT / "artifacts"


def _calibration(bundle: ModelBundle) -> dict[str, float]:
    calibrator = bundle.calibrator
    if calibrator is None or calibration_status(bundle) != "fitted" or bundle.threshold is None:
        raise ValueError(f"{bundle.name}: only a fitted recalibration can be exported.")
    return {"a": float(np.asarray(calibrator.intercept_).item()), "b": float(np.asarray(calibrator.coef_).item()),
            "threshold": float(bundle.threshold)}


def save_endpoint(directory: Path, bundles: dict[str, ModelBundle], background: pd.DataFrame,
                  metadata: dict[str, object]) -> None:
    """Write preprocessing, both models, recalibration, threshold and the SHAP background."""
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    models: dict[str, object] = {}
    for name in MODELS:
        bundle = bundles[name]
        joblib.dump(bundle.pipeline.named_steps["preprocess"], directory / f"{name}_preprocess.joblib")
        model = bundle.pipeline.named_steps["model"]
        if name == "lr":
            payload = {"coef": np.asarray(model.coef_).tolist(), "intercept": np.asarray(model.intercept_).tolist(),
                       "classes": np.asarray(model.classes_).tolist()}
            _ = (directory / "lr.json").write_text(json.dumps(payload))
        else:
            model.get_booster().save_model(directory / "xgboost.json")
        models[name] = {"parameters": bundle.parameters, "cv_score": bundle.cv_score,
                        "training_prevalence": bundle.training_prevalence, **_calibration(bundle)}
    background.to_csv(directory / "background.csv", index=False)
    _ = (directory / "metadata.json").write_text(json.dumps({**metadata, "models": models}, indent=1))


def _load_model(directory: Path, name: str) -> LogisticRegression | SavedBooster:
    if name == "xgboost":
        booster = xgb.Booster()
        booster.load_model(directory / "xgboost.json")
        return SavedBooster(booster)
    payload = json.loads((directory / "lr.json").read_text())
    model = LogisticRegression()
    model.coef_ = np.asarray(payload["coef"], dtype=float)
    model.intercept_ = np.asarray(payload["intercept"], dtype=float)
    model.classes_ = np.asarray(payload["classes"])
    return model


def load_endpoint(directory: Path) -> EndpointArtifacts:
    """Rebuild project ModelBundles from disk, with no reference to the fitting session."""
    metadata = json.loads((directory / "metadata.json").read_text())
    bundles: dict[str, ModelBundle] = {}
    for name in MODELS:
        saved = metadata["models"][name]
        pipeline = Pipeline([("preprocess", joblib.load(directory / f"{name}_preprocess.joblib")),
                             ("model", _load_model(directory, name))])
        calibrator = LogisticRegression()
        calibrator.coef_ = np.array([[saved["b"]]], dtype=float)
        calibrator.intercept_ = np.array([saved["a"]], dtype=float)
        calibrator.classes_ = np.array([0, 1])
        bundles[name] = ModelBundle(pipeline=pipeline, name=name, parameters=saved["parameters"],
                                    cv_score=saved["cv_score"], training_prevalence=saved["training_prevalence"],
                                    calibrator=calibrator, threshold=saved["threshold"],
                                    diagnostics={"calibration_status": "fitted"})
    background = pd.read_csv(directory / "background.csv", dtype={"sex": str, "asa": str}, keep_default_na=True)
    if tuple(background.columns) != tuple(FEATURES):
        raise ValueError("Saved SHAP background has unexpected columns.")
    return EndpointArtifacts(bundles=bundles, background=background, metadata=metadata)
