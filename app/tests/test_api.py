"""API schema, validation, SHAP additivity and determinism."""

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

from app.api.schemas import RANGES
from pipeline.config import load_paths
from pipeline.model_artifacts import ENDPOINTS, MODELS, artifacts_dir
from preopxai.preprocessing import FEATURES, LABS

BASE = {
    "age": 64,
    "sex": "F",
    "asa": 3,
    "hemoglobin": 12.1,
    "platelets": 210,
    "creatinine": 1.1,
    "bun": 18,
    "sodium": 139,
    "potassium": 4.2,
    "glucose": 110,
}


def predictions(body):
    return [body[endpoint][model] for endpoint in ENDPOINTS for model in MODELS]


def inputs(client):
    rng = np.random.default_rng(2026)
    cases = [patient["inputs"] for patient in client.get("/patients").json()["patients"]]
    for _ in range(25):
        case = {
            "age": float(rng.uniform(*RANGES["age"])),
            "sex": str(rng.choice(["F", "M"])),
            "asa": int(rng.integers(1, 6)),
        }
        for lab in LABS:
            case[lab] = None if rng.random() < 0.4 else float(rng.uniform(*RANGES[lab]))
        cases.append(case)
    return cases


def test_predict_schema(client):
    response = client.post("/predict", json=BASE)
    assert response.status_code == 200
    body = response.json()
    assert "not for clinical use" in body["notice"]
    for item in predictions(body):
        assert [row["concept"] for row in item["shap"]] == list(FEATURES)
        assert 0 < item["calibrated_probability"] < 1
        assert item["above_threshold"] == (item["calibrated_probability"] >= item["threshold"])


def test_shap_additivity_within_1e_6(client):
    for case in inputs(client):
        for item in predictions(client.post("/predict", json=case).json()):
            total = item["base_value"] + sum(row["contribution"] for row in item["shap"])
            assert abs(total - item["log_odds"]) <= 1e-6


def test_concept_contribution_is_value_plus_missingness(client):
    body = client.post("/predict", json={"age": 70, "sex": "M", "asa": 4}).json()
    for item in predictions(body):
        for row in item["shap"]:
            assert row["contribution"] == pytest.approx(row["value_part"] + row["missingness_part"], abs=1e-12)


def test_probability_uses_study_recalibration(client):
    for item in predictions(client.post("/predict", json=BASE).json()):
        logit = item["recalibration_intercept"] + item["recalibration_slope"] * item["native_margin"]
        assert item["calibrated_probability"] == pytest.approx(float(expit(logit)), abs=1e-9)
        assert abs(item["log_odds"] - item["native_margin"]) < 1e-4


def test_predict_is_deterministic(client):
    first = client.post("/predict", json=BASE).content
    assert all(client.post("/predict", json=BASE).content == first for _ in range(5))


def test_missing_labs_are_accepted(client):
    assert client.post("/predict", json={"age": 50, "sex": "M", "asa": 2}).status_code == 200
    assert client.post("/predict", json={**BASE, "sodium": None}).status_code == 200


@pytest.mark.parametrize("name", ["age", *LABS])
def test_range_limits(client, name):
    low, high = RANGES[name]
    assert client.post("/predict", json={**BASE, name: low}).status_code == 200
    assert client.post("/predict", json={**BASE, name: high}).status_code == 200
    response = client.post("/predict", json={**BASE, name: high + 1})
    assert response.status_code == 422
    detail = response.json()["detail"][0]
    assert detail["field"] == name and "must be between" in detail["message"]


@pytest.mark.parametrize(
    "change",
    [
        {"asa": 6},
        {"asa": 0},
        {"asa": "3"},
        {"asa": 2.5},
        {"sex": "X"},
        {"age": None},
        {"age": "60"},
        {"sodium": "high"},
        {"glucose": True},
        {"extra": 1},
    ],
)
def test_invalid_inputs_are_rejected(client, change):
    assert client.post("/predict", json={**BASE, **change}).status_code == 422


def test_patients_are_vitaldb_or_synthetic_and_hide_outcomes(client):
    body = client.get("/patients").json()
    assert "CC BY 4.0" in body["attribution"]
    assert {patient["source"] for patient in body["patients"]} == {"vitaldb", "synthetic"}
    for patient in body["patients"]:
        assert not {"mortality", "icu", "outcome"} & set(patient)
        status = client.get(f"/patients/{patient['id']}/outcome").status_code
        assert status == (200 if patient["has_outcome"] else 404)


def test_patients_contain_no_background_rows(client):
    served = client.get("/patients").json()["patients"]
    for endpoint in ENDPOINTS:
        background = pd.read_csv(artifacts_dir() / endpoint / "background.csv", dtype={"sex": str, "asa": str})
        rows = {
            tuple(None if pd.isna(value) else float(value) for value in row)
            for row in background[["age", *LABS]].itertuples(index=False)
        }
        for patient in served:
            case = patient["inputs"]
            assert tuple(None if case[k] is None else float(case[k]) for k in ("age", *LABS)) not in rows


def test_synthetic_profiles_match_no_mover_row(client):
    table = load_paths().tables / "mover_analysis.csv"
    if not table.is_file():
        pytest.skip("MOVER analysis table not found.")
    mover = pd.read_csv(table, dtype={"sex": str, "asa": str})
    for patient in client.get("/patients").json()["patients"]:
        if patient["source"] != "synthetic":
            continue
        case = patient["inputs"]
        match = (mover["age"] == case["age"]) & (mover["sex"] == case["sex"]) & (mover["asa"] == str(case["asa"]))
        for lab in LABS:
            match &= mover[lab].isna() if case[lab] is None else mover[lab] == case[lab]
        assert not match.any(), patient["id"]
