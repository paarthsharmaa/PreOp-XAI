"""Pass over a byte range of patient_labs.csv keeping only rows whose (Lab Name, unit) is in the candidate map and
whose LOG_ID is an indexed cohort operation. Output: compact candidate rows (kept on this computer only)."""
import io, sys, time
import pandas as pd
path, start, end, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
NAMES = {"Hemoglobin", "Platelets", "Creatinine", "Urea nitrogen", "Sodium", "Potassium", "Glucose"}
ops = set(pd.read_pickle(sys.argv[5]).operation_id)
t = time.time()
with open(path, "rb") as f:
    header = f.readline()
    if start > 0:
        f.seek(start - 1)
        if f.read(1) != b"\n":
            f.readline()
    else:
        f.seek(len(header))
    pos = f.tell(); buf = f.read(max(0, end - pos)); buf += f.readline()
df = pd.read_csv(io.BytesIO(header + buf), dtype=str, keep_default_na=False,
                 usecols=["LOG_ID", "Lab Code", "Lab Name", "Observation Value", "Measurement Units", "Collection Datetime"])
df = df[df["Lab Name"].isin(NAMES) & df["LOG_ID"].isin(ops)]
df.to_pickle(out)
print(len(df), "kept", round(time.time() - t), "s")
