"""FastAPI app. Run through `make app`; it binds to localhost and must not be deployed publicly."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.engine import NOTICE, Engine
from app.api.patients import ATTRIBUTION, PatientStore
from app.api.patients import NOTICE as PATIENT_NOTICE
from app.api.schemas import (
    LABELS,
    RANGES,
    UNITS,
    ObservedOutcome,
    PatientInput,
    PatientsResponse,
    PredictionResponse,
)
from pipeline.config import load_paths


async def _validation_error(_: Request, error: Exception) -> JSONResponse:
    """Return one clear message per field, without echoing the submitted values."""
    assert isinstance(error, RequestValidationError)
    details = [
        {"field": ".".join(str(part) for part in item["loc"] if part != "body"), "message": item["msg"]}
        for item in error.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


def create_app() -> FastAPI:
    """Load the models and example patients once."""
    engine = Engine()
    store = PatientStore(load_paths().vitaldb_clinical)
    app = FastAPI(title="PreOp-XAI research API", description=NOTICE, version="0.1.0")
    app.add_exception_handler(RequestValidationError, _validation_error)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "notice": NOTICE}

    @app.get("/meta")
    def meta() -> dict[str, object]:
        return {
            "notice": NOTICE,
            "labels": LABELS,
            "units": UNITS,
            "ranges": {name: {"min": low, "max": high} for name, (low, high) in RANGES.items()},
        }

    @app.post("/predict")
    def predict(patient: PatientInput) -> PredictionResponse:
        return engine.predict(patient)

    @app.get("/patients")
    def patients() -> PatientsResponse:
        return PatientsResponse(notice=PATIENT_NOTICE, attribution=ATTRIBUTION, patients=store.patients)

    @app.get("/patients/{patient_id}/outcome")
    def outcome(patient_id: str) -> ObservedOutcome:
        if patient_id not in store.outcomes:
            raise HTTPException(status_code=404, detail="No observed outcome for this patient.")
        return store.outcomes[patient_id]

    return app
