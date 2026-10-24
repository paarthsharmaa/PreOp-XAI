"""One-command runner for the PreOp-XAI MOVER study. Run from this folder:  python mover_run.py

Steps (each is skipped if its output already exists, so the run can be resumed after an interruption):
  1. environment check and exact-SHAP self-test (brute-force comparison)
  2. main analysis, split seed 2026, mortality and ICU admission (1,000 bootstraps, SHAP, 10 stability refits,
     external validation of the frozen models on VitalDB)
  3. sensitivity analysis on the lag-0 laboratory table (performance only, 1,000 bootstraps)
  4. determinism check: the main mortality analysis is run a second time and compared
  5. split check: test-set event counts for split seeds 1-1000 (splitting only)
  6. repeated splits: whole protocol for split seeds 1-100, both endpoints (parallel)
  7. export: aggregate results only -> export/preopxai_mover_results.zip

Patient-level files (predictions, SHAP arrays, local explanation plots) stay in runs/ on this computer and are
never copied to the export.
"""
import json
import multiprocessing as mp
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS, EXPORT = HERE / "runs", HERE / "export"
TABLE, TABLE_LAG0 = HERE / "mover_analysis.csv", HERE / "mover_analysis_lag0h.csv"
ENDPOINTS = ("mortality", "icu")
N_REPEATS = int(os.environ.get("PREOPXAI_TEST_REPEATS", 100))   # 100 = protocol; override only for testing
EXPECTED = {"scikit-learn": "1.8.0", "xgboost": "2.1.4"}


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(RUNS / "run_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------- repeated-split worker (top level for Windows spawn)
def repeat_one(job):
    endpoint, seed, table = job
    target = RUNS / f"repeats_{endpoint}" / f"seed{seed:03d}.json"
    if target.exists():
        return endpoint, seed, None
    warnings.simplefilter("ignore")
    sys.path.insert(0, str(HERE))
    from mover_study import main
    with tempfile.TemporaryDirectory() as tmp:
        r = main(endpoint, seed, tmp, mode="light", table=table)
    ev = r["evaluation"]
    keep = {"seed": seed, "partition_events": r["partition_events"], "selection": {
        k: {kk: v[kk] for kk in ("parameters", "cv_average_precision", "threshold", "calibration_status")}
        | {"calibration_slope": v["diagnostics"].get("calibration_slope"),
           "calibration_intercept": v["diagnostics"].get("calibration_intercept")}
        for k, v in r["selection"].items()},
        "test": {k: {kk: m[kk] for kk in ("raw", "calibrated", "raw_calibration", "calibration", "tp", "fp", "tn", "fn",
                                          "sensitivity", "specificity", "ppv", "npv", "training_prevalence_brier",
                                          "calibration_status")} for k, m in ev["models"].items()},
        "test_n": ev["n"], "test_events": ev["events"], "runtime_s": r["runtime_s"]}
    target.write_text(json.dumps(keep, default=str))
    return endpoint, seed, {k: round(m["raw"]["auroc"], 3) for k, m in ev["models"].items()}


# ---------------------------------------------------------------- steps
def step_environment():
    import importlib
    env = {"python": sys.version, "platform": platform.platform(), "processor": platform.processor(),
           "cpu_count": os.cpu_count(), "packages": {}}
    for p, mod in (("scikit-learn", "sklearn"), ("xgboost", "xgboost"), ("numpy", "numpy"), ("pandas", "pandas"),
                   ("scipy", "scipy"), ("matplotlib", "matplotlib")):
        try:
            env["packages"][p] = importlib.import_module(mod).__version__
        except ImportError:
            raise SystemExit(f"Package {p} is missing. Install with: pip install -r requirements.txt")
    for p, v in EXPECTED.items():
        if env["packages"][p] != v:
            log(f"WARNING: {p} {env['packages'][p]} installed; the study was prepared with {v}.")
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required (the repository uses 3.11 syntax).")
    import hashlib
    env["inputs"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in (TABLE, TABLE_LAG0, HERE / "data" / "vitaldb_clinical_data.csv")}
    env["repo_commit"] = (HERE / "preop_xai" / "REPO_COMMIT.txt").read_text().strip()
    (RUNS / "environment.json").write_text(json.dumps(env, indent=1))
    log(f"environment: Python {platform.python_version()}, " +
        ", ".join(f"{k} {v}" for k, v in env["packages"].items()))
    t = subprocess.run([sys.executable, str(HERE / "tests" / "test_exact_shap.py")], capture_output=True, text=True)
    (RUNS / "shap_selftest.txt").write_text(t.stdout + t.stderr)
    if t.returncode != 0 or "PASS" not in t.stdout:
        raise SystemExit("Exact-SHAP self-test failed; see runs/shap_selftest.txt")
    log("exact-SHAP self-test passed: " + t.stdout.strip().splitlines()[-2])


def step_main():
    from mover_study import main
    for e in ENDPOINTS:
        out = RUNS / f"main_{e}"
        if (out / "study.json").exists():
            log(f"main {e}: already done")
            continue
        log(f"main {e}: started (about 5-15 minutes)")
        r = main(e, 2026, out, mode="full", table=TABLE)
        m, x = r["evaluation"]["models"], r["external_vitaldb"]["models"]
        log(f"main {e}: done in {r['runtime_s']} s; test events {r['partition_events']['test']}; AUROC test "
            f"LR {m['lr']['raw']['auroc']:.3f} XGB {m['xgboost']['raw']['auroc']:.3f}; VitalDB "
            f"LR {x['lr']['raw']['auroc']:.3f} XGB {x['xgboost']['raw']['auroc']:.3f}")


def step_lag0():
    from mover_study import main
    for e in ENDPOINTS:
        out = RUNS / f"lag0_{e}"
        if (out / "study.json").exists():
            log(f"lag-0 {e}: already done")
            continue
        r = main(e, 2026, out, mode="perf", table=TABLE_LAG0)
        m = r["evaluation"]["models"]
        log(f"lag-0 {e}: AUROC LR {m['lr']['raw']['auroc']:.3f} XGB {m['xgboost']['raw']['auroc']:.3f}")


def _strip(d):
    if isinstance(d, dict):
        return {k: _strip(v) for k, v in d.items() if k not in ("runtime_s",)}
    if isinstance(d, list):
        return [_strip(v) for v in d]
    return d


def step_rerun():
    from mover_study import main
    target = RUNS / "determinism_check.json"
    if target.exists():
        log("determinism check: already done")
        return
    log("determinism check: re-running the main mortality analysis")
    r2 = main("mortality", 2026, RUNS / "rerun_mortality", mode="full", table=TABLE)
    r1 = json.loads((RUNS / "main_mortality" / "study.json").read_text())
    r2 = json.loads(json.dumps(r2, default=str))
    same = _strip(r1) == _strip(r2)
    diffs = []
    if not same:
        def walk(a, b, path):
            if type(a) is not type(b):
                diffs.append(path)
            elif isinstance(a, dict):
                for k in set(a) | set(b):
                    walk(a.get(k), b.get(k), f"{path}.{k}")
            elif isinstance(a, list):
                if len(a) != len(b):
                    diffs.append(path)
                else:
                    for i, (u, v) in enumerate(zip(a, b)):
                        walk(u, v, f"{path}[{i}]")
            elif a != b:
                diffs.append(path)
        walk(_strip(r1), _strip(r2), "")
    target.write_text(json.dumps({"identical_except_runtime": same, "differences": diffs[:200]}, indent=1))
    log(f"determinism check: identical = {same}" + ("" if same else f" ({len(diffs)} differing values)"))


def step_split_check():
    target = RUNS / "split_check.json"
    if target.exists():
        log("split check: already done")
        return
    import numpy as np
    from cohort_vitaldb import assign_splits
    from mover_study import load_table
    _, labels = load_table(TABLE)

    def events(seed):
        sp = assign_splits(labels, seed)
        k = sp.partition == "test"
        return int(sp.loc[k, "icu"].sum()), int(sp.loc[k, "mortality"].sum())
    alt = np.array([events(s) for s in range(1, 1001)])
    p = events(2026)
    out = {"primary_seed": 2026, "primary_test_icu": p[0], "primary_test_deaths": p[1], "alt_seeds": [1, 1000],
           "alt_test_icu_min": int(alt[:, 0].min()), "alt_test_icu_median": float(np.median(alt[:, 0])),
           "alt_test_icu_max": int(alt[:, 0].max()), "alt_share_le_primary": float(np.mean(alt[:, 0] <= p[0])),
           "alt_test_deaths_unique": sorted(set(alt[:, 1].tolist()))}
    target.write_text(json.dumps(out, indent=1))
    log(f"split check: primary test ICU {p[0]} (seeds 1-1000: {out['alt_test_icu_min']}-{out['alt_test_icu_max']})")


def step_repeats():
    jobs = [(e, s, str(TABLE)) for e in ENDPOINTS for s in range(1, N_REPEATS + 1)]
    for e in ENDPOINTS:
        (RUNS / f"repeats_{e}").mkdir(parents=True, exist_ok=True)
    todo = [j for j in jobs if not (RUNS / f"repeats_{j[0]}" / f"seed{j[1]:03d}.json").exists()]
    if not todo:
        log("repeated splits: already done")
        return
    workers = max(1, min(int(os.environ.get("PREOPXAI_WORKERS", min((os.cpu_count() or 2) - 2, 10))), len(todo)))
    log(f"repeated splits: {len(todo)} runs left, {workers} parallel workers (this is the longest step)")
    t0, done = time.time(), 0
    # 'spawn' (the Windows default) everywhere: forking after OpenMP threads exist can deadlock on Linux.
    with mp.get_context("spawn").Pool(workers, maxtasksperchild=10) as pool:
        for e, s, auc in pool.imap_unordered(repeat_one, todo):
            done += 1
            eta = (time.time() - t0) / done * (len(todo) - done) / 60
            if done % 5 == 0 or done == len(todo):
                log(f"  {done}/{len(todo)} done (last: {e} seed {s} {auc}); about {eta:.0f} min left")


SUPPRESSED = {"cells": 0}


def _suppress(d):
    """Drop calibration-bin cells describing fewer than 11 patients (they could describe single patients)."""
    if isinstance(d, dict):
        return {k: _suppress(v) for k, v in d.items()}
    if isinstance(d, list):
        keep = []
        for v in d:
            if isinstance(v, dict) and {"n", "predicted", "observed"} <= set(v) and isinstance(v["n"], int) and v["n"] < 11:
                SUPPRESSED["cells"] += 1
                continue
            keep.append(_suppress(v))
        return keep
    return d


def step_export():
    if EXPORT.exists():
        shutil.rmtree(EXPORT)
    EXPORT.mkdir()
    files = {}
    for name in ("environment.json", "shap_selftest.txt", "determinism_check.json", "split_check.json", "run_log.txt"):
        files[name] = RUNS / name
    for name in ("mover_cohort_flow.json", "mover_feature_stats.json", "mover_feature_stats_lag0h.json",
                 "mover_respiratory_feasibility.json"):
        if (HERE / name).exists():
            files[f"cohort/{name}"] = HERE / name
    for run in [f"main_{e}" for e in ENDPOINTS] + [f"lag0_{e}" for e in ENDPOINTS] + ["rerun_mortality"]:
        for rel in ("study.json", "metrics.json", "intervals.csv", "performance.csv", "explain/explain.json",
                    "stability/stability.json", "external_vitaldb/metrics.json", "external_vitaldb/intervals.csv"):
            if (RUNS / run / rel).exists():
                files[f"{run}/{rel}"] = RUNS / run / rel
    for e in ENDPOINTS:
        for f in sorted((RUNS / f"repeats_{e}").glob("seed*.json")):
            files[f"repeats_{e}/{f.name}"] = f
    for rel, src in files.items():
        dst = EXPORT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".json":
            dst.write_text(json.dumps(_suppress(json.loads(src.read_text())), indent=1))
        else:
            shutil.copy2(src, dst)
    (EXPORT / "EXPORT_NOTE.txt").write_text(
        "Aggregate results only (metrics, intervals, model settings, aggregate SHAP summaries, curve coordinates, "
        "decile calibration). No identifiers, dates, rows, predictions or per-patient SHAP values.\n"
        f"Calibration-bin cells with fewer than 11 patients removed: {SUPPRESSED['cells']}.\n")
    z = EXPORT / "preopxai_mover_results.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(EXPORT.rglob("*")):
            if p.is_file() and p != z:
                zf.write(p, p.relative_to(EXPORT))
    log(f"export: {len(files)} files -> {z} ({z.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    mp.freeze_support()
    RUNS.mkdir(exist_ok=True)
    sys.path[:0] = [str(HERE), str(HERE / "shapshim")]
    warnings.simplefilter("ignore")
    only = sys.argv[1:]
    steps = [("environment", step_environment), ("main", step_main), ("lag0", step_lag0), ("rerun", step_rerun),
             ("split_check", step_split_check), ("repeats", step_repeats), ("export", step_export)]
    T = time.time()
    for name, fn in steps:
        if only and name not in only:
            continue
        fn()
    log(f"finished in {(time.time() - T) / 60:.1f} min. Send export/preopxai_mover_results.zip back (it stays in "
        f"this folder; Claude can pick it up).")
