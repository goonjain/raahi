import os
import json
import shutil
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.knowledge import ingest_record, KnowledgeRecord, _load_records, _save_records

client = TestClient(app)

# Path to the records file used by the service
RECORDS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "knowledge", "records.json"))

@pytest.fixture(autouse=True)
def isolate_records(tmp_path, monkeypatch):
    """Make a temporary copy of records.json for each test to avoid side effects."""
    # Ensure the original exists
    if not os.path.exists(RECORDS_PATH):
        # create an empty file if missing
        with open(RECORDS_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
    # Copy to a temp location
    temp_file = tmp_path / "records.json"
    shutil.copyfile(RECORDS_PATH, temp_file)
    # Point the service to the temp file by monkey‑patching the module constant
    monkeypatch.setattr("backend.app.services.knowledge.RECORDS_PATH", str(temp_file))
    # Reload records in the service (the module reads at import, but we force reload)
    # Reset the in‑memory records by re‑instantiating the retriever inside tests where needed
    yield
    # After test, no need to restore original because we never modified the real file

def test_ingest_and_search():
    # Ingest a new record
    new_record = {
        "attractionId": "testplace",
        "name": "Test Place",
        "description": "A wonderful place to test search functionality.",
        "interests": ["testing", "search"],
        "geo": {"lat": 1.23, "lng": 4.56},
        "sourceTitle": "Test Data",
        "sourceUrl": "https://example.com/test",
        "retrievedAt": datetime.utcnow().isoformat(),
        "verificationStatus": "verified",
    }
    rec: KnowledgeRecord = ingest_record(new_record)
    assert rec.attractionId == "testplace"

    # Use the API endpoint
    response = client.post("/knowledge/search", json={"query": "wonderful", "limit": 5})
    assert response.status_code == 200
    results = response.json()
    # At least one result should contain our test record
    ids = [r.get("attractionId") for r in results]
    assert "testplace" in ids
