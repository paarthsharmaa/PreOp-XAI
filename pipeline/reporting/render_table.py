"""Render the README results table from the committed aggregate results.

Run: uv run --locked python -m pipeline.reporting.render_table [--check]
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Final, cast

from pipeline.config import ROOT

START: Final = "<!-- results:start -->"
END: Final = "<!-- results:end -->"
ENDPOINTS: Final = (("mortality", "In-hospital mortality"), ("icu", "ICU admission"))
MODELS: Final = (("lr", "L2 logistic regression"), ("xgboost", "XGBoost"))
HEADER: Final = ("| Endpoint | Model | MOVER test AUROC (95% CI) | 100-split median AUROC (2.5–97.5%) "
                 "| VitalDB AUROC (95% CI) | VitalDB calibration slope |\n"
                 "| --- | --- | --- | --- | --- | --- |")


def _interval(path: Path, comparison: str) -> tuple[float, float]:
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            if row["comparison"] == comparison:
                return float(row["lower"]), float(row["upper"])
    raise KeyError(f"{comparison} not found in {path}")


def _load(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text()))


def _get(data: dict[str, object], *keys: str) -> float:
    current: object = data
    for key in keys:
        current = cast(dict[str, object], current)[key]
    return float(cast(float, current))


def render(results: Path) -> str:
    """Build the Markdown table; every number is read from results/."""
    summary = _load(results / "summary.json")
    rows = [HEADER]
    for endpoint, endpoint_name in ENDPOINTS:
        run = results / f"main_{endpoint}"
        study = _load(run / "study.json")
        repeats = cast(dict[str, object], summary[endpoint])
        for model, model_name in MODELS:
            test = _get(study, "evaluation", "models", model, "raw", "auroc")
            test_low, test_high = _interval(run / "intervals.csv", f"{model}.raw.auroc")
            external = _get(study, "external_vitaldb", "models", model, "raw", "auroc")
            external_low, external_high = _interval(run / "external_vitaldb/intervals.csv",
                                                    f"{model}.raw.auroc")
            slope = _get(study, "external_vitaldb", "models", model, "calibration", "joint_slope")
            median = _get(repeats, model, "auroc", "median")
            low = _get(repeats, model, "auroc", "p2_5")
            high = _get(repeats, model, "auroc", "p97_5")
            rows.append(f"| {endpoint_name} | {model_name} | {test:.3f} ({test_low:.3f}–{test_high:.3f}) "
                        f"| {median:.3f} ({low:.3f}–{high:.3f}) "
                        f"| {external:.3f} ({external_low:.3f}–{external_high:.3f}) | {slope:.3f} |")
    return "\n".join(rows)


def update(readme: Path, table: str) -> str:
    """Return the README text with the table placed between its markers."""
    text = readme.read_text()
    before, _, rest = text.partition(START)
    _, _, after = rest.partition(END)
    return f"{before}{START}\n{table}\n{END}{after}"


def main() -> None:
    """Write the table into README.md, or fail if it is stale with --check."""
    readme = ROOT / "README.md"
    updated = update(readme, render(ROOT / "results"))
    if "--check" in sys.argv:
        if updated != readme.read_text():
            raise SystemExit("README results table is stale; run make table.")
        return
    _ = readme.write_text(updated)


if __name__ == "__main__":
    main()
