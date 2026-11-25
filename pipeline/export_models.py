"""Refit the primary split, save it to artifacts/ and prove the saved models reproduce the study.

Run: uv run --locked python -m pipeline.cli export-models
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Final
import warnings

import numpy as np
import pandas as pd

from pipeline.cli import digest
from pipeline.config import ROOT, load_paths
from pipeline.model_artifacts import ENDPOINTS, MODELS, EndpointArtifacts, artifacts_dir, load_endpoint, save_endpoint
from pipeline.protocol import _suppress  # pyright: ignore[reportPrivateUsage]
from preopxai import study  # noqa: F401  # Puts the exact-SHAP shim on sys.path before explain is imported.
from preopxai.calibration import calibrate_models
from preopxai.evaluate import evaluate_models
from preopxai.explain import _background, _explain_raw  # pyright: ignore[reportPrivateUsage]
from preopxai.preprocessing import FEATURES
from preopxai.study import assign_splits, build_vitaldb, load_table
from preopxai.train import fit_models

SPLIT_SEED: Final = 2026
TRAINING_SEED: Final = 2026
FOLDS: Final = 5
# Committed results come from Windows; per-run values differ from Linux by up to about 6e-7.
TOLERANCE: Final = 2e-6
COMPARED_KEYS: Final = ("raw", "calibrated", "raw_calibration", "calibration", "bins", "raw_bins", "threshold", "tp",
                        "fp", "tn", "fn", "sensitivity", "specificity", "ppv", "npv", "accuracy", "f1",
                        "predicted_positives", "training_prevalence_brier")


def mismatches(expected: object, actual: object, path: str) -> list[tuple[str, float | None]]:
    """List every leaf that differs, with its absolute difference when numeric."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected) != set(actual):
            return [(f"{path} keys differ", None)]
        return [item for key in expected for item in mismatches(expected[key], actual[key], f"{path}.{key}")]
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [(f"{path} length {len(expected)} != {len(actual)}", None)]
        return [item for i, (a, b) in enumerate(zip(expected, actual, strict=True))
                for item in mismatches(a, b, f"{path}[{i}]")]
    if isinstance(expected, bool) or isinstance(actual, bool) or not (
            isinstance(expected, int | float) and isinstance(actual, int | float)):
        return [] if expected == actual else [(f"{path}: {expected!r} != {actual!r}", None)]
    gap = abs(float(expected) - float(actual))
    return [] if gap <= TOLERANCE else [(f"{path}: {expected} != {actual}", gap)]


def largest_gap(expected: object, actual: object) -> float:
    """Largest absolute numeric difference between two matching structures."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        return max((largest_gap(expected[k], actual[k]) for k in expected if k in actual), default=0.0)
    if isinstance(expected, list) and isinstance(actual, list):
        return max((largest_gap(a, b) for a, b in zip(expected, actual, strict=False)), default=0.0)
    if isinstance(expected, int | float) and isinstance(actual, int | float) and not isinstance(expected, bool):
        return abs(float(expected) - float(actual))
    return 0.0


def primary_partitions(table: Path, endpoint: str) -> dict[str, tuple[pd.DataFrame, pd.Series]]:
    """Rebuild the study's partitions for the primary split seed."""
    X, labels = load_table(table)
    splits = assign_splits(labels, seed=SPLIT_SEED)
    X = X.loc[labels.sort_values(["patient_id", "operation_id"], kind="stable").index].reset_index(drop=True)
    parts: dict[str, tuple[pd.DataFrame, pd.Series]] = {}
    for name in ("train", "validation", "test"):
        mask = (splits.partition == name).to_numpy()
        parts[name] = (X[mask].reset_index(drop=True), splits.loc[mask, endpoint].astype(int).reset_index(drop=True))
    return parts


def vitaldb_partition(path: Path, endpoint: str) -> tuple[pd.DataFrame, pd.Series]:
    """Rebuild the external cohort with known outcomes."""
    X, labels, _, _ = build_vitaldb(path)
    known = labels[endpoint].notna().to_numpy()
    return X[known].reset_index(drop=True), labels.loc[known, endpoint].astype(int).reset_index(drop=True)


