"""VitalDB adapter for the PreOp-XAI protocol (cohort, labels, fixed clinical feature matrix).

Rules mirror the PreOp-XAI protocol v1.1 (docs/protocol.md) as far as VitalDB allows:
  * eligibility: age >= 18 years, valid anesthesia boundary (aneend > anestart), ASA VI excluded;
  * one indexed operation per patient, chosen BEFORE any outcome is looked at. VitalDB times are
    relative to each case's own start, so cross-case chronology is not recoverable; the case with the
    lowest case identifier is indexed (an outcome-independent, deterministic rule);
  * outcome linkage requires admission <= anesthesia start and discharge >= anesthesia end; otherwise
    the label is unknown (not survival) and the patient is excluded from modelling;
  * predictors: age, sex, ASA I-V (missing -> 'unknown'), and the latest preoperative hemoglobin,
    platelets, creatinine, BUN, sodium, potassium and glucose recorded by VitalDB.
"""
import hashlib
import json

import numpy as np
import pandas as pd

LAB_MAP = {"hemoglobin": "preop_hb", "platelets": "preop_plt", "creatinine": "preop_cr",
           "bun": "preop_bun", "sodium": "preop_na", "potassium": "preop_k", "glucose": "preop_gluc"}
FEATURES = ("age", "sex", "asa", *LAB_MAP)


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def build(path):
    raw = pd.read_csv(path)
    raw = raw.rename(columns={"case_id": "caseid"})   # the two public mirrors name the first column differently
    flow = {"source_cases": int(len(raw)), "source_patients": int(raw.subjectid.nunique())}
    df = raw.copy()
    df["age_years"] = pd.to_numeric(df.age.astype(str).str.replace(">89", "90", regex=False), errors="coerce")
    flow["age_top_coded_gt89_set_to_90"] = int((raw.age.astype(str) == ">89").sum())
    steps = [("age_under_18_or_missing", ~(df.age_years >= 18)),
             ("invalid_anesthesia_boundary", ~(df.aneend > df.anestart)),
             ("asa_vi", df.asa == 6)]
    keep = pd.Series(True, index=df.index)
    for name, bad in steps:
        flow[f"excluded_{name}_cases"] = int((keep & bad).sum())
        keep &= ~bad
    el = df[keep]
    flow["eligible_cases"] = int(len(el))
    flow["eligible_patients"] = int(el.subjectid.nunique())
    idx = el.sort_values("caseid", kind="stable").groupby("subjectid", sort=False).head(1)
    idx = idx.sort_values("subjectid", kind="stable").reset_index(drop=True)
    flow["indexed_patients"] = int(len(idx))
    linked = (idx.adm <= idx.anestart) & (idx.dis >= idx.aneend)
    flow["unknown_outcome_invalid_linkage"] = int((~linked).sum())
    labels = pd.DataFrame({
        "patient_id": idx.subjectid.astype(str).values,
        "operation_id": idx.caseid.astype(str).values,
        "mortality": np.where(linked, idx.death_inhosp, np.nan),
        "icu": np.where(linked, (idx.icu_days >= 1).astype(float), np.nan),
    })
    X = pd.DataFrame({"age": idx.age_years.astype(float),
                      "sex": idx.sex.astype(object),
                      "asa": idx.asa.map(lambda v: "unknown" if pd.isna(v) else str(int(v))).astype(object)})
    # Missing ASA is encoded as the explicit category 'unknown' here, exactly as
    # preop_xai.preprocessing.feature_matrix does at training time. (The repository's explain.py
    # transforms the raw frame without feature_matrix, so a NaN would otherwise be encoded
    # differently at explanation time and break SHAP additivity.)
    for concept, col in LAB_MAP.items():
        X[concept] = idx[col].astype(float)
    X = X[list(FEATURES)]
    known = labels.mortality.notna()
    flow["modelled_patients"] = int(known.sum())
    flow["mortality_events"] = int(labels.mortality[known].sum())
    flow["icu_events"] = int(labels.icu[known].sum())
    return X, labels, flow, idx


def assign_splits(labels, seed=2026):
    """Verbatim logic of preop_xai.splits.assign_splits (70/15/15, stratified on known mortality;
    unknown labels by seeded largest-remainder allocation)."""
    from sklearn.model_selection import train_test_split
    result = labels.copy().sort_values(["patient_id", "operation_id"], kind="stable").reset_index(drop=True)
    known = result.index[result["mortality"].notna()]
    train, held = train_test_split(known, test_size=0.30, random_state=seed,
                                   stratify=result.loc[known, "mortality"].astype(int))
    validation, test = train_test_split(held, test_size=0.5, random_state=seed,
                                        stratify=result.loc[held, "mortality"].astype(int))
    result["partition"] = pd.Series(index=result.index, dtype="string")
    for partition, indices in (("train", train), ("validation", validation), ("test", test)):
        if result.loc[indices, "mortality"].nunique() != 2:
            raise ValueError("Each partition needs both mortality classes.")
        result.loc[indices, "partition"] = partition
    unknown = result.index[result["mortality"].isna()].to_numpy(copy=True)
    rng = np.random.default_rng(seed)
    rng.shuffle(unknown)
    sizes = np.array([0.70, 0.15, 0.15]) * len(unknown)
    allocation = np.floor(sizes).astype(int)
    order = np.argsort(-(sizes - allocation), kind="stable")
    allocation[order[: len(unknown) - allocation.sum()]] += 1
    offset = 0
    for partition, size in zip(("train", "validation", "test"), allocation):
        result.loc[unknown[offset: offset + size], "partition"] = partition
        offset += size
    return result


def characteristics(X, labels, endpoint):
    """Cohort description by outcome among modelled patients."""
    m = labels[endpoint].notna().values
    Xm, y = X[m], labels[endpoint][m].astype(int).values
    out = {}
    for name, grp in (("all", np.ones(len(y), bool)), ("event", y == 1), ("no_event", y == 0)):
        g = Xm[grp]
        d = {"n": int(grp.sum()), "age_median": float(g.age.median()),
             "age_q1": float(g.age.quantile(.25)), "age_q3": float(g.age.quantile(.75)),
             "female_pct": float(100 * (g.sex == "F").mean()),
             "asa_pct": {k: float(100 * (g.asa == k).mean()) for k in ("1", "2", "3", "4")},
             "asa_missing_pct": float(100 * (g.asa == "unknown").mean())}
        for lab in LAB_MAP:
            d[lab] = {"median": float(g[lab].median()), "q1": float(g[lab].quantile(.25)),
                      "q3": float(g[lab].quantile(.75)), "missing_pct": float(100 * g[lab].isna().mean())}
        out[name] = d
    return out


if __name__ == "__main__":
    import sys
    X, labels, flow, idx = build(sys.argv[1])
    print(json.dumps(flow, indent=1))
