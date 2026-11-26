import os
import json
from typing import List, Optional, Tuple
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services.knowledge import LexicalRetriever
from backend.app.services.groq_wrapper import GroqWrapper, GroqError
from backend.app.schemas import FoodProposal

router = APIRouter()

class AttractionInfo(BaseModel):
    id: str = Field(..., description="Attraction identifier")
    start_time: str = Field(..., description="HH:MM start time")
    end_time: str = Field(..., description="HH:MM end time")

class FoodEnrichmentRequest(BaseModel):
    date: str = Field(..., description="Travel date in YYYY-MM-DD")
    attractions: List[AttractionInfo]
    interests: Optional[List[str]] = None
    food_preferences: Optional[List[str]] = None
    dietary_preferences: Optional[List[str]] = None
    budget_per_meal: Optional[int] = None

def _build_query(req: FoodEnrichmentRequest) -> str:
    parts: List[str] = []
    parts.extend([f"attraction:{a.id}" for a in req.attractions])
    if req.interests:
        parts.extend(req.interests)
    if req.food_preferences:
        parts.extend(req.food_preferences)
    if req.dietary_preferences:
        parts.extend(req.dietary_preferences)
    parts.append("food")
    return " ".join(parts)

def _collect_evidence(retriever: LexicalRetriever, query: str) -> List[dict]:
    return retriever.search(query, limit=10)

def _load_restaurants() -> dict:
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "food", "restaurants.json"))
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {item["id"]: item for item in data}

def _time_to_minutes(t: str) -> int:
    hh, mm = map(int, t.split(":"))
    return hh * 60 + mm

def _validate_proposal(
    proposal: FoodProposal,
    req: FoodEnrichmentRequest,
    evidence_urls: List[str],
    restaurant_index: dict,
    used_slots: List[Tuple[int, int]],
) -> Optional[FoodProposal]:
    # 1. venue_id check
    if proposal.venue_id:
        if proposal.venue_id.startswith("restaurant:"):
            rid = proposal.venue_id.split(":", 1)[1]
            if rid not in restaurant_index:
                return None
        elif proposal.venue_id.startswith("food:"):
            # ok – generic food experience
            pass
        else:
            return None
    # 2. nearby_attraction_id must be one of the requested attractions
    if proposal.nearby_attraction_id and proposal.nearby_attraction_id not in {a.id for a in req.attractions}:
        return None
    # 3. dietary compliance – must contain all requested tags (no implicit conversion)
    if req.dietary_preferences:
        prop_tags = set(proposal.dietary or [])
        if not set(req.dietary_preferences).issubset(prop_tags):
            return None
    # 4. evidence_refs must be subset of retrieved URLs
    if not set(proposal.evidence_refs).issubset(set(evidence_urls)):
        return None
    # 5. cost_estimate must be empty – cannot invent price
    if proposal.cost_estimate:
        return None
    # 6. time slot must lie within overall day window and not overlap attractions or other meals
    start_min = _time_to_minutes(proposal.start_time)
    end_min = start_min + proposal.duration_min
    day_start = min(_time_to_minutes(a.start_time) for a in req.attractions)
    day_end = max(_time_to_minutes(a.end_time) for a in req.attractions)
    if start_min < day_start or end_min > day_end:
        return None
    # overlap with attractions
    for a in req.attractions:
        a_start = _time_to_minutes(a.start_time)
        a_end = _time_to_minutes(a.end_time)
        if not (end_min <= a_start or start_min >= a_end):
            return None
    # overlap with already accepted meals
    for s, e in used_slots:
        if not (end_min <= s or start_min >= e):
            return None
    used_slots.append((start_min, end_min))
    return proposal

@router.post("/itinerary/enrich-food", response_model=List[FoodProposal])
async def enrich_food(req: FoodEnrichmentRequest):
    try:
        retriever = LexicalRetriever()
        query = _build_query(req)
        evidence = _collect_evidence(retriever, query)
        evidence_str = "\n".join(
            f"- [{e['sourceTitle']}] {e['snippet']} (source: {e['sourceUrl']})" for e in evidence
        )
        prompt = (
            f"You are a helpful assistant that proposes food experiences for a Jaipur itinerary.\n"
            f"Date: {req.date}\n"
            f"Attractions (id, start‑end): "
            + ", ".join([f"{a.id} ({a.start_time}-{a.end_time})" for a in req.attractions])
            + "\n"
            f"Interests: {', '.join(req.interests or [])}\n"
            f"Food preferences: {', '.join(req.food_preferences or [])}\n"
            f"Dietary preferences: {', '.join(req.dietary_preferences or [])}\n"
            f"Budget per meal: {req.budget_per_meal if req.budget_per_meal is not None else 'unspecified'}\n"
            f"Evidence:\n{evidence_str}\n"
            f"Provide a JSON array of food proposals, each matching the FoodProposal schema.\n"
            f"Do not invent venues or data not present in the evidence."
        )
        schema = FoodProposal.schema()
        raw = GroqWrapper.generate(prompt, response_schema=schema)
        if not isinstance(raw, list):
            raise ValueError("Groq response must be a list")
        restaurant_index = _load_restaurants()
        evidence_urls = [e["sourceUrl"] for e in evidence]
        used_slots: List[Tuple[int, int]] = []
        valid: List[FoodProposal] = []
        for item in raw:
            try:
                proposal = FoodProposal(**item)
            except Exception:
                continue
            vp = _validate_proposal(proposal, req, evidence_urls, restaurant_index, used_slots)
            if vp:
                valid.append(vp)
        return valid
    except GroqError as ge:
        raise HTTPException(status_code=503, detail=str(ge))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
