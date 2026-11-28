import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from sqlalchemy import text
from backend.app.config import settings
from backend.app.database import engine, Base, SessionLocal
from backend.app.models import Destination, User
from backend.app.routers import auth, community, rewards, gems, admin, legacy_compat, social, knowledge, itinerary_food, itinerary_ai

from backend.app.data.canonical_destinations import CANONICAL_DESTINATIONS

# CANONICAL_DESTINATIONS imported from data module


def seed_destinations():
    db = SessionLocal()
    try:
        existing = {d.id: d for d in db.query(Destination).all()}
        for item in CANONICAL_DESTINATIONS:
            if item["id"] not in existing:
                dest = Destination(
                    id=item["id"],
                    name=item["name"],
                    hindi=item["hindi"],
                    tags=item["tags"],
                    base_crowd=item["base_crowd"],
                    cost=item["cost"],
                    is_gem=item["is_gem"],
                    alternatives=item["alternatives"],
                    capacity=item["capacity"],
                    sensitivity=item["sensitivity"],
                )
                db.add(dest)
        db.commit()
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("TESTING") != "1" and not getattr(app.state, "testing", False):
        # Initialize DB schema
        Base.metadata.create_all(bind=engine)
        # Safe migration: ensure image column exists
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE crowd_reports ADD COLUMN image TEXT"))
                conn.commit()
        except Exception:
            pass
        # Seed destination foundation
        seed_destinations()
    yield

app = FastAPI(
    title="Musafir Community API",
    description="Real, database-backed community crowd reporting, forecasting, and reward engine for Jaipur.",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration (explicit origins required when allow_credentials=True)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(community.router)
app.include_router(social.router)
app.include_router(rewards.router)
app.include_router(gems.router)
app.include_router(admin.router)
app.include_router(legacy_compat.router)
app.include_router(knowledge.router)
app.include_router(itinerary_food.router)
app.include_router(itinerary_ai.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
