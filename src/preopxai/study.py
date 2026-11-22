"""PreOp-XAI protocol on the de-identified MOVER EPIC analysis table (one endpoint, one split seed), with external
validation of the frozen models on VitalDB. Uses the repository's modules unchanged (preop_xai.train / calibration /
evaluate / explain / stability); the SHAP back end is the exact implementation in exact_shap.py (via shapshim).

Modes: full (1,000 bootstraps, SHAP, 10 stability refits, VitalDB external validation, figure data),
       perf (1,000 bootstraps only), light (point estimates only; used for the repeated splits).
"""
import hashlib
import json
import sys
import time
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / "shapshim")]
import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd

from cohort_vitaldb import assign_splits, build as build_vitaldb
from preop_xai.calibration import calibrate_models, calibration_status, probabilities, raw_scores
from preop_xai.evaluate import evaluate_models
from preop_xai.train import fit_models

LABS = ["hemoglobin", "platelets", "creatinine", "bun", "sodium", "potassium", "glucose"]
FEATURES = ["age", "sex", "asa"] + LABS


def load_table(path):
    t = pd.read_csv(path, dtype={"sex": str, "asa": str})
    X = t[FEATURES].copy()
    X["age"] = X["age"].astype(float)
    for k in LABS:
        X[k] = X[k].astype(float)
    ids = [f"{i:06d}" for i in range(len(t))]          # rows are already in patient order; no identifiers kept
    labels = pd.DataFrame({"patient_id": ids, "operation_id": ids,
                           "mortality": t["mortality"].astype(float), "icu": t["icu"].astype(float)})
    return X, labels


def characteristics(X, y):
    out = {}
    for name, grp in (("all", np.ones(len(y), bool)), ("event", y == 1), ("no_event", y == 0)):
        g = X[grp]
        d = {"n": int(grp.sum()), "age_median": float(g.age.median()), "age_q1": float(g.age.quantile(.25)),
             "age_q3": float(g.age.quantile(.75)), "female_pct": float(100 * (g.sex == "F").mean()),
             "asa_pct": {k: float(100 * (g.asa == k).mean()) for k in ("1", "2", "3", "4", "5")},
             "asa_missing_pct": float(100 * (g.asa == "unknown").mean())}
        for lab in LABS:
            d[lab] = {"median": float(g[lab].median()) if g[lab].notna().any() else None,
                      "q1": float(g[lab].quantile(.25)) if g[lab].notna().any() else None,
                      "q3": float(g[lab].quantile(.75)) if g[lab].notna().any() else None,
                      "missing_pct": float(100 * g[lab].isna().mean())}
        out[name] = d
    return out


def deciles(y, p):
    edges = np.quantile(p, np.linspace(0, 1, 11))
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, 9)
    return [{"n": int((idx == i).sum()), "predicted": float(p[idx == i].mean()), "observed": float(y[idx == i].mean())}
            for i in range(10) if (idx == i).any()]


def dependence_bins(Xva, grouped, concepts):
    """Aggregate SHAP dependence: mean grouped SHAP (log-odds) by quintile of each numeric concept, by category
    for sex/ASA, and for 'missing'. Cells with fewer than 11 patients are not reported."""
    out = {}
    for j, c in enumerate(concepts):
        v, s = Xva[c], grouped[:, j]
        cells = []
        if c in ("sex", "asa"):
            for k in sorted(v.dropna().unique()):
                m = (v == k).values
                cells.append({"label": str(k), "n": int(m.sum()), "mean": float(s[m].mean()),
                              "q1": float(np.quantile(s[m], .25)), "q3": float(np.quantile(s[m], .75))})
        else:
            obs = v.notna().values
            if obs.sum():
                edges = np.unique(np.quantile(v[obs], np.linspace(0, 1, 6)))
                idx = np.clip(np.searchsorted(edges, v[obs], side="right") - 1, 0, len(edges) - 2)
                for i in range(len(edges) - 1):
                    m = np.flatnonzero(obs)[idx == i]
                    if len(m):
                        cells.append({"label": f"{edges[i]:.4g}-{edges[i + 1]:.4g}", "lo": float(edges[i]),
                                      "hi": float(edges[i + 1]), "x_median": float(v.iloc[m].median()), "n": int(len(m)),
                                      "mean": float(s[m].mean()), "q1": float(np.quantile(s[m], .25)),
                                      "q3": float(np.quantile(s[m], .75))})
            m = ~obs
            if m.any():
                cells.append({"label": "missing", "n": int(m.sum()), "mean": float(s[m].mean()),
                              "q1": float(np.quantile(s[m], .25)), "q3": float(np.quantile(s[m], .75))})
        out[c] = [x for x in cells if x["n"] >= 11]
    return out


def curves(y, p):
    from sklearn.metrics import precision_recall_curve, roc_curve
    fpr, tpr, _ = roc_curve(y, p)
    pr, rc, _ = precision_recall_curve(y, p)
    return {"fpr": fpr.round(5).tolist(), "tpr": tpr.round(5).tolist(), "precision": pr.round(5).tolist(),
            "recall": rc.round(5).tolist()}


