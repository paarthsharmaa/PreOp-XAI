"""Feasibility of the protocol's optional respiratory endpoint in MOVER EPIC, using the repository's rule semantics
(preop_xai.labels.build_labels: one consistent reviewed state per operation; mixed states are 'contradictory').
Candidate reviewed rules: AQI post-op complication value 'Respiratory' -> 1, AQI value 'None' -> 0 (any context).
Aggregate counts only."""
import json, os, sys
import pandas as pd
RAW = sys.argv[1]; W = os.path.expanduser("~/work"); OUT = os.path.expanduser("~/mnt/Downloads/MOVER/preopxai")
c = pd.read_csv(f"{RAW}/patient_post_op_complications.csv", dtype=str, keep_default_na=False)
co = pd.read_pickle(f"{W}/cohort.pkl")
a = c[c.Element_abbr == "AN Post-op Complications"]
state = a.SMRTDTA_ELEM_VALUE.map({"Respiratory": 1, "None": 0})
a = a.assign(state=state)
out = {"complication_rows": len(c), "aqi_rows": len(a)}
for name, ops in (("indexed", co), ("modelled", co[co.mortality.notna()])):
    keys = set(zip(ops.patient_id, ops.operation_id))
    m = a[[k in keys for k in zip(a.MRN, a.LOG_ID)]]
    g = m.groupby(["MRN", "LOG_ID"]).state.agg(lambda s: tuple(sorted(set(s.dropna().astype(int)))))
    out[name] = {"operations": len(ops), "with_aqi_documentation": int(len(g)),
                 "negative_only": int((g == (0,)).sum()), "positive_only": int((g == (1,)).sum()),
                 "contradictory": int((g == (0, 1)).sum()), "no_reviewed_state": int((g == ()).sum()),
                 "any_positive": int(g.map(lambda t: 1 in t).sum())}
json.dump(out, open(f"{OUT}/mover_respiratory_feasibility.json", "w"), indent=1)
print(json.dumps(out, indent=1))
