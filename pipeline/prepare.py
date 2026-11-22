"""Run original preparation scripts with an isolated HOME, not source changes.

Run: uv run --locked python scripts/reproduce.py prepare
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pandas as pd

from scripts.reproduce import LOGS, ROOT, RUNNER, SOURCE, digest, stage


def main() -> None:
    """Prepare real EPIC inputs in bounded byte chunks using the reference code."""
    stage()
    raw = Path(os.environ.get("PREOPXAI_RAW", ROOT / "MOVER/EPIC_EMR/EMR")).resolve()
    scripts = SOURCE / "data_prep"
    with tempfile.TemporaryDirectory(prefix="preop-preparation-") as directory:
        home = Path(directory)
        work = home / "work"
        work.mkdir()
        target = home / "mnt/Downloads/MOVER/preopxai"
        target.parent.mkdir(parents=True)
        target.symlink_to(RUNNER, target_is_directory=True)
        env = dict(os.environ, HOME=str(home))
        cohort = subprocess.run(
            [sys.executable, str(scripts / "mover_cohort.py"), str(raw),
             str(work / "cohort.pkl")], env=env, capture_output=True, text=True, check=True)
        _ = (RUNNER / "mover_cohort_flow.json").write_text(cohort.stdout)
        print(cohort.stdout, flush=True)
        lab = raw / "patient_labs.csv"
        size = lab.stat().st_size
        boundaries = [0]
        with lab.open("rb") as stream:
            for offset in range(128 * 1024 * 1024, size, 128 * 1024 * 1024):
                _ = stream.seek(offset - 1)
                # The extractor completes the end line; prevent exact-line-boundary overlap.
                boundaries.append(offset + 1 if stream.read(1) == b"\n" else offset)
        boundaries.append(size)
        chunks: list[Path] = []
        for index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
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
        comparisons = {}
        for name in ("mover_analysis.csv", "mover_analysis_lag0h.csv"):
            generated = pd.read_csv(RUNNER / name)
            original = pd.read_csv(SOURCE / name)
            pd.testing.assert_frame_equal(generated, original, check_exact=True)
            comparisons[name] = {"rows": len(generated), "values_identical": True,
                                 "generated_sha256": digest(RUNNER / name),
                                 "reference_sha256": digest(SOURCE / name)}
        _ = (LOGS / "preparation-comparison.json").write_text(json.dumps(comparisons, indent=2))
    print("PASS preparation; isolated HOME and patient-level intermediate pickles removed", flush=True)


if __name__ == "__main__":
    main()
