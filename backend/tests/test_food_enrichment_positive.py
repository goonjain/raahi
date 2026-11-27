import os
import json
from fastapi.testclient import TestClient
from backend.app.main import app

# Ensure the test environment sees the project root for imports
os.environ['PYTHONPATH'] = os.getcwd()

client = TestClient(app)

# Mock GroqWrapper.generate to return a single valid proposal
class MockGroq:
    @staticmethod
    def generate(prompt: str, response_schema: dict):
        # Return a list with a single valid proposal matching schema
        return [
            {
                "venue_id": None,
                "venue_name": "Traditional Rajasthani Thali",
                "meal_type": "lunch",
                "start_time": "12:30",
                "duration_min": 60,
                "nearby_attraction_id": "amber",
                "reason": "A traditional Rajasthani meal.",
                "evidence_refs": [
                    "https://www.tourism.rajasthan.gov.in/rajasthani-cuisine.html"
                ],
                "dietary": ["vegetarian"],
                "cost_estimate": None
            }
        ]

# Patch the GroqWrapper used in the router
from unittest.mock import patch

def test_enrich_food_positive():
    request_body = {
        "date": "2023-10-01",
        "attractions": [
            {
                "id": "amber",
                "start_time": "10:00",
                "end_time": "11:30"
            },
            {
                "id": "hawa",
                "start_time": "14:00",
                "end_time": "15:00"
            }
        ],
        "interests": ["history"],
        "food_preferences": ["local"],
        "dietary_preferences": ["vegetarian"],
        "budget_per_meal": 500
    }

    with patch(
        "backend.app.routers.itinerary_food.GroqWrapper.generate",
        return_value=MockGroq.generate("", {})
    ):
        response = client.post(
            "/itinerary/enrich-food",
            json=request_body
        )

    assert response.status_code == 200, response.text

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1

