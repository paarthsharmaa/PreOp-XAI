"""Select preoperative labs (PreOp-XAI rules, collection-time proxy) and write the de-identified analysis table.
Lab identity is fixed by LOINC code and unit (reviewed map below). Output keeps no identifiers or dates."""
import json, os, sys
import numpy as np, pandas as pd
LAG = float(sys.argv[1]) if len(sys.argv) > 1 else 24.0
SUFFIX = "" if LAG == 24 else f"_lag{int(LAG)}h"
W = os.path.expanduser("~/work"); OUT = os.path.expanduser("~/mnt/Downloads/MOVER/preopxai")
MAP = {"hemoglobin": ({"718-7", "30350-3", "14775-1"}, {"G/DL", "g/dL"}, 0.0, 30.0),
       "platelets": ({"26515-7", "778-1"}, {"THOUS/MCL", "THOUS/ CU MM"}, 0.0, 3000.0),
       "creatinine": ({"2160-0", "38483-4"}, {"mg/dL", "MG/DL"}, 0.0, 30.0),
       "bun": ({"3094-0", "12962-7"}, {"mg/dL", "MG/DL"}, 0.0, 300.0),
       "sodium": ({"2951-2", "2947-0"}, {"mmol/L", "MMOL/L"}, 70.0, 200.0),
       "potassium": ({"2823-3", "6298-4"}, {"mmol/L", "MMOL/L"}, 1.0, 12.0),
       "glucose": ({"2345-7", "2339-0"}, {"mg/dL", "MG/DL"}, 0.0, 2000.0)}
NAME = {"hemoglobin": "Hemoglobin", "platelets": "Platelets", "creatinine": "Creatinine", "bun": "Urea nitrogen",
        "sodium": "Sodium", "potassium": "Potassium", "glucose": "Glucose"}
co = pd.read_pickle(f"{W}/cohort.pkl")
co = co[co.mortality.notna()].copy()
c = pd.read_pickle(f"{W}/candidates.pkl")
c = c[c.LOG_ID.isin(set(co.operation_id))].merge(co[["operation_id", "t0"]], left_on="LOG_ID", right_on="operation_id")
c["concept"] = None
for k, (codes, units, lo, hi) in MAP.items():
    c.loc[(c["Lab Name"] == NAME[k]) & c["Lab Code"].isin(codes) & c["Measurement Units"].isin(units), "concept"] = k
stats = {"candidate_rows": int(len(c)), "unmapped_code_or_unit": int(c.concept.isna().sum())}
c = c[c.concept.notna()].copy()
c["ct"] = pd.to_datetime(c["Collection Datetime"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
c["v"] = pd.to_numeric(c["Observation Value"], errors="coerce")
h = (c.ct - c.t0).dt.total_seconds() / 3600
reason = np.select([c.ct.isna(), h < -720, h > 0, h > -LAG, c.v.isna()],
                   ["missing_time", "before_lookback", "future_collection", "proxy_lag", "nonnumeric"], "eligible")
lo = c.concept.map({k: v[2] for k, v in MAP.items()}); hi = c.concept.map({k: v[3] for k, v in MAP.items()})
reason = np.where((reason == "eligible") & ~c.v.between(lo, hi), "implausible", reason)
c["reason"] = reason
stats["reasons"] = c.reason.value_counts().to_dict()
e = c[c.reason == "eligible"]
latest = e.groupby(["operation_id", "concept"]).ct.transform("max")
e = e[e.ct == latest]
g = e.groupby(["operation_id", "concept"]).v.agg(["nunique", "first"])
stats["conflicting_latest"] = int((g["nunique"] > 1).sum())
g = g[g["nunique"] == 1]["first"].unstack()
tab = co.sort_values("patient_id", kind="stable").reset_index(drop=True)
tab = tab.join(g, on="operation_id")
out = pd.DataFrame({"age": tab.age.astype(float),
                    "sex": tab.sex.map({"Male": "M", "Female": "F"}).fillna("unknown"),
                    "asa": tab.asa.fillna("unknown").astype(str)})
for k in MAP:
    out[k] = tab[k].astype(float) if k in tab else np.nan
out["mortality"] = tab.mortality.astype(int)
out["icu"] = tab.icu_flag.map({"Yes": 1, "No": 0}).astype(int)
stats.update(modelled=len(out), deaths=int(out.mortality.sum()), icu=int(out.icu.sum()),
             missing_pct={k: round(100 * out[k].isna().mean(), 2) for k in MAP},
             asa=out.asa.value_counts().to_dict(), sex=out.sex.value_counts().to_dict(),
             age_min=float(out.age.min()), age_max=float(out.age.max()))
out.to_csv(f"{OUT}/mover_analysis{SUFFIX}.csv", index=False)
json.dump(stats, open(f"{OUT}/mover_feature_stats{SUFFIX}.json", "w"), indent=1)
print(json.dumps(stats, indent=1))
