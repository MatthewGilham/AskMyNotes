"""Tests for the health route."""

from pathlib import Path

from fastapi.testclient import TestClient
from helpers import build_app


def test_health_endpoint_reports_ok(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
