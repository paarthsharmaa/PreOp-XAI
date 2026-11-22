"""Shared fixtures. API tests need local artifacts, so they skip where those are absent (for example in CI)."""

from collections.abc import Iterator

import pytest

import app  # noqa: F401
from pipeline.config import load_paths
from pipeline.model_artifacts import ENDPOINTS, artifacts_dir


@pytest.fixture(scope="session")
def client() -> Iterator[object]:
    if not all((artifacts_dir() / name / "metadata.json").is_file() for name in ENDPOINTS):
        pytest.skip("Model artifacts not found. Run `make export-models`.")
    if not load_paths().vitaldb_clinical.is_file():
        pytest.skip("VitalDB clinical table not found.")
    from fastapi.testclient import TestClient

    from app.api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
