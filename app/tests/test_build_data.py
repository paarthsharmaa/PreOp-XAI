"""Every number on the site must trace back to a committed results file."""

import json
from pathlib import Path
import re
from typing import Any

import pandas as pd
import pytest

from app.build_data import OPS, SMALL_CELL, Sources, build, compact
from pipeline.config import ROOT
from pipeline.model_artifacts import ENDPOINTS, artifacts_dir
from preopxai.preprocessing import LABS

WEB = ROOT / "app/web"
ALLOWED_SOURCE = ("results/", "verification/")


@pytest.fixture(scope="module")
def built() -> tuple[dict[str, Any], dict[str, Any]]:
    return build()


def resolve(src: Sources, spec: dict[str, Any]) -> Any:
    if "op" in spec:
        return OPS[spec["op"]](*[resolve(src, arg) for arg in spec["args"]])
    assert spec["ref"].startswith(ALLOWED_SOURCE), spec["ref"]
    value = src.lookup(spec["ref"])
    return len(value) if isinstance(value, list) else value


def leaves(node: Any, path: str = "") -> list[tuple[str, Any]]:
    if isinstance(node, dict):
        return [item for key, value in node.items() for item in leaves(value, f"{path}/{key}")]
    if isinstance(node, list):
        return [item for index, value in enumerate(node) for item in leaves(value, f"{path}/{index}")]
    return [(path, node)]


def test_every_number_has_a_source(built):
    site, provenance = built
    series = tuple(f"{path}/" for path, spec in provenance.items() if "indices" in spec)
    numbers = [
        (path, value) for path, value in leaves(site) if isinstance(value, int | float) and not isinstance(value, bool)
    ]
    assert numbers
    untraced = [path for path, _ in numbers if path not in provenance and not path.startswith(series)]
    assert untraced == []


def test_every_value_equals_its_source(built):
    site, provenance = built
    src = Sources()
    flat = dict(leaves(site))
    for path, spec in provenance.items():
        if "template" in spec:
            args = {key: format(resolve(src, value), value["format"]) for key, value in spec["args"].items()}
            assert flat[path] == spec["template"].format(**args), path
        elif "indices" in spec:
            values = src.lookup(spec["ref"])
            picked = [values[i] for i in spec["indices"]] if spec["indices"] is not None else values
            assert [flat[f"{path}/{i}"] for i in range(len(picked))] == [compact(item) for item in picked], path
        elif spec.get("masked"):
            assert flat[path] == f"<{SMALL_CELL}" and 0 < src.lookup(spec["ref"]) < SMALL_CELL, path
        else:
            assert flat[path] == compact(resolve(src, spec)), path


def test_small_mover_counts_are_masked():
    src = Sources()
    src._cache["results/x.json"] = {"small": 9, "zero": 0, "large": 11}
    assert src.count("results/x.json", "small").__class__.__name__ == "Masked"
    assert src.count("results/x.json", "zero").value == 0
    assert src.count("results/x.json", "large").value == 11


def test_site_has_no_operating_point_counts(built):
    names = {path.rsplit("/", 1)[-1] for path, _ in leaves(built[0])}
    assert not names & {"tp", "fp", "tn", "fn"}


def published_files() -> list[Path]:
    roots = [WEB / "public/data", WEB / "dist", WEB / "dist-static"]
    return [path for root in roots if root.is_dir() for path in root.rglob("*") if path.is_file()]


def test_no_patient_level_file_types_in_web_output():
    forbidden = {".csv", ".joblib", ".npz", ".npy", ".pkl", ".pickle", ".parquet"}
    assert not [path for path in published_files() if path.suffix.lower() in forbidden]


def numeric_groups(node: Any) -> list[set[float]]:
    """The numbers held directly by each JSON object or array."""
    if isinstance(node, dict):
        children = list(node.values())
    elif isinstance(node, list):
        children = node
    else:
        return []
    own = {float(item) for item in children if isinstance(item, int | float) and not isinstance(item, bool)}
    return [own, *[group for child in children for group in numeric_groups(child)]]


def test_no_mover_background_row_in_web_output():
    if not all((artifacts_dir() / name / "background.csv").is_file() for name in ENDPOINTS):
        pytest.skip("Model artifacts not found.")
    files = [path for path in published_files() if path.suffix == ".json"]
    assert files, "Run `uv run preopxai app build` first."
    groups = [group for path in files for group in numeric_groups(json.loads(path.read_text())) if len(group) >= 2]
    for endpoint in ENDPOINTS:
        background = pd.read_csv(artifacts_dir() / endpoint / "background.csv")
        for row in background[["age", *LABS]].itertuples(index=False):
            values = {float(value) for value in row if not pd.isna(value)}
            # Rows without labs hold one number, which cannot identify a row in aggregate output.
            if len(values) >= 3:
                assert not any(values <= group for group in groups)


def test_frontend_has_no_typed_numbers_in_visible_text():
    sources = sorted((WEB / "src").rglob("*.tsx"))
    assert sources
    pattern = re.compile(r">\s*([^<>{}=;()&|?]*\d[^<>{}=;()&|?]*?)\s*<")
    attribute = re.compile(r"\b(?:title|takeaway|note|eyebrow)=\"([^\"]*\d[^\"]*)\"")
    found = []
    for path in sources:
        text = path.read_text()
        for match in [*pattern.finditer(text), *attribute.finditer(text)]:
            if match.group(1).replace("Lag-0", "").strip() and re.search(r"\d", match.group(1).replace("Lag-0", "")):
                found.append(f"{path.name}: {match.group(1).strip()}")
    assert found == []
