import json
from fastapi.testclient import TestClient
import pytest
from backend.app.main import app
from backend.app.schemas import ItineraryAIRequest, Proposal, ItineraryAIResponse
from backend.app.services.groq_wrapper import GroqError

client = TestClient(app)

# Helper request data
valid_req = {
    "startDate": "2024-01-01",
    "endDate": "2024-01-03",
    "locationType": "city",
    "customLocation": None,
    "interests": ["heritage", "photography"],
    "mustVisit": ["amber", "hawa"],
    "foodPreference": "vegetarian",
    "dietaryRestrictions": "vegetarian",
    "groupType": "family",
    "groupSize": 4,
    "budget": 2000,
    "travelPace": "relaxed",
    "crowdTolerance": "moderate",
    "hiddenGemsPreference": "high"
}

# Mock data for restaurant index file – assume file contains a restaurant with id "rest1"
mock_restaurant_index = {"rest1": {"id": "rest1", "name": "Test Restaurant"}}

# Mock evidence list
mock_evidence = [{"sourceTitle": "Title", "snippet": "Snippet", "sourceUrl": "http://example.com"}]

def mock_load_restaurants():
    return mock_restaurant_index

def mock_search(self, query, limit=10):
    return mock_evidence

@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch):
    # Patch restaurant loader used in router
    monkeypatch.setattr("backend.app.routers.itinerary_ai._load_restaurants", lambda: mock_restaurant_index)
    # Patch LexicalRetriever.search
    from backend.app.services.knowledge import LexicalRetriever
    monkeypatch.setattr(LexicalRetriever, "search", mock_search)
    yield

def test_valid_proposal(monkeypatch):
    # Groq returns a valid proposal matching schemas and IDs
    proposal = {
        "attraction_ids": ["amber", "hawa"],
        "restaurant_ids": ["restaurant:rest1"],
        "reason": "Close to attractions",
        "evidence_refs": ["http://example.com"]
    }
    monkeypatch.setattr("backend.app.routers.itinerary_ai.GroqWrapper.generate", lambda prompt, response_schema=None: [proposal])
    resp = client.post("/v1/itinerary/recommendations", json=valid_req)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict) and "proposals" in data
    assert len(data["proposals"]) == 1
    assert data["proposals"][0]["reason"] == "Close to attractions"

def test_invalid_attraction_filtered(monkeypatch):
    # Proposal includes an unknown attraction ID
    proposal = {
        "attraction_ids": ["unknown"],
        "restaurant_ids": ["restaurant:rest1"],
        "reason": "Invalid attraction",
        "evidence_refs": ["http://example.com"]
    }
    monkeypatch.setattr("backend.app.routers.itinerary_ai.GroqWrapper.generate", lambda prompt, response_schema=None: [proposal])
    resp = client.post("/v1/itinerary/recommendations", json=valid_req)
    assert resp.status_code == 200
    assert resp.json()["proposals"] == []

def test_invalid_restaurant_filtered(monkeypatch):
    # Proposal includes restaurant ID not in index
    proposal = {
        "attraction_ids": ["amber"],
        "restaurant_ids": ["restaurant:missing"],
        "reason": "Missing restaurant",
        "evidence_refs": ["http://example.com"]
    }
    monkeypatch.setattr("backend.app.routers.itinerary_ai.GroqWrapper.generate", lambda prompt, response_schema=None: [proposal])
    resp = client.post("/v1/itinerary/recommendations", json=valid_req)
    assert resp.status_code == 200
    assert resp.json()["proposals"] == []

def test_groq_error(monkeypatch):
    def raise_error(prompt, response_schema=None):
        raise GroqError("service unavailable")
    monkeypatch.setattr("backend.app.routers.itinerary_ai.GroqWrapper.generate", raise_error)
    resp = client.post("/v1/itinerary/recommendations", json=valid_req)
    assert resp.status_code == 503
    assert "service unavailable" in resp.text

def test_nonlist_response(monkeypatch):
    monkeypatch.setattr("backend.app.routers.itinerary_ai.GroqWrapper.generate", lambda prompt, response_schema=None: {"foo": "bar"})
    resp = client.post("/v1/itinerary/recommendations", json=valid_req)
    assert resp.status_code == 400
    assert "list" in resp.text.lower()

