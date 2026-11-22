"""Score and explain one patient with the saved study models and the project's SHAP code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd
from scipy.special import logit

from app.api.schemas import LABELS, EndpointPrediction, ModelPrediction, PatientInput, PredictionResponse
from pipeline.model_artifacts import ENDPOINTS, EndpointArtifacts, artifacts_dir, load_endpoint
from preopxai import study  # noqa: F401  # Puts the exact-SHAP shim on sys.path before explain is imported.
from preopxai.calibration import probabilities
from preopxai.exact_shap import _satisfies, parse_trees  # pyright: ignore[reportPrivateUsage]
from preopxai.explain import _calibration_parameters, _explain_raw  # pyright: ignore[reportPrivateUsage]
from preopxai.preprocessing import FEATURES, feature_matrix

SCALE: Final = "SHAP values are additive on the raw log-odds scale, not on the probability scale."
NOTICE: Final = "Research prototype, not for clinical use."


class TreeMargin:
    """Float64 sum of the booster's leaves, so that SHAP additivity is not limited by float32 accumulation.

    XGBoost's own margin is float32 and is still used for probabilities, so they match the study.
    """

    def __init__(self, model) -> None:
        booster = model.get_booster()
        config = json.loads(booster.save_config())
        self.intercept = float(logit(float(config["learner"]["learner_model_param"]["base_score"])))
        self.trees = parse_trees(model)

    def __call__(self, X: np.ndarray) -> np.ndarray:
        rows = np.asarray(X, dtype=float).astype(np.float32)
        total = np.full(len(rows), self.intercept)
        for leaves in self.trees:
            for value, path in leaves:
                total[_satisfies(rows, path)] += value
        return total


class Engine:
    """Holds the loaded artifacts. Background rows never leave this object."""

    def __init__(self, root: Path | None = None) -> None:
        directory = root or artifacts_dir()
        missing = [name for name in ENDPOINTS if not (directory / name / "metadata.json").is_file()]
        if missing:
            raise RuntimeError(f"Missing model artifacts for {missing}. Run `make export-models` first.")
        self._saved: dict[str, EndpointArtifacts] = {name: load_endpoint(directory / name) for name in ENDPOINTS}
        self._margins = {name: TreeMargin(saved.bundles["xgboost"].pipeline.named_steps["model"])
                         for name, saved in self._saved.items()}

    def _explain(self, endpoint: str, model: str, frame: pd.DataFrame) -> ModelPrediction:
        saved = self._saved[endpoint]
        bundle = saved.bundles[model]
        data = _explain_raw(bundle, saved.background, frame)
        values = data["values"][0]
        native = float(data["scores"][0])
        log_odds, base = native, float(data["baseline"][0])
        if model == "xgboost":
            margin = self._margins[endpoint]
            preprocess = bundle.pipeline.named_steps["preprocess"]
            log_odds = float(margin(data["transformed"])[0])
            base = float(margin(np.asarray(preprocess.transform(saved.background), dtype=float)).mean())
        a, b = _calibration_parameters(bundle)
        probability = float(probabilities(bundle, frame)[0])
        threshold = float(bundle.threshold)  # pyright: ignore[reportArgumentType]
        groups = np.asarray(data["groups"])
        shap = [{"concept": concept, "label": LABELS[concept],
                 "contribution": float(values[groups == concept].sum()),
                 "value_part": float(values[(groups == concept) & ~data["missing"]].sum()),
                 "missingness_part": float(values[(groups == concept) & data["missing"]].sum())}
                for concept in FEATURES]
        return ModelPrediction.model_validate({
            "log_odds": log_odds, "native_margin": native, "base_value": base, "calibrated_log_odds": a + b * native,
            "calibrated_probability": probability, "threshold": threshold, "above_threshold": probability >= threshold,
            "recalibration_intercept": a, "recalibration_slope": b, "shap": shap})

    def predict(self, patient: PatientInput) -> PredictionResponse:
        """Return both models for both endpoints."""
        row = patient.model_dump()
        row["asa"] = str(row["asa"])
        frame = pd.DataFrame([{name: row[name] if row[name] is not None else np.nan for name in FEATURES}])
        frame = feature_matrix(frame)
        result = {endpoint: EndpointPrediction(lr=self._explain(endpoint, "lr", frame),
                                               xgboost=self._explain(endpoint, "xgboost", frame))
                  for endpoint in ENDPOINTS}
        return PredictionResponse(scale=SCALE, notice=NOTICE, mortality=result["mortality"], icu=result["icu"])
