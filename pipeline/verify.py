"""Compare a completed run with the committed aggregate results.

Run: uv run --locked python -m pipeline.cli verify
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys

from pydantic import JsonValue, TypeAdapter

from pipeline.cli import check
from pipeline.config import ROOT, load_paths

JSON = JsonValue
IGNORED = {"runtime_s", "code_commit"}
RELATIVE_TOLERANCE = 1e-8
ABSOLUTE_TOLERANCE = 1e-10


def differences(expected: JSON, actual: JSON, path: str = "") -> list[str]:
    """Compare semantic results at tight numeric tolerance, retaining every mismatch."""
    match expected, actual:
        case dict() as left, dict() as right:
            found: list[str] = []
            for key in sorted((left.keys() | right.keys()) - IGNORED):
                if key not in left or key not in right:
                    found.append(path + "." + key + " missing")
                else:
                    found.extend(differences(left[key], right[key], path + "." + key))
            return found
        case list() as left, list() as right:
            if len(left) != len(right):
                return [path + " length mismatch"]
            return [item for index, (a, b) in enumerate(zip(left, right, strict=True))
                    for item in differences(a, b, f"{path}[{index}]")]
        case int() | float(), int() | float():
            close = math.isclose(expected, actual, rel_tol=RELATIVE_TOLERANCE,
                                 abs_tol=ABSOLUTE_TOLERANCE)
            return [] if close else [f"{path}: expected={expected}, actual={actual}"]
        case _:
            return [] if expected == actual else [f"{path}: expected={expected}, actual={actual}"]


def artifact_pairs() -> dict[str, tuple[Path, Path]]:
    """Map every committed aggregate JSON to its regenerated counterpart."""
    paths = load_paths()
    pairs = {source.relative_to(ROOT / "results").as_posix():
             (source, paths.export / source.relative_to(ROOT / "results"))
             for source in sorted((ROOT / "results").rglob("*.json"))
             if source.name != "summary.json"}
    pairs["summary.json"] = (ROOT / "results/summary.json", paths.report / "results/summary.json")
    for name in ("determinism_check.json", "split_check.json"):
        pairs[name] = (ROOT / "verification" / name, paths.export / name)
    return pairs


def main() -> None:
    """Run the brute-force SHAP check and compare every aggregate artifact."""
    check()
    paths = load_paths()
    selftest = subprocess.run([sys.executable, str(ROOT / "tests/shap_selftest.py")],
                              capture_output=True, text=True, check=False)
    print(selftest.stdout, end="")
    selftest.check_returncode()
    adapter: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
    report: dict[str, list[str]] = {}
    for name, (committed, generated) in artifact_pairs().items():
        if not generated.is_file():
            report[name] = ["missing regenerated artifact"]
            continue
        report[name] = differences(adapter.validate_json(committed.read_text()),
                                   adapter.validate_json(generated.read_text()))
    output = paths.logs / "results-comparison.json"
    _ = output.write_text(json.dumps(report, indent=2))
    failed = [name for name, values in report.items() if values]
    print(f"Compared {len(report)} artifacts; {len(failed)} differ; full paths in {output}")
    if failed:
        raise SystemExit(1)
    print("PASS results comparison")


if __name__ == "__main__":
    main()
