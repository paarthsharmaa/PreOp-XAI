"""PreOp-XAI command line.

Run: uv run --locked python -m pipeline.cli check|prepare|protocol [steps...]|report|verify|export-models|all
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
from typing import Final

from pipeline.config import ROOT, load_paths

MOVER_FILES: Final = ("patient_information.csv", "patient_labs.csv",
                      "patient_post_op_complications.csv")
VITALDB_COLUMNS: Final = frozenset({
    "caseid", "subjectid", "anestart", "aneend", "adm", "dis", "icu_days", "death_inhosp",
    "age", "sex", "asa", "preop_hb", "preop_plt", "preop_cr", "preop_bun", "preop_na",
    "preop_k", "preop_gluc"})
SCIENTIFIC_PACKAGES: Final = ("scikit-learn", "xgboost", "numpy", "pandas", "scipy", "matplotlib")


def digest(path: Path) -> str:
    """Hash a file without loading large raw inputs into memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(args: list[str], name: str) -> None:
    """Capture a subprocess's combined output and propagate its failure."""
    logs = load_paths().logs
    logs.mkdir(parents=True, exist_ok=True)
    print(f"RUN {name}: {' '.join(args)}", flush=True)
    with (logs / f"{name}.log").open("w") as log:
        result = subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
    print(f"EXIT {name}: {result.returncode}; {logs / (name + '.log')}", flush=True)
    result.check_returncode()


def pinned_versions() -> dict[str, str]:
    """Read the exact scientific dependency pins from pyproject.toml."""
    with (ROOT / "pyproject.toml").open("rb") as stream:
        dependencies: list[str] = tomllib.load(stream)["project"]["dependencies"]
    pins = dict(item.split("==", 1) for item in dependencies)
    return {name: pins[name] for name in SCIENTIFIC_PACKAGES}


def check() -> None:
    """Check dependency versions and the presence and shape of the raw inputs."""
    paths = load_paths()
    expected = pinned_versions()
    versions = {name: importlib.metadata.version(name) for name in expected}
    if versions != expected:
        raise SystemExit(f"Dependency mismatch: {versions}")
    missing = [str(paths.mover_raw / name) for name in MOVER_FILES
               if not (paths.mover_raw / name).is_file()]
    if not paths.vitaldb_clinical.is_file():
        missing.append(str(paths.vitaldb_clinical))
    if missing:
        raise SystemExit("Missing input files (see data/README.md): " + ", ".join(missing))
    with paths.vitaldb_clinical.open() as stream:
        columns = set(stream.readline().strip().split(","))
    if absent := VITALDB_COLUMNS - columns:
        raise SystemExit(f"VitalDB clinical table lacks columns: {sorted(absent)}")
    metadata = {"python": sys.version, "versions": versions, "cpu_count": os.cpu_count(),
                "mover_raw": str(paths.mover_raw), "vitaldb_clinical": str(paths.vitaldb_clinical),
                "vitaldb_sha256": digest(paths.vitaldb_clinical),
                "thread_environment": {key: os.environ.get(key) for key in
                                       ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                        "MKL_NUM_THREADS", "PREOPXAI_WORKERS")}}
    paths.logs.mkdir(parents=True, exist_ok=True)
    _ = (paths.logs / "check.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


def protocol(steps: list[str]) -> None:
    """Run protocol steps; completed steps resume from their outputs."""
    run([sys.executable, "-m", "pipeline.protocol", *steps],
        "protocol-" + ("all" if not steps else "-".join(steps)))


def main() -> None:
    """Dispatch explicit stages without changing scientific defaults."""
    _ = os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        _ = os.environ.setdefault(name, "1")
    _ = os.environ.setdefault("PREOPXAI_WORKERS", "6")
    commands = {
        "check": check,
        "prepare": lambda: run([sys.executable, "-m", "pipeline.prepare"], "prepare"),
        "protocol": lambda: protocol(sys.argv[2:]),
        "report": lambda: run([sys.executable, "-m", "pipeline.reporting.stage", *sys.argv[2:]],
                              "report"),
        "verify": lambda: run([sys.executable, "-m", "pipeline.verify"], "verify"),
        "export-models": lambda: run([sys.executable, "-m", "pipeline.export_models"], "export-models"),
    }
    command = sys.argv[1] if len(sys.argv) > 1 else "help"
    if command == "all":
        check()
        commands["prepare"]()
        protocol([])
        commands["report"]()
        commands["verify"]()
    elif command in commands:
        commands[command]()
    else:
        raise SystemExit("Usage: pipeline.cli check|prepare|protocol [steps...]|report [--promote]|verify|"
                         "export-models|all")


if __name__ == "__main__":
    main()
