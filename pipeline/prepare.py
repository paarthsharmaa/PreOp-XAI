"""Build the analysis tables from raw MOVER EPIC files.

Run: uv run --locked python -m pipeline.cli prepare
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pandas as pd

from pipeline.cli import digest
from pipeline.config import ROOT, load_paths

CHUNK_BYTES = 128 * 1024 * 1024


def main() -> None:
    """Prepare real EPIC inputs in bounded byte chunks; intermediates are deleted on exit."""
    paths = load_paths()
    raw = paths.mover_raw
    scripts = ROOT / "data_prep"
    paths.tables.mkdir(parents=True, exist_ok=True)
    paths.logs.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="preopxai-prepare-") as directory:
        work = Path(directory)
        env = dict(os.environ, PREOPXAI_WORK_DIR=str(work), PREOPXAI_TABLE_DIR=str(paths.tables))
        cohort = subprocess.run(
            [sys.executable, str(scripts / "mover_cohort.py"), str(raw),
             str(work / "cohort.pkl")], env=env, capture_output=True, text=True, check=True)
        _ = (paths.tables / "mover_cohort_flow.json").write_text(cohort.stdout)
        print(cohort.stdout, flush=True)
        lab = raw / "patient_labs.csv"
        size = lab.stat().st_size
        boundaries = [0]
        with lab.open("rb") as stream:
            for offset in range(CHUNK_BYTES, size, CHUNK_BYTES):
                _ = stream.seek(offset - 1)
                # The extractor completes the end line; prevent exact-line-boundary overlap.
                boundaries.append(offset + 1 if stream.read(1) == b"\n" else offset)
        boundaries.append(size)
        chunks: list[Path] = []
        for index, (start, end) in enumerate(zip(boundaries, boundaries[1:], strict=False)):
            chunk = work / f"chunk-{index:03d}.pkl"
            _ = subprocess.run([sys.executable, str(scripts / "lab_extract.py"), str(lab),
                                str(start), str(end), str(chunk), str(work / "cohort.pkl")],
                               env=env, check=True)
            chunks.append(chunk)
        frames: list[pd.DataFrame] = [pd.read_pickle(path) for path in chunks]
        candidates: pd.DataFrame = pd.concat(frames, ignore_index=True)
        candidates.to_pickle(work / "candidates.pkl")
        for script, args in (("mover_features.py", []), ("mover_features2.py", ["0"]),
                             ("resp_feasibility.py", [str(raw)])):
            _ = subprocess.run([sys.executable, str(scripts / script), *args], env=env, check=True)
    tables = {name: {"rows": len(pd.read_csv(paths.tables / name)),
                     "sha256": digest(paths.tables / name)}
              for name in ("mover_analysis.csv", "mover_analysis_lag0h.csv")}
    _ = (paths.logs / "preparation.json").write_text(json.dumps(tables, indent=2))
    print("PASS preparation; patient-level intermediates removed", flush=True)


if __name__ == "__main__":
    main()
