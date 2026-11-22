"""Minimal, exact stand-in for the parts of the `shap` API that PreOp-XAI's explain.py and
stability.py call (LinearExplainer with an Independent masker, interventional TreeExplainer on
raw log-odds, Explanation, plots.beeswarm). The `shap` package could not be installed in the study
environment (no package-index access), so the values are computed by `exact_shap`:
  * linear model + independent masker: phi_j = w_j (x_j - mean_b z_j)  (exact interventional SHAP)
  * tree ensemble, interventional: exact baseline-Shapley per background row, averaged over the
    background (Lundberg et al. 2020, interventional TreeSHAP), from the XGBoost JSON tree dump.
Both are verified against brute-force Shapley enumeration in tests/test_exact_shap.py."""
import numpy as np
from . import maskers, plots          # noqa: F401
from exact_shap import linear_shap, tree_shap_interventional

__version__ = "exact-in-house-1.0 (shap API subset)"


class Explanation:
    def __init__(self, values, base_values=None, data=None, feature_names=None):
        self.values = np.asarray(values, dtype=float)
        self.base_values = base_values
        self.data = data
        self.feature_names = feature_names


class LinearExplainer:
    def __init__(self, model, masker):
        self.w = np.asarray(model.coef_, dtype=float).reshape(-1)
        self.b = float(np.asarray(model.intercept_).reshape(-1)[0])
        self.bg = np.asarray(masker.data, dtype=float)

    def __call__(self, X):
        phi, base = linear_shap(self.w, self.b, np.asarray(X, dtype=float), self.bg)
        return Explanation(phi, np.full(len(phi), base), X)


class TreeExplainer:
    def __init__(self, model, data=None, feature_perturbation="interventional", model_output="raw"):
        if feature_perturbation != "interventional" or model_output != "raw":
            raise NotImplementedError("Only interventional raw-margin explanations are implemented.")
        self.model = model
        self.bg = np.asarray(data, dtype=float)

    def __call__(self, X):
        phi, base = tree_shap_interventional(self.model, np.asarray(X, dtype=float), self.bg)
        return Explanation(phi, np.full(len(phi), base), X)
