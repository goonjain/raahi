import json
from typing import List, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.services.knowledge import LexicalRetriever

router = APIRouter()

class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    attractionId: Optional[str] = None

@router.post("/knowledge/search", response_model=List[Any])
async def search(req: SearchRequest):
    try:
        retriever = LexicalRetriever()  # instantiate per request to pick up latest records
        results = retriever.search(req.query, limit=req.limit, attraction_id=req.attractionId)
        return results
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

