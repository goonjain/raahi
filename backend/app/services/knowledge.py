import json
import os
import re
import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator

# Path to the JSON store – relative to project root
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "knowledge"))
RECORDS_PATH = os.path.join(DATA_DIR, "records.json")

# Ensure the directory exists at import time
os.makedirs(DATA_DIR, exist_ok=True)

class KnowledgeRecord(BaseModel):
    attractionId: str = Field(..., alias="attractionId")
    name: str
    description: str
    interests: List[str]
    geo: Dict[str, float]
    openingHours: Optional[str] = None
    ticketPrice: Optional[int] = None
    accessibility: Optional[str] = None
    restrictions: Optional[str] = None
    visitDuration: Optional[str] = None
    sourceTitle: str
    sourceUrl: str
    retrievedAt: datetime.datetime
    verificationStatus: str
    # New optional metadata – does not affect existing callers
    category: Optional[str] = None
    dietary: Optional[List[str]] = None

    @validator("verificationStatus")
    def _verify_status(cls, v):
        if v not in {"verified", "unverified"}:
            raise ValueError("verificationStatus must be 'verified' or 'unverified'")
        return v

    @validator("retrievedAt", pre=True)
    def _parse_dt(cls, v):
        if isinstance(v, str):
            return datetime.datetime.fromisoformat(v)
        return v

    class Config:
        allow_population_by_field_name = True
        extra = "allow"
    attractionId: str = Field(..., alias="attractionId")
    name: str
    description: str
    interests: List[str]
    geo: Dict[str, float]
    openingHours: Optional[str] = None
    ticketPrice: Optional[int] = None
    accessibility: Optional[str] = None
    restrictions: Optional[str] = None
    visitDuration: Optional[str] = None
    sourceTitle: str
    sourceUrl: str
    retrievedAt: datetime.datetime
    verificationStatus: str

    @validator("verificationStatus")
    def _verify_status(cls, v):
        if v not in {"verified", "unverified"}:
            raise ValueError("verificationStatus must be 'verified' or 'unverified'")
        return v

    @validator("retrievedAt", pre=True)
    def _parse_dt(cls, v):
        if isinstance(v, str):
            return datetime.datetime.fromisoformat(v)
        return v

    class Config:
        allow_population_by_field_name = True

def _load_records() -> List[KnowledgeRecord]:
    records = []
    # Load main attraction records
    if os.path.exists(RECORDS_PATH):
        with open(RECORDS_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        records.extend([KnowledgeRecord(**r) for r in raw])
    # Load additional food knowledge records if present
    FOOD_PATH = os.path.join(DATA_DIR, "food_records.json")
    if os.path.exists(FOOD_PATH):
        with open(FOOD_PATH, "r", encoding="utf-8") as f:
            raw_food = json.load(f)
        records.extend([KnowledgeRecord(**r) for r in raw_food])
    return records

def _save_records(records: List[KnowledgeRecord]) -> None:
    # Sort by attractionId for deterministic file order
    records_sorted = sorted(records, key=lambda r: (r.attractionId, r.sourceUrl))
    with open(RECORDS_PATH, "w", encoding="utf-8") as f:
        json.dump([r.dict(by_alias=True) for r in records_sorted], f, ensure_ascii=False, indent=2, default=str)

def ingest_record(record: Dict[str, Any]) -> KnowledgeRecord:
    """Validate and add a new knowledge record.
    Duplicate detection is based on (attractionId, sourceUrl).
    If a duplicate exists with an older retrievedAt, it is replaced.
    """
    new_rec = KnowledgeRecord(**record)
    records = _load_records()
    # Remove exact duplicate (same attractionId & sourceUrl) if newer
    filtered = []
    for r in records:
        if r.attractionId == new_rec.attractionId and r.sourceUrl == new_rec.sourceUrl:
            if new_rec.retrievedAt > r.retrievedAt:
                continue  # replace older with newer
            else:
                return r  # existing newer, ignore ingest
        filtered.append(r)
    filtered.append(new_rec)
    _save_records(filtered)
    return new_rec

def update_record(attractionId: str, sourceUrl: str, updates: Dict[str, Any]) -> KnowledgeRecord:
    """Update fields of an existing record identified by attractionId and sourceUrl.
    Raises ValueError if not found.
    """
    records = _load_records()
    for idx, r in enumerate(records):
        if r.attractionId == attractionId and r.sourceUrl == sourceUrl:
            data = r.dict()
            data.update(updates)
            updated = KnowledgeRecord(**data)
            records[idx] = updated
            _save_records(records)
            return updated
    raise ValueError("Record not found for update")

def _tokenize(text: str) -> List[str]:
    # Simple whitespace/punctuation tokenization, lower‑cased
    return re.findall(r"\b\w+\b", text.lower())

class LexicalRetriever:
    """Very small lexical search over the persisted records.
    Builds an inverted index on demand; suitable for the tiny dataset.
    """
    def __init__(self):
        self.records = _load_records()
        self.index: Dict[str, set] = {}
        for i, rec in enumerate(self.records):
            tokens = set(_tokenize(rec.name) + _tokenize(rec.description) + [t.lower() for t in rec.interests])
            for tok in tokens:
                self.index.setdefault(tok, set()).add(i)

    def search(self, query: str, limit: int = 5, attraction_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return []
        candidate_ids: set = set()
        for tok in query_tokens:
            candidate_ids.update(self.index.get(tok, set()))
        results = []
        for idx in candidate_ids:
            rec = self.records[idx]
            if attraction_id and rec.attractionId != attraction_id:
                continue
            rec_tokens = set(_tokenize(rec.name) + _tokenize(rec.description) + [t.lower() for t in rec.interests])
            overlap = len(query_tokens & rec_tokens)
            if overlap == 0:
                continue
            # Build snippet – first sentence containing any query token
            snippet = ""
            sentences = re.split(r"(?<=[.!?])\s+", rec.description)
            for s in sentences:
                if any(tok in _tokenize(s) for tok in query_tokens):
                    snippet = s.strip()
                    break
            if not snippet:
                snippet = rec.description[:200].strip()
            results.append({
                "attractionId": rec.attractionId,
                "snippet": snippet,
                "sourceTitle": rec.sourceTitle,
                "sourceUrl": rec.sourceUrl,
                "retrievedAt": rec.retrievedAt.isoformat(),
                "verificationStatus": rec.verificationStatus,
                "_score": overlap,
            })
        results.sort(key=lambda x: (-x["_score"], x["retrievedAt"]))
        for r in results:
            r.pop("_score", None)
        return results[:limit]

__all__ = ["KnowledgeRecord", "ingest_record", "update_record", "LexicalRetriever"]

