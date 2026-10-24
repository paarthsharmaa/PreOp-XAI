"""Exact SHAP values on the raw log-odds scale for the two model families used in PreOp-XAI.

linear_shap: interventional (independent-masker) SHAP for a linear logit,
    phi_ij = w_j * (x_ij - mean_b z_bj),  base = b0 + w . mean_b z_b.

tree_shap_interventional: interventional TreeSHAP (Lundberg et al., Nat. Mach. Intell. 2020) for an
    XGBoost binary:logistic booster. For one explained row x and one background row z, the value of a
    coalition S is the margin of the hybrid row (x on S, z elsewhere). Each leaf contributes the
    product game  v_leaf * prod_{f on path} 1[(f in S and x satisfies f's conditions) or
    (f not in S and z satisfies them)].  With A = features only x satisfies and B = features only z
    satisfies (and no feature that neither satisfies), the exact Shapley values of that game are
        f in A: +v (|A|-1)! |B|! / (|A|+|B|)!,     f in B: -v |A)! (|B|-1)! / (|A|+|B|)!,
    and zero otherwise. Averaging over the background rows gives the interventional SHAP values, which
    sum to margin(x) - mean_b margin(z_b). XGBoost compares float32 inputs with float32 split values
    (go to 'yes' iff x < split, NaN follows 'missing'); the same arithmetic is used here.
"""
import json
from math import factorial

import numpy as np


def linear_shap(w, b0, X, background):
    w = np.asarray(w, float).reshape(-1)
    mu = np.asarray(background, float).mean(axis=0)
    phi = (np.asarray(X, float) - mu) * w
    return phi, float(b0 + w @ mu)


def _booster(model):
    return model.get_booster() if hasattr(model, "get_booster") else model


def _leaves(node, path, out):
    if "leaf" in node:
        out.append((float(node["leaf"]), list(path)))
        return
    f = int(str(node["split"]).lstrip("f")) if str(node["split"]).lstrip("f").isdigit() else node["split"]
    c = np.float32(node["split_condition"])
    children = {ch["nodeid"]: ch for ch in node["children"]}
    yes, no, miss = node["yes"], node["no"], node["missing"]
    _leaves(children[yes], path + [(f, c, True, miss == yes)], out)
    _leaves(children[no], path + [(f, c, False, miss == no)], out)


def parse_trees(model):
    booster = _booster(model)
    names = booster.feature_names
    index = {n: i for i, n in enumerate(names)} if names else None
    trees = []
    for dump in booster.get_dump(dump_format="json"):
        leaves = []
        _leaves(json.loads(dump), [], leaves)
        if index is not None:
            leaves = [(v, [(index[f] if not isinstance(f, (int, np.integer)) else f, c, l, m)
                           for f, c, l, m in p]) for v, p in leaves]
        trees.append(leaves)
    return trees


def _satisfies(X32, conditions):
    """Boolean (rows,) : row satisfies every split condition in `conditions` (same feature)."""
    ok = np.ones(len(X32), dtype=bool)
    for f, c, left, miss in conditions:
        x = X32[:, f]
        nan = np.isnan(x)
        cmp = (x < c) if left else ~(x < c)
        ok &= np.where(nan, miss, cmp)
    return ok


def tree_shap_interventional(model, X, background, chunk=256):
    X = np.asarray(X, float)
    Z = np.asarray(background, float)
    X32, Z32 = X.astype(np.float32), Z.astype(np.float32)
    trees = parse_trees(model)
    n, p = X.shape
    m = len(Z)
    phi = np.zeros((n, p))
    fact = [factorial(k) for k in range(64)]
    for leaves in trees:
        for v, path in leaves:
            feats = sorted({f for f, *_ in path})
            K = len(feats)
            if K == 0:          # root-only tree: a constant, absorbed by the base value
                continue
            a = np.column_stack([_satisfies(X32, [c for c in path if c[0] == f]) for f in feats])
            bz = np.column_stack([_satisfies(Z32, [c for c in path if c[0] == f]) for f in feats])
            # The leaf's game depends on a row only through its satisfaction pattern (2^K possibilities), so the
            # contribution is computed once per (explained pattern, background pattern) pair and scattered.
            weights = 1 << np.arange(K)
            a_code = a.astype(np.int64) @ weights
            b_code = bz.astype(np.int64) @ weights
            b_count = np.bincount(b_code, minlength=1 << K) / m
            table = np.zeros((1 << K, K))
            for pa in np.unique(a_code):
                abits = np.array([(pa >> k) & 1 for k in range(K)], bool)
                for pb in np.flatnonzero(b_count):
                    bbits = np.array([(pb >> k) & 1 for k in range(K)], bool)
                    if (~abits & ~bbits).any():
                        continue                      # a feature no hybrid can satisfy: leaf unreachable
                    A, B = abits & ~bbits, ~abits & bbits
                    ka, kb = int(A.sum()), int(B.sum())
                    if ka + kb == 0:
                        continue
                    if ka:
                        table[pa, A] += b_count[pb] * v * fact[ka - 1] * fact[kb] / fact[ka + kb]
                    if kb:
                        table[pa, B] -= b_count[pb] * v * fact[ka] * fact[kb - 1] / fact[ka + kb]
            phi[:, feats] += table[a_code]
    margin = np.asarray(_predict_margin(model, X), float)
    base_rows = np.asarray(_predict_margin(model, Z), float)
    base = float(base_rows.mean())
    if not np.allclose(base + phi.sum(1), margin, atol=1e-4, rtol=1e-5):
        worst = float(np.max(np.abs(base + phi.sum(1) - margin)))
        raise ValueError(f"Interventional TreeSHAP additivity failed (max error {worst:.2e}).")
    return phi, base


def _predict_margin(model, X):
    if hasattr(model, "get_booster"):
        return model.predict(X, output_margin=True)
    import xgboost as xgb
    return model.predict(xgb.DMatrix(X), output_margin=True)


def brute_force_interventional(margin_fn, x, Z):
    """Exact interventional Shapley values by enumerating all 2^p coalitions (small p only)."""
    from itertools import combinations
    p = len(x)
    vals = {}
    for k in range(p + 1):
        for S in combinations(range(p), k):
            H = Z.copy()
            H[:, list(S)] = x[list(S)]
            vals[frozenset(S)] = float(np.mean(margin_fn(H)))
    phi = np.zeros(p)
    for j in range(p):
        others = [i for i in range(p) if i != j]
        for k in range(p):
            for S in combinations(others, k):
                w = factorial(k) * factorial(p - k - 1) / factorial(p)
                phi[j] += w * (vals[frozenset(S) | {j}] - vals[frozenset(S)])
    return phi
