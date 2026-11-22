"""MOVER EPIC cohort + mortality labels: pandas port of preop_xai.cohort.build_cohort and labels.build_labels
(same rules), with the reviewed mappings stated explicitly below. Prints aggregate counts only."""
import json, sys
import numpy as np, pandas as pd
RAW = sys.argv[1]
def parse_times(values):
    text = values.astype("string")
    parsed = pd.to_datetime(text, format="ISO8601", errors="coerce")
    for fmt in ("%m/%d/%y %H:%M", "%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M"):
        parsed = parsed.fillna(pd.to_datetime(text, format=fmt, errors="coerce"))
    return parsed
COLS = {"MRN": "patient_id", "LOG_ID": "operation_id", "BIRTH_DATE": "age", "SEX": "sex", "ASA_RATING_C": "asa",
        "AN_START_DATETIME": "t0", "AN_STOP_DATETIME": "anesthesia_end", "HOSP_ADMSN_TIME": "admission_time",
        "HOSP_DISCH_TIME": "discharge_time", "DISCH_DISP_C": "disposition_code", "DISCH_DISP": "disposition",
        "ICU_ADMIN_FLAG": "icu_flag"}
info = pd.read_csv(f"{RAW}/patient_information.csv", dtype=str, keep_default_na=False, na_values=[""])
info = info[list(COLS)].rename(columns=COLS)
for c in ("t0", "anesthesia_end", "admission_time", "discharge_time"):
    info[c] = parse_times(info[c])
flow = {"rows": len(info), "patients": int(info.patient_id.nunique()), "operations": int(info.operation_id.nunique())}
data = info.drop_duplicates().copy()
flow["exact_duplicates_removed"] = len(info) - len(data)
ex = {}
def remove(mask, reason):
    global data
    ex[reason] = int(mask.sum()); data = data.loc[~mask].copy()
remove(data.operation_id.duplicated(keep=False), "operation_conflict")
data["age"] = pd.to_numeric(data.age, errors="coerce")
asa = pd.to_numeric(data.asa, errors="coerce")
remove(data.age.isna() | ~data.age.between(18, np.inf), "not_adult")
asa = asa.loc[data.index]
remove(asa.eq(6).fillna(False) | (asa.notna() & ~asa.isin([1, 2, 3, 4, 5, 6])), "invalid_or_donor_asa")
data["asa"] = pd.to_numeric(data.asa, errors="coerce").astype("Int64").astype("string")
remove(~(data.t0.notna() & (data.anesthesia_end > data.t0)), "invalid_anesthesia_boundary")
data = data.sort_values(["patient_id", "t0", "operation_id"], kind="stable")
first = data.groupby("patient_id").t0.transform("min")
firsts = data.loc[data.t0.eq(first)]
amb = firsts.loc[firsts.duplicated("patient_id", keep=False), "patient_id"]
remove(data.patient_id.isin(amb), "ambiguous_first_operation_time")
remove(data.patient_id.duplicated(), "later_eligible_operation")
cohort = data.reset_index(drop=True)
flow["exclusions"] = ex; flow["indexed_patients"] = len(cohort)
# reviewed in-hospital mortality mapping (death at discharge; transfers/hospice unknown, not survival)
POS = {"Expired", "Coroner"}
UNK = {"Hospice Facility", "Hospice Home", "Acute Care Facility (not this hospital)", "Acute Care Facility (this hospital)",
       "Federal Hospital", "Federal Hospital w Planned Readmit", "Critical Access Hospital", "Cancer Ctr/Children's Hospital",
       "Other Healthcare Not Defined in this List", "Designated Disaster Alternative Care Site",
       "Designated Disaster Alternate Care Site"}
linked = (cohort.admission_time <= cohort.t0) & (cohort.discharge_time >= cohort.anesthesia_end)
disp = cohort.disposition.fillna("")
mort = pd.Series(np.where(disp.isin(POS), 1.0, np.where(disp.isin(UNK) | disp.eq(""), np.nan, 0.0)), index=cohort.index)
mort[~linked] = np.nan
cohort["mortality"] = mort
flow["unlinked"] = int((~linked).sum()); flow["unknown_disposition"] = int((linked & (disp.isin(UNK) | disp.eq(""))).sum())
flow["mortality_known"] = int(mort.notna().sum()); flow["mortality_events"] = int(mort.sum())
flow["icu_flag_yes_among_known"] = int((cohort.icu_flag.eq("Yes") & mort.notna()).sum())
flow["asa_missing"] = int(cohort.asa.isna().sum())
print(json.dumps(flow, indent=1))
cohort.to_pickle(sys.argv[2])
