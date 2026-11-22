"""Aggregate inventory of lab names x units in a byte range of patient_labs.csv (no patient-level output)."""
import io, sys, pickle, time
import pandas as pd
path, start, end, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
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
df = pd.read_csv(io.BytesIO(header + buf), dtype=str, keep_default_na=False, usecols=["Lab Name", "Measurement Units", "ENC_TYPE_NM"])
c = df.groupby(["Lab Name", "Measurement Units"]).size()
pickle.dump({"counts": c, "rows": len(df), "enc": df["ENC_TYPE_NM"].value_counts()}, open(out, "wb"))
print(len(df), "rows", round(time.time() - t), "s")
