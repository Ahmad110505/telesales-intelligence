"""
Integration tests for FastAPI headless endpoints.
"""

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.db.session import get_db


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "cohere_model" in data


def test_analyze_and_retrieve_call(client, sample_jordanian_transcript):
    payload = {
        "call_id": "CALL-API-001",
        "agent_id": "AGT-OMAR-04",
        "call_objective": "fiber_subscription_upgrade",
        "transcript": sample_jordanian_transcript,
        "source": "http_api"
    }

    # 1. Analyze call via POST /calls/analyze
    post_resp = client.post("/calls/analyze", json=payload)
    assert post_resp.status_code == 201
    analysis_data = post_resp.json()
    assert analysis_data["call_id"] == "CALL-API-001"
    assert "assessment" in analysis_data

    # 2. Retrieve call analysis via GET /calls/{call_id}
    get_resp = client.get("/calls/CALL-API-001")
    assert get_resp.status_code == 200
    assert get_resp.json()["call_id"] == "CALL-API-001"

    # 3. Retrieve dashboard-ready data via GET /calls/{call_id}/dashboard-data
    dash_resp = client.get("/calls/CALL-API-001/dashboard-data")
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert dash_data["call_id"] == "CALL-API-001"
    assert "kpis" in dash_data
    assert "transcript_raw" in dash_data


def test_review_status_update(client, sample_jordanian_transcript):
    # Ingest call first
    client.post("/calls/analyze", json={
        "call_id": "CALL-REVIEW-001",
        "transcript": sample_jordanian_transcript
    })

    # Update review status
    review_payload = {
        "finding_type": "assessment",
        "finding_id": "CALL-REVIEW-001",
        "new_status": "accepted",
        "reviewer_notes": "Supervisor reviewed and confirmed high quality handling."
    }
    resp = client.post("/calls/CALL-REVIEW-001/review", json=review_payload)
    assert resp.status_code == 200
    assert resp.json()["new_status"] == "accepted"
