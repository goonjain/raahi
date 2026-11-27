
import os
import json
from typing import List
from fastapi import APIRouter, HTTPException

from backend.app.services.knowledge import LexicalRetriever
from backend.app.services.groq_wrapper import GroqWrapper, GroqError
from backend.app.schemas import ItineraryAIRequest, ItineraryAIResponse, Proposal
from backend.app.data.canonical_destinations import CANONICAL_DESTINATIONS

router = APIRouter()

# Helper to load restaurant index (reuse logic from itinerary_food)
def _load_restaurants() -> dict:
    path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "food", "restaurants.json"
        )
    )
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {item["id"]: item for item in data}

def _build_query(req: ItineraryAIRequest) -> str:
    parts: List[str] = []
    parts.append(req.locationType)
    if req.customLocation:
        parts.append(req.customLocation)
    parts.extend(req.interests)
    parts.extend(req.mustVisit)
    parts.append("itinerary")
    parts.append(req.foodPreference)
    if req.dietaryRestrictions:
        parts.append(req.dietaryRestrictions)
    # Include additional notes if provided to guide recommendations
    if getattr(req, 'notesStep1', None):
        parts.append(req.notesStep1)
    if getattr(req, 'notesStep2', None):
        parts.append(req.notesStep2)
    if getattr(req, 'notesStep3', None):
        parts.append(req.notesStep3)
    if getattr(req, 'notesStep4', None):
        parts.append(req.notesStep4)
    return " ".join(parts)

def _validate_proposal(
    proposal: Proposal,
    req: ItineraryAIRequest,
    evidence_urls: List[str],
    restaurant_index: dict,
) -> bool:
    # attraction ids must exist
    canonical_ids = {d["id"] for d in CANONICAL_DESTINATIONS}
    if not set(proposal.attraction_ids).issubset(canonical_ids):
        return False
    # restaurant ids must exist and start with expected prefix (restaurant:)
    for rid in proposal.restaurant_ids:
        if not rid.startswith("restaurant:"):
            return False
        real_id = rid.split(":", 1)[1]
        if real_id not in restaurant_index:
            return False
    # evidence refs must be subset of URLs
    if not set(proposal.evidence_refs).issubset(set(evidence_urls)):
        return False
    # basic non‑empty reason
    if not proposal.reason:
        return False
    return True

@router.post("/v1/itinerary/recommendations", response_model=ItineraryAIResponse)
async def recommend_itinerary(req: ItineraryAIRequest):
    try:
        retriever = LexicalRetriever()
        query = _build_query(req)
        evidence = retriever.search(query, limit=10)
        evidence_str = "\n".join(
            f"- [{e['sourceTitle']}] {e['snippet']} (source: {e['sourceUrl']})" for e in evidence
        )
        canonical_attractions = [
            {"id": d["id"], "name": d.get("name", d["id"])}
            for d in CANONICAL_DESTINATIONS
        ]

        allowed_attractions = json.dumps(
            canonical_attractions,
            ensure_ascii=False
)
        prompt = (
            "You are an AI assistant that recommends attractions for a Jaipur itinerary.\n"
            f"User request: {req.model_dump_json()}\n"
            f"Allowed attraction IDs and names:\n{allowed_attractions}\n"
            f"Evidence:\n{evidence_str}\n"
            "Return a JSON object with exactly one top-level key named "
            "'proposals', containing an array of objects.\n"
            "Each proposal must contain attraction_ids, restaurant_ids, "
            "reason and evidence_refs.\n"
            "Use only attraction IDs from the allowed list.\n"
            "Use an empty restaurant_ids list if no eligible restaurant IDs are provided.\n"
            "Use only evidence source URLs provided above; otherwise use an empty evidence_refs list.\n"
            "Do not invent facts or IDs."
        )
        schema = Proposal.schema()
        raw = GroqWrapper.generate(prompt, response_schema=schema)
        if not isinstance(raw, list):
            raise ValueError("Groq response must be a list")
        restaurant_index = _load_restaurants()
        evidence_urls = [e["sourceUrl"] for e in evidence]
        valid: List[Proposal] = []

        for item in raw:
            try:
                prop = Proposal(**item)
            except Exception:
                 continue

            if _validate_proposal(
                prop, req, evidence_urls, restaurant_index
    ):
                valid.append(prop)

        return ItineraryAIResponse(proposals=valid)

    except GroqError as ge:
        raise HTTPException(status_code=503, detail=str(ge))

    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
