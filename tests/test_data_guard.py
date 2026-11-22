"""Fail if patient-level data or non-aggregate tables are tracked by git."""

from pathlib import PurePosixPath
import subprocess

from pipeline.config import ROOT

FORBIDDEN_SUFFIXES = {".pkl", ".pickle", ".npz", ".npy", ".parquet", ".feather", ".joblib", ".h5"}
AGGREGATE_CSV_NAMES = {"intervals.csv", "performance.csv"}


def tracked_files() -> list[PurePosixPath]:
    output = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True,
                            text=True, check=True).stdout
    return [PurePosixPath(name) for name in output.split("\0") if name]


def violations(files: list[PurePosixPath]) -> list[str]:
    found: list[str] = []
    for path in files:
        if path.parts[0] == "data" and path.as_posix() != "data/README.md":
            found.append(f"{path}: file under data/")
        if path.parts[0] == "outputs":
            found.append(f"{path}: run output")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            found.append(f"{path}: patient-level artifact type")
        if path.suffix.lower() == ".csv" and (path.parts[0] != "results" or path.name not in AGGREGATE_CSV_NAMES):
            found.append(f"{path}: non-aggregate CSV")
    return found


def test_no_patient_level_files_are_tracked() -> None:
    assert violations(tracked_files()) == []


def test_guard_detects_violations() -> None:
    bad = [PurePosixPath(name) for name in ("data/vitaldb/vitaldb_cases.csv", "results/mover_analysis.csv",
                                            "src/model.pkl", "outputs/runs/x.json")]
    assert all(violations([path]) for path in bad)
    assert violations([PurePosixPath("data/README.md"), PurePosixPath("results/main_icu/intervals.csv")]) == []
