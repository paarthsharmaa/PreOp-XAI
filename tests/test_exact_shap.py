"""Exact SHAP agrees with brute-force Shapley enumeration and is additive."""

import subprocess
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
import xgboost as xgb

from pipeline.config import ROOT
from preopxai.exact_shap import brute_force_interventional, linear_shap, tree_shap_interventional


def _tree_case() -> tuple[xgb.XGBClassifier, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, 5))
    X[rng.random(X.shape) < 0.05] = np.nan
    signal = np.nan_to_num(X[:, 0]) + np.nan_to_num(X[:, 1]) * np.nan_to_num(X[:, 2])
    y = (signal + rng.normal(size=400) > 0.5).astype(int)
    model = xgb.XGBClassifier(n_estimators=40, max_depth=3, learning_rate=0.1, min_child_weight=5,
                              tree_method="hist", random_state=1, n_jobs=1).fit(X, y)
    return model, X[:6], X[rng.choice(400, 12, replace=False)]


def test_tree_shap_matches_brute_force() -> None:
    model, explained, background = _tree_case()
    phi, _ = tree_shap_interventional(model, explained, background)

    def margin(rows: np.ndarray) -> np.ndarray:
        return model.predict(rows, output_margin=True)

    for index, row in enumerate(explained):
        exact = brute_force_interventional(margin, row, background.copy())
        assert np.max(np.abs(exact - phi[index])) < 1e-5


def test_tree_shap_is_additive() -> None:
    model, explained, background = _tree_case()
    phi, base = tree_shap_interventional(model, explained, background)
    margin = model.predict(explained, output_margin=True)
    assert np.max(np.abs(base + phi.sum(axis=1) - margin)) < 1e-5


def test_linear_shap_matches_brute_force_and_is_additive() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(300, 6))
    y = (X[:, 0] - X[:, 3] + rng.normal(size=300) > 0).astype(int)
    model = LogisticRegression().fit(X, y)
    background, explained = X[:20], X[20:26]
    phi, base = linear_shap(model.coef_, model.intercept_[0], explained, background)
    for index, row in enumerate(explained):
        exact = brute_force_interventional(model.decision_function, row, background.copy())
        assert np.max(np.abs(exact - phi[index])) < 1e-9
    assert np.max(np.abs(base + phi.sum(axis=1) - model.decision_function(explained))) < 1e-9


def test_full_selftest_passes() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "tests/shap_selftest.py")],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "PASS" in result.stdout
