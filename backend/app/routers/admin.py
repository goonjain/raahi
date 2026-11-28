import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Literal

from backend.app.database import get_db
from backend.app.models import CrowdReport, GemSuggestion, PostComment, Reward
from backend.app.config import settings
from backend.app.services.auth import require_admin

router = APIRouter(prefix="/api/admin", tags=["Admin Moderation"], dependencies=[Depends(require_admin)])

class ModerationAction(BaseModel):
    status: Literal["approved", "rejected", "flagged"]
    notes: Optional[str] = None

class CommentModerationAction(BaseModel):
    status: Literal["approved", "rejected", "flagged"]
    notes: Optional[str] = None

class GemSuggestionAction(BaseModel):
    status: Literal["approved", "rejected"]
    capacity: Optional[int] = 500
    sensitivity: Optional[Literal["normal", "fragile"]] = "normal"
    notes: Optional[str] = None

@router.get("/reports")
def get_moderation_queue(
    status_filter: Optional[str] = "pending",
    db: Session = Depends(get_db)
):
    query = db.query(CrowdReport)
    if status_filter and status_filter != "all":
        query = query.filter(CrowdReport.moderation_status == status_filter)
    
    reports = query.order_by(CrowdReport.submitted_at.desc()).limit(100).all()
    return {
        "reports": [
            {
                "id": r.id,
                "destination_id": r.destination_id,
                "destination_name": r.destination.name if r.destination else r.destination_id,
                "user_id": r.user_id,
                "user_name": r.user.username if r.user else r.user_id,
                "crowd_level": r.crowd_level,
                "tip": r.tip,
                "moderation_status": r.moderation_status,
                "submitted_at": r.submitted_at.isoformat(),
                "trust_weight": r.trust_weight,
            } for r in reports
        ]
    }

@router.patch("/reports/{report_id}")
def moderate_report(
    report_id: int,
    action: ModerationAction,
    db: Session = Depends(get_db)
):
    report = db.query(CrowdReport).filter(CrowdReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    old_status = report.moderation_status
    report.moderation_status = action.status

    # If rejected, retract reward if one was given
    if action.status == "rejected":
        ref_id = f"crowd_report_{report.id}"
        reward = db.query(Reward).filter(
            Reward.user_id == report.user_id,
            Reward.reference_id == ref_id
        ).first()
        if reward:
            db.delete(reward)

    # If approved from pending, grant reward respecting daily cap and idempotency
    elif action.status == "approved" and old_status == "pending":
        now = datetime.datetime.now(datetime.timezone.utc)
        one_day_ago = now - datetime.timedelta(hours=24)
        daily_points = db.query(func.coalesce(func.sum(Reward.points), 0)).filter(
            Reward.user_id == report.user_id,
            Reward.created_at >= one_day_ago
        ).scalar() or 0
        if daily_points < settings.DAILY_POINTS_CAP:
            points_to_give = min(settings.POINTS_PER_CHECKIN, settings.DAILY_POINTS_CAP - daily_points)
            ref_id = f"crowd_report_{report.id}"
            # Ensure we don't duplicate reward
            existing = db.query(Reward).filter(
                Reward.user_id == report.user_id,
                Reward.reference_id == ref_id
            ).first()
            if not existing and points_to_give > 0:
                reward = Reward(
                    user_id=report.user_id,
                    points=points_to_give,
                    reason=f"Admin approved crowd report {report.id}",
                    reference_id=ref_id,
                    created_at=now,
                )
                db.add(reward)

    db.commit()
    return {
        "success": True,
        "report_id": report.id,
        "old_status": old_status,
        "new_status": report.moderation_status,
    }

@router.get("/gem-suggestions")
def get_gem_suggestions_queue(
    db: Session = Depends(get_db)
):
    suggestions = db.query(GemSuggestion).order_by(
        GemSuggestion.created_at.desc()
    ).all()

    return {
        "suggestions": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "place_name": s.place_name,
                "description": s.description,
                "similar_to": s.similar_to_destination_id,
                "vibe_tags": s.vibe_tags,
                "fragile": s.fragile_flag,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
            } for s in suggestions
        ]
    }

@router.patch("/gem-suggestions/{suggestion_id}")
def review_gem_suggestion(
    suggestion_id: int,
    action: GemSuggestionAction,
    db: Session = Depends(get_db)
):
    suggestion = db.query(GemSuggestion).filter(GemSuggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    suggestion.status = action.status
    now = datetime.datetime.now(datetime.timezone.utc)

    # If approved, award persistent points to the contributor
    if action.status == "approved":
        ref_id = f"gem_suggestion_{suggestion.id}"
        existing_reward = db.query(Reward).filter(
            Reward.user_id == suggestion.user_id,
            Reward.reference_id == ref_id
        ).first()

        if not existing_reward:
            reward = Reward(
                user_id=suggestion.user_id,
                points=settings.POINTS_FOR_GEM_APPROVAL,
                reason=f"Approved hidden gem suggestion: {suggestion.place_name}",
                reference_id=ref_id,
                created_at=now,
            )
            db.add(reward)

    db.commit()
    return {
        "success": True,
        "suggestion_id": suggestion.id,
        "status": suggestion.status,
        "points_awarded": settings.POINTS_FOR_GEM_APPROVAL if action.status == "approved" else 0
    }


@router.get("/comments")
def get_admin_comments(
    status_filter: Optional[str] = "all",
    db: Session = Depends(get_db)
):
    query = db.query(PostComment)
    if status_filter and status_filter != "all":
        query = query.filter(PostComment.moderation_status == status_filter)

    comments = query.order_by(PostComment.created_at.desc()).limit(100).all()
    return {
        "comments": [
            {
                "id": c.id,
                "post_id": c.post_id,
                "post_title": (
                    c.post.title
                    or (c.post.content[:60] + "..." if len(c.post.content) > 60 else c.post.content)
                ) if c.post else None,
                "user_id": c.user_id,
                "user_name": c.user.username if c.user else "Traveller",
                "content": c.content,
                "moderation_status": c.moderation_status,
                "created_at": c.created_at.isoformat(),
            }
            for c in comments
        ]
    }


@router.patch("/comments/{comment_id}")
def moderate_comment(
    comment_id: int,
    action: CommentModerationAction,
    db: Session = Depends(get_db)
):
    comment = db.query(PostComment).filter(PostComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    old_status = comment.moderation_status
    comment.moderation_status = action.status
    db.commit()
    db.refresh(comment)

    return {
        "success": True,
        "comment_id": comment.id,
        "post_id": comment.post_id,
        "old_status": old_status,
        "new_status": comment.moderation_status,
    }


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db)
):
    comment = db.query(PostComment).filter(PostComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    post_id = comment.post_id
    db.delete(comment)
    db.commit()

    return {
        "success": True,
        "deleted_comment_id": comment_id,
        "post_id": post_id,
    }
