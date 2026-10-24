"""Verify exact_shap against brute-force Shapley enumeration (run: python tests/test_exact_shap.py)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from exact_shap import tree_shap_interventional, linear_shap, brute_force_interventional

rng = np.random.default_rng(0)
worst = 0.0
for trial, (depth, trees, p) in enumerate([(2, 50, 5), (3, 120, 6), (3, 300, 7)]):
    X = rng.normal(size=(800, p)); X[rng.random(X.shape) < 0.05] = np.nan
    y = (np.nan_to_num(X[:, 0]) + np.nan_to_num(X[:, 1]) * np.nan_to_num(X[:, 2]) + rng.normal(size=800) > 0.5).astype(int)
    m = xgb.XGBClassifier(n_estimators=trees, max_depth=depth, learning_rate=0.1, min_child_weight=5,
                          reg_lambda=5.0, tree_method="hist", random_state=1, n_jobs=1).fit(X, y)
    Z = X[rng.choice(800, 16, replace=False)]
    E = X[:12]
    phi, base = tree_shap_interventional(m, E, Z)
    f = lambda H: m.predict(H, output_margin=True)
    for i in range(len(E)):
        bf = brute_force_interventional(f, E[i], Z.copy())
        worst = max(worst, float(np.max(np.abs(bf - phi[i]))))
    print(f"tree trial {trial}: depth {depth}, {trees} trees, {p} features: max |exact - brute force| = {worst:.2e}")
X = rng.normal(size=(500, 6)); y = (X[:, 0] - X[:, 3] + rng.normal(size=500) > 0).astype(int)
lr = LogisticRegression().fit(X, y)
Z = X[:20]; E = X[20:30]
phi, base = linear_shap(lr.coef_, lr.intercept_[0], E, Z)
wl = max(float(np.max(np.abs(brute_force_interventional(lr.decision_function, E[i], Z.copy()) - phi[i]))) for i in range(10))
print(f"linear: max |exact - brute force| = {wl:.2e}; additivity error {np.max(np.abs(base + phi.sum(1) - lr.decision_function(E))):.2e}")
assert worst < 1e-5 and wl < 1e-9
print("PASS")
