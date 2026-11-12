"""
backend/tests/test_api.py — JalDrishti FastAPI Endpoint Tests
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify system root endpoint returns JalDrishti service status."""
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "JalDrishti"
    assert data["status"] == "running"
    assert "CGWB Problem Statement #25068" in data["description"]


def test_health_endpoint():
    """Verify /api/health returns valid service payload."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "JalDrishti API v1"
    assert "data_mode" in data
