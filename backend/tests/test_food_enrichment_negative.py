import os
import json
from fastapi.testclient import TestClient
from backend.app.main import app
from unittest.mock import patch

# Ensure project root is in PYTHONPATH for imports during tests
os.environ['PYTHONPATH'] = os.getcwd()

client = TestClient(app)

# Mock GeminiWrapper to return a mix of valid and invalid proposals
class MockGemini:
    @staticmethod
    def generate(prompt: str, response_schema: dict):
        # The order of items does not matter; the router will filter out the invalid ones.
        return [
            # 1. Invalid venue_id (restaurant that does not exist)
            {
                "venue_id": "restaurant:nonexistent_id",
                "nearby_attraction_id": "amber",
                "meal_type": "lunch",
                "start_time": "12:00",
                "duration_min": 60,
                "dietary": ["vegetarian"],
                "evidence_refs": ["https://example.com/evidence"],
                "cost_estimate": None,
                "venue_name": "Traditional Rajasthani Thali",
                "reason": "Some reason",
            },
            # 2. nearby_attraction_id not in request
            {
                "venue_id": "food:rajasthani_thali",
                "nearby_attraction_id": "unknown_attraction",
                "meal_type": "lunch",
                "start_time": "12:30",
                "duration_min": 60,
                "dietary": ["vegetarian"],
                "evidence_refs": ["https://www.tourism.rajasthan.gov.in/rajasthani-cuisine.html"],
                "cost_estimate": None,
                "venue_name": "Traditional Rajasthani Thali",
                "reason": "Some reason",
            },
            # 3. Dietary mismatch (request wants vegan, proposal only vegetarian)
            {
                "venue_id": "food:vegan_salad",
                "nearby_attraction_id": "amber",
                "meal_type": "snack",
                "start_time": "11:00",
                "duration_min": 30,
                "dietary": ["vegetarian"],
                "evidence_refs": ["https://example.com/evidence"],
                "cost_estimate": None,
                "venue_name": "Traditional Rajasthani Thali",
                "reason": "Some reason",
            },
            # 4. Evidence reference not in retrieved evidence URLs
            {
                "venue_id": "food:rajasthani_thali",
                "nearby_attraction_id": "amber",
                "meal_type": "lunch",
                "start_time": "13:00",
                "duration_min": 60,
                "dietary": ["vegetarian"],
                "evidence_refs": ["https://not-retrieved.example.com"],
                "cost_estimate": None,
                "venue_name": "Traditional Rajasthani Thali",
                "reason": "Some reason",
            },
            # 5. Cost estimate invented
            {
                "venue_id": "food:rajasthani_thali",
                "nearby_attraction_id": "amber",
                "meal_type": "lunch",
                "start_time": "14:00",
                "duration_min": 60,
                "dietary": ["vegetarian"],
                "evidence_refs": ["https://www.tourism.rajasthan.gov.in/rajasthani-cuisine.html"],
                "cost_estimate": 1000,
                "venue_name": "Traditional Rajasthani Thali",
                "reason": "Some reason",
            },
            # 6. Time overlaps an attraction (amber 10:00-11:30)
            {
                "venue_id": "food:rajasthani_thali",
                "nearby_attraction_id": "amber",
                "meal_type": "snack",
                "start_time": "10:30",
                "duration_min": 30,
                "dietary": ["vegetarian"],
                "evidence_refs": ["https://www.tourism.rajasthan.gov.in/rajasthani-cuisine.html"],
                "cost_estimate": None,
                "venue_name": "Traditional Rajasthani Thali",
                "reason": "Some reason",    
            },
            # 7. Time outside overall day window (last attraction ends 15:00, proposal starts 16:00)
            {
                "venue_id": "food:rajasthani_thali",
                "nearby_attraction_id": "amber",
                "meal_type": "dinner",
                "start_time": "16:00",
                "duration_min": 60,
                "dietary": ["vegetarian"],
                "evidence_refs": ["https://www.tourism.rajasthan.gov.in/rajasthani-cuisine.html"],
                "cost_estimate": None,
                "venue_name": "Traditional Rajasthani Thali",
                "reason": "Some reason",
            },
            # 8. Overlaps another accepted meal (we will provide a second valid proposal later)
            {
                "venue_id": "food:rajasthani_thali",
                "nearby_attraction_id": "amber",
                "meal_type": "lunch",
                "start_time": "12:30",
                "duration_min": 60,
                "dietary": ["vegetarian"],
                "evidence_refs": ["https://www.tourism.rajasthan.gov.in/rajasthani-cuisine.html"],
                "cost_estimate": None,
                "venue_name": "Traditional Rajasthani Thali",
                "reason": "Some reason",
            },
            # 9. Second valid proposal that conflicts with the first (same time)
            {
                "venue_id": "food:rajasthani_thali",
                "nearby_attraction_id": "amber",
                "meal_type": "snack",
                "start_time": "12:45",
                "duration_min": 30,
                "dietary": ["vegetarian"],
                "evidence_refs": ["https://www.tourism.rajasthan.gov.in/rajasthani-cuisine.html"],
                "cost_estimate": None,
                "venue_name": "Traditional Rajasthani Thali",
                "reason": "Some reason",
            },
        ]

# Patch GeminiWrapper used in the router

def test_enrich_food_negative_filters():
    request_body = {
        "date": "2023-10-01",
        "attractions": [
            {"id": "amber", "start_time": "10:00", "end_time": "11:30"},
            {"id": "hawa", "start_time": "14:00", "end_time": "15:00"},
        ],
        "interests": ["history"],
        "food_preferences": ["local"],
        "dietary_preferences": ["vegetarian"],
        "budget_per_meal": 500,
    }
    with patch(
        "backend.app.routers.itinerary_food.GroqWrapper.generate",
        return_value=MockGemini.generate("", {})
        ):
        response = client.post(
            "/itinerary/enrich-food",
            json=request_body
    )
    assert response.status_code == 200
    data = response.json()
    # Only the first valid proposal (item 8) should survive; the overlapping second (item 9) is filtered out
    assert isinstance(data, list)
    assert len(data) == 1
    proposal = data[0]
    assert proposal["venue_id"] == "food:rajasthani_thali"
    assert proposal["nearby_attraction_id"] == "amber"
    assert proposal["start_time"] == "12:30"
    # Ensure that dietary includes the requested preference
    assert "vegetarian" in proposal["dietary"]

