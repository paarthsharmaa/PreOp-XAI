"""Request and response models, validated against the pipeline's plausibility ranges."""

from __future__ import annotations

import ast
import json
from typing import Annotated, Final, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

from pipeline.config import ROOT
from preopxai.preprocessing import LABS

UNITS: Final = {"age": "years", "hemoglobin": "g/dL", "platelets": "×10³/µL", "creatinine": "mg/dL", "bun": "mg/dL",
                "sodium": "mmol/L", "potassium": "mmol/L", "glucose": "mg/dL"}
LABELS: Final = {"age": "Age", "sex": "Sex", "asa": "ASA class", "hemoglobin": "Haemoglobin", "platelets": "Platelets",
                 "creatinine": "Creatinine", "bun": "BUN", "sodium": "Sodium", "potassium": "Potassium",
                 "glucose": "Glucose"}


def _lab_ranges() -> dict[str, tuple[float, float]]:
    """Read the plausibility limits from the pipeline script, which cannot be imported without running it."""
    tree = ast.parse((ROOT / "data_prep/mover_features.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "MAP":
            mapping = ast.literal_eval(node.value)
            return {lab: (float(mapping[lab][2]), float(mapping[lab][3])) for lab in LABS}
    raise RuntimeError("Plausibility map not found in data_prep/mover_features.py.")


def _age_range() -> tuple[float, float]:
    stats = json.loads((ROOT / "results/cohort/mover_feature_stats.json").read_text())
    return float(stats["age_min"]), float(stats["age_max"])


RANGES: Final = {"age": _age_range(), **_lab_ranges()}


def _number(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise PydanticCustomError("not_a_number", "must be a number")
    return value


Number = Annotated[float, BeforeValidator(_number)]


class PatientInput(BaseModel):
    """The ten study concepts. A lab left out or set to null is treated as missing, as in the study."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    age: Number
    sex: Literal["F", "M"]
    asa: Annotated[int, Field(strict=True, ge=1, le=5)]
    hemoglobin: Number | None = None
    platelets: Number | None = None
    creatinine: Number | None = None
    bun: Number | None = None
    sodium: Number | None = None
    potassium: Number | None = None
    glucose: Number | None = None

    @field_validator("age", *LABS)
    @classmethod
    def within_plausible_range(cls, value: float | None, info: ValidationInfo) -> float | None:
        name = str(info.field_name)
        low, high = RANGES[name]
        if value is not None and not low <= value <= high:
            raise PydanticCustomError("out_of_range", "{label} must be between {low} and {high} {unit}",
                                      {"label": LABELS[name], "low": f"{low:g}", "high": f"{high:g}",
                                       "unit": UNITS[name]})
        return value


class ConceptContribution(BaseModel):
    concept: str
    label: str
    contribution: float
    value_part: float
    missingness_part: float


class ModelPrediction(BaseModel):
    log_odds: float
    native_margin: float
    base_value: float
    calibrated_log_odds: float
    calibrated_probability: float
    threshold: float
    above_threshold: bool
    recalibration_intercept: float
    recalibration_slope: float
    shap: list[ConceptContribution]


class EndpointPrediction(BaseModel):
    lr: ModelPrediction
    xgboost: ModelPrediction


class PredictionResponse(BaseModel):
    scale: str
    notice: str
    mortality: EndpointPrediction
    icu: EndpointPrediction


class ExamplePatient(BaseModel):
    id: str
    label: str
    source: Literal["vitaldb", "synthetic"]
    description: str
    inputs: PatientInput
    has_outcome: bool


class PatientsResponse(BaseModel):
    notice: str
    attribution: str
    patients: list[ExamplePatient]


class ObservedOutcome(BaseModel):
    id: str
    mortality: bool
    icu: bool
