"""Aggregate the repeated-split results into results/summary.json (every number quoted from the repeats)."""
import collections
import glob
import json

import sys

import numpy as np

N_SPLITS = 100                      # prespecified number of repeated splits (seeds 1..100)
PARTIAL = "--partial" in sys.argv

out = {}
for e in ("mortality", "icu"):
    R = [json.load(open(f)) for f in sorted(glob.glob(f"results/repeats_{e}/seed*.json"))]
    R = [r for r in R if 1 <= r["seed"] <= N_SPLITS]
    assert len(R) == N_SPLITS or PARTIAL, (e, len(R))
    s = {"splits": len(R), "seeds": [R[0]["seed"], R[-1]["seed"]]}
    ev = np.array([r["test_events"] for r in R]); vev = np.array([r["partition_events"]["validation"] for r in R])
    s["test_events_median"], s["test_events_min"], s["test_events_max"] = float(np.median(ev)), int(ev.min()), int(ev.max())
    s["validation_events_min"], s["validation_events_max"] = int(vev.min()), int(vev.max())

    def q(v):
        v = np.asarray([x for x in v if x is not None], float)
        return {"n": int(len(v)), "median": float(np.median(v)), "q1": float(np.quantile(v, .25)),
                "q3": float(np.quantile(v, .75)), "p2_5": float(np.quantile(v, .025)), "p97_5": float(np.quantile(v, .975)),
                "min": float(v.min()), "max": float(v.max()), "mean": float(v.mean())}
    for m in ("lr", "xgboost"):
        T = [r["test"][m] for r in R]
        S = [r["selection"][m] for r in R]
        d = {"auroc": q([t["raw"]["auroc"] for t in T]), "ap": q([t["raw"]["average_precision"] for t in T]),
             "brier_raw": q([t["raw"]["brier"] for t in T]),
             "brier_cal": q([t["calibrated"]["brier"] if t["calibrated"] else None for t in T]),
             "val_recal_slope": q([x["calibration_slope"] for x in S]),
             "val_recal_slope_nonpositive": int(sum(1 for x in S if x["calibration_slope"] is not None and x["calibration_slope"] <= 0)),
             "calibration_status": dict(collections.Counter(x["calibration_status"] for x in S)),
             "test_cal_slope_raw": q([t["raw_calibration"]["joint_slope"] for t in T]),
             "test_cal_slope_cal": q([t["calibration"]["joint_slope"] if t["calibration"] else None for t in T]),
             "test_citl_raw": q([t["raw_calibration"]["offset_intercept"] for t in T]),
             "test_citl_cal": q([t["calibration"]["offset_intercept"] if t["calibration"] else None for t in T]),
             "test_sensitivity": q([t["sensitivity"] for t in T]),
             "test_specificity": q([t["specificity"] for t in T]),
             "test_ppv": q([t["ppv"] for t in T]),
             "share_sensitivity_ge_0_8": float(np.mean([t["sensitivity"] >= 0.8 for t in T if t["sensitivity"] is not None])),
             "share_brier_cal_below_prevalence": float(np.mean([t["calibrated"]["brier"] < t["training_prevalence_brier"]
                                                                for t in T if t["calibrated"]])),
             "share_brier_raw_below_prevalence": float(np.mean([t["raw"]["brier"] < t["training_prevalence_brier"] for t in T])),
             "selected": dict(collections.Counter(json.dumps(x["parameters"], sort_keys=True) for x in S))}
        s[m] = d
    for metric, key in (("auroc", "auroc"), ("ap", "average_precision")):
        diff = [r["test"]["xgboost"]["raw"][key] - r["test"]["lr"]["raw"][key] for r in R
                if r["test"]["lr"]["raw"][key] is not None]
        s[f"diff_{metric}"] = q(diff) | {"share_xgb_better": float(np.mean(np.asarray(diff) > 0)),
                                        "share_ties": float(np.mean(np.asarray(diff) == 0))}
    dcb = [r["test"]["xgboost"]["calibrated"]["brier"] - r["test"]["lr"]["calibrated"]["brier"] for r in R
           if r["test"]["xgboost"]["calibrated"] and r["test"]["lr"]["calibrated"]]
    s["diff_brier_cal"] = q(dcb) | {"share_xgb_better": float(np.mean(np.asarray(dcb) < 0))}
    out[e] = s
json.dump(out, open("results/summary.json", "w"), indent=1)
for e, s in out.items():
    print(e, s["splits"], "events", s["test_events_min"], s["test_events_max"],
          "AUROC LR", round(s["lr"]["auroc"]["median"], 3), "XGB", round(s["xgboost"]["auroc"]["median"], 3),
          "dAUROC", round(s["diff_auroc"]["median"], 3), [round(s["diff_auroc"]["p2_5"], 3), round(s["diff_auroc"]["p97_5"], 3)],
          "xgb>lr", round(s["diff_auroc"]["share_xgb_better"], 2), "dAP", round(s["diff_ap"]["median"], 3),
          round(s["diff_ap"]["share_xgb_better"], 2))