def main(endpoint, seed, out, mode="full", table=None):
    t0 = time.time()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    table = Path(table or HERE / "mover_analysis.csv")
    X, labels = load_table(table)
    splits = assign_splits(labels, seed=seed)
    X = X.loc[labels.sort_values(["patient_id", "operation_id"], kind="stable").index].reset_index(drop=True)
    parts = {}
    for name in ("train", "validation", "test"):
        m = (splits.partition == name).values
        parts[name] = (X[m].reset_index(drop=True), splits.loc[m, endpoint].astype(int).reset_index(drop=True))
    (Xtr, ytr), (Xva, yva), (Xte, yte) = parts["train"], parts["validation"], parts["test"]
    info = {"dataset": "MOVER EPIC", "table": table.name, "table_sha256": hashlib.sha256(table.read_bytes()).hexdigest(), "endpoint": endpoint, "split_seed": seed, "mode": mode,
            "n": int(len(X)), "events": int(labels[endpoint].sum()),
            "partition_n": {k: int(len(v[1])) for k, v in parts.items()},
            "partition_events": {k: int(v[1].sum()) for k, v in parts.items()}}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        bundles = fit_models(Xtr, ytr, seed=2026, folds=5)
        calibrate_models(bundles, Xva, yva)
    info["warnings"] = sorted({str(w.message) for w in caught if not issubclass(w.category, DeprecationWarning)})
    info["selection"] = {k: {"parameters": b.parameters, "cv_average_precision": b.cv_score,
                             "candidates": [[p, s] for p, s in b.candidate_scores], "diagnostics": b.diagnostics,
                             "threshold": b.threshold, "calibration_status": calibration_status(b)}
                         for k, b in bundles.items()}
    info["evaluation"] = evaluate_models(bundles, Xte, yte, out, bootstraps=1 if mode == "light" else 1000, seed=2026)
    if mode == "full":
        from preop_xai.explain import explain_models
        from preop_xai.stability import run_stability
        info["explain"] = explain_models(bundles, Xtr, Xva, yva.values, out / "explain", seed=2026)
        info["stability"] = run_stability(bundles, Xtr, ytr.values, Xva, out / "stability", refits=10, seed=2026)
        info["characteristics"] = characteristics(X, labels[endpoint].to_numpy().astype(int))
        lr = bundles["lr"].pipeline
        names = list(lr.named_steps["preprocess"].get_feature_names_out())
        info["lr_coefficients"] = dict(zip(names, lr.named_steps["model"].coef_[0].tolist()))
        # ---- external validation of the frozen, MOVER-recalibrated models on VitalDB
        Xv, lv, flow_v, _ = build_vitaldb(HERE / "data" / "vitaldb_clinical_data.csv")
        kv = lv[endpoint].notna().values
        Xv, yv = Xv[kv].reset_index(drop=True), lv.loc[kv, endpoint].astype(int).reset_index(drop=True)
        info["external_vitaldb"] = evaluate_models(bundles, Xv, yv, out / "external_vitaldb", bootstraps=1000, seed=2026)
        info["external_vitaldb"]["flow"] = flow_v
        info["external_vitaldb"]["characteristics"] = characteristics(Xv, yv.values)
        # ---- aggregate figure data (curves, decile calibration, refit SHAP importances); no patient-level values
        fig = {"test": {}, "external": {}, "shap_refit_importance": {}, "dependence": {}}
        for m, b in bundles.items():
            for key, (Xs, ys) in (("test", (Xte, yte)), ("external", (Xv, yv))):
                y_ = ys.to_numpy()
                raw = probabilities(b, Xs, calibrated=False)
                cal = probabilities(b, Xs, allow_invalid=True)
                fig[key][m] = {"curves": curves(y_, raw), "deciles_raw": deciles(y_, raw), "deciles_cal": deciles(y_, cal)}
            gc = np.load(out / "stability" / "private" / f"{m}_stability.npz")["grouped_contributions"]
            fig["shap_refit_importance"][m] = np.abs(gc).mean(axis=1).tolist()   # refits x concepts
            ex = np.load(out / "explain" / "private" / f"{m}_explanations.npz", allow_pickle=True)
            fig["dependence"][m] = dependence_bins(Xva, ex["grouped_raw"], FEATURES)
        info["figure_data"] = fig
    info["runtime_s"] = round(time.time() - t0, 1)
    (out / "study.json").write_text(json.dumps(info, indent=1, default=str))
    return info


if __name__ == "__main__":
    a = sys.argv[1:]
    r = main(a[0], int(a[1]), a[2], mode=a[3] if len(a) > 3 else "full", table=a[4] if len(a) > 4 else None)
    ev = r["evaluation"]["models"]
    print(r["endpoint"], r["split_seed"], r["partition_events"], f"{r['runtime_s']}s",
          {k: round(v["raw"]["auroc"], 3) for k, v in ev.items()})
