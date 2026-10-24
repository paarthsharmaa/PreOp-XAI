"""Execute the unchanged reference in a separate, resumable output workspace.

Run: uv run --locked python scripts/reproduce.py all
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, TypeAdapter

ROOT: Final = Path(__file__).resolve().parents[1]
SOURCE: Final = ROOT / "MOVER/preopxai"
BUNDLE: Final = ROOT / "PreOp_XAI_MOVER_code_and_verification"
OUT: Final = ROOT / "outputs/reproduction"
RUNNER: Final = OUT / "runner"
LOGS: Final = OUT / "logs"

class ReferenceEnvironment(BaseModel):
    """Machine-consumed dependency and input-hash evidence."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    packages: dict[str, str]
    inputs: dict[str, str]


def digest(path: Path) -> str:
    """Hash a file without loading large raw inputs into memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(args: list[str], cwd: Path, name: str) -> None:
    """Capture a real subprocess's combined output and propagate its failure."""
    LOGS.mkdir(parents=True, exist_ok=True)
    print(f"RUN {name}: {' '.join(args)}", flush=True)
    with (LOGS / f"{name}.log").open("w") as log:
        result = subprocess.run(args, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                check=False)
    print(f"EXIT {name}: {result.returncode}; {LOGS / (name + '.log')}", flush=True)
    result.check_returncode()


def stage() -> None:
    """Copy reference source byte-for-byte, never historical completed runs."""
    RUNNER.mkdir(parents=True, exist_ok=True)
    for path in SOURCE.iterdir():
        if path.is_file() and path.suffix in {".py", ".txt", ".bat"}:
            _ = shutil.copy2(path, RUNNER / path.name)
    for name in ("preop_xai", "shapshim", "data_prep", "tests"):
        _ = shutil.copytree(SOURCE / name, RUNNER / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for relative in ("mover_analysis.csv", "mover_analysis_lag0h.csv",
                     "data/vitaldb_clinical_data.csv"):
        target = RUNNER / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            _ = shutil.copy2(SOURCE / relative, target)
    for path in SOURCE.glob("mover_*.json"):
        if not (RUNNER / path.name).exists():
            _ = shutil.copy2(path, RUNNER / path.name)


def check() -> None:
    """Check dependencies, real input provenance and immutable source hashes."""
    expected = ReferenceEnvironment.model_validate_json(
        (BUNDLE / "verification/environment.json").read_text())
    versions = {name: importlib.metadata.version(name)
                for name in expected.packages}
    if versions != expected.packages:
        raise SystemExit(f"Dependency mismatch: {versions}")
    inputs = {name: digest(SOURCE / ("data/" + name if name.startswith("vitaldb") else name))
              for name in expected.inputs}
    if inputs != expected.inputs:
        raise SystemExit(f"Reference input hash mismatch: {inputs}")
    manifest = TypeAdapter(dict[str, str]).validate_json(
        (ROOT / "reference-source.sha256.json").read_text())
    changed = [name for name, sha in manifest.items() if digest(ROOT / name) != sha]
    if changed:
        raise SystemExit(f"Reference source changed: {changed}")
    metadata = {"python": sys.version, "versions": versions, "inputs": inputs,
                "source_files_verified": len(manifest), "cpu_count": os.cpu_count(),
                "thread_environment": {key: os.environ.get(key) for key in
                                       ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                        "MKL_NUM_THREADS", "PREOPXAI_WORKERS")}}
    LOGS.mkdir(parents=True, exist_ok=True)
    _ = (LOGS / "check.log").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


def protocol(steps: list[str]) -> None:
    """Run the original runner; complete stages resume using original semantics."""
    stage()
    run([sys.executable, "mover_run.py", *steps], RUNNER,
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
        "prepare": lambda: run([sys.executable, "-m", "scripts.prepare"],
                              ROOT, "prepare"),
        "protocol": lambda: protocol(sys.argv[2:]),
        "publication": lambda: run([sys.executable, "-m", "scripts.publication"],
                                  ROOT, "publication"),
        "verify": lambda: run([sys.executable, "-m", "scripts.verify"],
                             ROOT, "verify"),
    }
    command = sys.argv[1] if len(sys.argv) > 1 else "help"
    if command == "all":
        check()
        commands["prepare"]()
        protocol([])
        failures: list[str] = []
        for name in ("publication", "verify"):
            try:
                commands[name]()
            except subprocess.CalledProcessError:
                failures.append(name)
        if failures:
            raise SystemExit("Failed stages (see captured logs): " + ", ".join(failures))
    elif command in commands:
        commands[command]()
    else:
        raise SystemExit("Usage: reproduce.py check|prepare|protocol [steps...]|publication|verify|all")


if __name__ == "__main__":
    main()
