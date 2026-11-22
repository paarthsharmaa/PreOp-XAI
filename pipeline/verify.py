"""Check real generated artifacts against reference scientific outputs.

Run: uv run --locked python scripts/reproduce.py verify
"""

from __future__ import annotations

import json
import math
import sys

from pydantic import JsonValue, TypeAdapter

from scripts.reproduce import BUNDLE, LOGS, OUT, RUNNER, check, run

JSON = JsonValue
IGNORED = {"runtime_s"}


def differences(reference: JSON, actual: JSON, path: str = "") -> list[str]:
    """Compare semantic results at tight numeric tolerance, retaining every mismatch."""
    match reference, actual:
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
            return [item for index, (a, b) in enumerate(zip(left, right))
                    for item in differences(a, b, f"{path}[{index}]")]
        case int() | float(), int() | float():
            return [] if math.isclose(reference, actual, rel_tol=1e-8, abs_tol=1e-10) else [
                f"{path}: reference={reference}, actual={actual}"]
        case _:
            return [] if reference == actual else [f"{path}: reference={reference}, actual={actual}"]


def main() -> None:
    """Run the existing brute-force SHAP regression and compare every aggregate artifact."""
    check()
    run([sys.executable, "tests/test_exact_shap.py"], RUNNER, "exact-shap")
    report: dict[str, list[str]] = {}
    adapter: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
    # Compare numerical evidence, not OS metadata, wall-clock logs or private arrays.
    for source in sorted((BUNDLE / "results").rglob("*.json")):
        relative = source.relative_to(BUNDLE / "results")
        if relative.as_posix() in {"environment.json", "summary.json"}:
            continue
        generated = RUNNER / "export" / relative
        if not generated.is_file():
            report[str(relative)] = ["missing regenerated artifact"]
            continue
        report[str(relative)] = differences(adapter.validate_json(source.read_text()),
                                            adapter.validate_json(generated.read_text()))
    summary_reference = adapter.validate_json((BUNDLE / "results/summary.json").read_text())
    summary_actual = adapter.validate_json((OUT / "publication/results/summary.json").read_text())
    report["summary.json"] = differences(summary_reference, summary_actual)
    _ = (LOGS / "reference-comparison.json").write_text(json.dumps(report, indent=2))
    failed = {name: values for name, values in report.items() if values}
    print(f"Compared {len(report)} artifacts; {len(failed)} differ; "
          + f"full paths in {LOGS / 'reference-comparison.json'}")
    if failed:
        raise SystemExit(1)
    print("PASS reference comparison")


if __name__ == "__main__":
    main()