def _compare_metrics(saved: EndpointArtifacts, X: pd.DataFrame, y: pd.Series, committed: Path, label: str,
                     failures: list[str]) -> float:
    with tempfile.TemporaryDirectory() as directory, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = evaluate_models(saved.bundles, X, y, Path(directory), bootstraps=1, seed=TRAINING_SEED)
    actual: Any = _suppress(json.loads(json.dumps(result, default=str)))
    expected: Any = json.loads(committed.read_text())
    gap = 0.0
    for key in ("n", "events"):
        failures.extend(f"{label}.{text}" for text, _ in mismatches(expected[key], actual[key], key))
    for model in MODELS:
        left = {key: expected["models"][model][key] for key in COMPARED_KEYS}
        right = {key: actual["models"][model][key] for key in COMPARED_KEYS}
        failures.extend(f"{label}.{text}" for text, _ in mismatches(left, right, model))
        gap = max(gap, largest_gap(left, right))
    return gap


def _compare_shap(saved: EndpointArtifacts, X: pd.DataFrame, committed: Path, failures: list[str]) -> float:
    expected: Any = json.loads(committed.read_text())["models"]
    gap = 0.0
    for model in MODELS:
        data = _explain_raw(saved.bundles[model], saved.background, X)
        actual = {"global_mean_absolute_raw": dict(zip(FEATURES, np.abs(data["grouped"]).mean(axis=0).tolist(),
                                                       strict=True)),
                  "baseline_raw_mean": float(data["baseline"].mean())}
        left = {key: expected[model][key] for key in actual}
        failures.extend(f"shap.{text}" for text, _ in mismatches(left, actual, model))
        gap = max(gap, largest_gap(left, actual))
    return gap


def export_endpoint(endpoint: str, table: Path, vitaldb: Path, target: Path) -> dict[str, object]:
    """Fit, save, reload from disk and compare with results/main_<endpoint>."""
    run = ROOT / "results" / f"main_{endpoint}"
    study_record = json.loads((run / "study.json").read_text())
    table_hash = digest(table)
    if table_hash != study_record["table_sha256"]:
        raise SystemExit(f"{table} differs from the table used for results/main_{endpoint}.")
    parts = primary_partitions(table, endpoint)
    (x_train, y_train), (x_validation, y_validation) = parts["train"], parts["validation"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        bundles = fit_models(x_train, y_train, seed=TRAINING_SEED, folds=FOLDS)
        calibrate_models(bundles, x_validation, y_validation)
    background, _ = _background(x_train, TRAINING_SEED)
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                            check=True).stdout.strip()
    save_endpoint(target, bundles, background, {"endpoint": endpoint, "split_seed": SPLIT_SEED,
                                                "training_seed": TRAINING_SEED, "folds": FOLDS,
                                                "table_sha256": table_hash, "code_commit": commit})
    saved = load_endpoint(target)
    failures: list[str] = []
    for model in MODELS:
        failures.extend(f"selection.{text}" for text, _ in mismatches(
            study_record["selection"][model]["parameters"], saved.bundles[model].parameters, model))
    x_test, y_test = parts["test"]
    test_gap = _compare_metrics(saved, x_test, y_test, run / "metrics.json", "test", failures)
    x_external, y_external = vitaldb_partition(vitaldb, endpoint)
    external_gap = _compare_metrics(saved, x_external, y_external, run / "external_vitaldb/metrics.json", "vitaldb",
                                    failures)
    shap_gap = _compare_shap(saved, x_validation, run / "explain/explain.json", failures)
    if failures:
        print(f"{endpoint}: {len(failures)} values differ from results/main_{endpoint}", file=sys.stderr)
        print("\n".join(failures[:40]), file=sys.stderr)
        raise SystemExit(f"Saved {endpoint} models do not reproduce the committed results.")
    return {"tolerance": TOLERANCE, "largest_gap": {"test": test_gap, "vitaldb": external_gap, "shap": shap_gap}}


def main() -> None:
    """Export both endpoints and record the comparison."""
    paths = load_paths()
    table = paths.tables / "mover_analysis.csv"
    if not table.is_file():
        raise SystemExit(f"Missing {table}. Run `uv run preopxai prepare` first.")
    if not paths.vitaldb_clinical.is_file():
        raise SystemExit(f"Missing {paths.vitaldb_clinical}. See data/README.md.")
    root = artifacts_dir()
    root.mkdir(parents=True, exist_ok=True)
    report = {endpoint: export_endpoint(endpoint, table, paths.vitaldb_clinical, root / endpoint)
              for endpoint in ENDPOINTS}
    _ = (root / "verification.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    print("PASS saved models reproduce results/main_*")


if __name__ == "__main__":
    main()
