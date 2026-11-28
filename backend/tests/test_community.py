import os
os.environ["TESTING"] = "1"
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
app.state.testing = True
from backend.app.database import Base, get_db
from backend.app.models import Destination, User, CrowdReport, Reward, AccuracyVote, TravelPost, PostComment
from backend.app.config import settings

# Test in-memory SQLite database with StaticPool
TEST_DB_URL = "sqlite:///:memory:"
engine_test = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine_test)
    db = TestingSessionLocal()
    # Seed Amber Fort and Jaigarh
    db.add(Destination(id="amber", name="Amber Fort", base_crowd=62, is_gem=False, alternatives=["jaigarh"]))
    db.add(Destination(id="jaigarh", name="Jaigarh Fort", base_crowd=30, is_gem=True, alternatives=[]))
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine_test)

client = TestClient(app)


def _signup_client(name: str, email: str) -> TestClient:
    c = TestClient(app)
    res = c.post("/api/auth/signup", json={"name": name, "email": email, "password": "Password123"})
    assert res.status_code == 201, res.text
    return c


def _admin_client() -> TestClient:
    import uuid
    from backend.app.services.auth import hash_password
    email = f"admin_{uuid.uuid4().hex[:6]}@raahi.gov.in"
    db = TestingSessionLocal()
    db.add(User(
        id=f"adm_{uuid.uuid4().hex[:8]}",
        username="DoT Admin",
        email=email,
        password_hash=hash_password("AdminPass123"),
        role="admin",
    ))
    db.commit()
    db.close()
    c = TestClient(app)
    res = c.post("/api/auth/login", json={"email": email, "password": "AdminPass123"})
    assert res.status_code == 200, res.text
    return c

def test_empty_feed_shows_no_fabricated_data():
    """Requirement 11: Production community feed has NO fabricated data."""
    res = client.get("/api/crowd-reports")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 0
    assert data["reports"] == []

def test_submit_valid_crowd_report_starts_pending_and_awards_points_on_verify():
    """Requirement: New report starts pending (0 pts, hidden from verified feed); admin approval verifies & awards points."""
    tourist = _signup_client("Arjun K.", "arjun@example.com")
    admin = _admin_client()
    payload = {
        "destination_id": "amber",
        "crowd_level": "Busy",
        "vs_forecast": "About right",
        "wait_minutes": 25,
        "tip": "Elephant ride queue is long, walked up the ramp instead.",
        "user_name": "Arjun K."
    }
    res = tourist.post("/api/crowd-reports", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["success"] is True
    assert data["points_awarded"] == 0
    assert data["total_points"] == 0
    assert data["report"]["destination_id"] == "amber"
    assert data["report"]["crowd_level"] == "Busy"
    assert data["report"]["wait_minutes"] == 25
    assert data["report"]["tip"] == payload["tip"]
    assert "submitted_at" in data["report"]
    assert data["report"]["moderation_status"] == "pending"

    # Pending report is NOT in verified public feed yet
    pending_feed = client.get("/api/crowd-reports?destination_id=amber").json()
    assert pending_feed["count"] == 0

    # Admin verifies the pending report -> becomes approved & awards 20 points
    report_id = data["report"]["id"]
    verify_res = admin.patch(f"/api/admin/reports/{report_id}", json={"status": "approved"})
    assert verify_res.status_code == 200
    assert verify_res.json()["new_status"] == "approved"

    balance = tourist.get("/api/rewards/balance").json()
    assert balance["total_points"] == 20

    # Verify retrieval from public feed across sessions
    feed_res = client.get("/api/crowd-reports?destination_id=amber")
    assert feed_res.status_code == 200
    feed_data = feed_res.json()
    assert feed_data["count"] == 1
    assert feed_data["reports"][0]["tip"] == payload["tip"]
    assert feed_data["reports"][0]["user_name"] == "Arjun K."

def test_validation_rejects_invalid_destination_and_crowd_level():
    """Requirement 6: Server-side validation rejects invalid values."""
    tourist = _signup_client("Validator", "validator@example.com")
    # Invalid destination
    res1 = tourist.post("/api/crowd-reports", json={"destination_id": "non_existent_fort", "crowd_level": "Quiet"})
    assert res1.status_code == 404

    # Invalid crowd level
    res2 = tourist.post("/api/crowd-reports", json={"destination_id": "amber", "crowd_level": "SuperPacked"})
    assert res2.status_code == 422

def test_rate_limit_blocks_duplicate_report_within_45_minutes():
    """Requirement 8 & 9: One report per user per place every 45 minutes."""
    tourist = _signup_client("Spammer", "spammer@example.com")
    payload = {"destination_id": "amber", "crowd_level": "Quiet", "tip": "Nice visit"}
    
    # First report succeeds
    res1 = tourist.post("/api/crowd-reports", json=payload)
    assert res1.status_code == 201

    # Second report within 45 min is rejected
    res2 = tourist.post("/api/crowd-reports", json=payload)
    assert res2.status_code == 429
    assert "Rate limit" in res2.json()["detail"]

def test_daily_points_cap_enforced():
    """Requirement 10: Persistent points daily cap (100 pts max) enforced upon admin approval."""
    tourist = _signup_client("Point Farmer", "farmer@example.com")
    admin = _admin_client()
    db = TestingSessionLocal()
    # Create 6 distinct destinations to bypass per-place rate limits
    for i in range(1, 7):
        db.add(Destination(id=f"dest_{i}", name=f"Place {i}", base_crowd=30))
    db.commit()
    db.close()

    # Submit and approve 5 reports on 5 different destinations (20 pts each = 100 pts)
    for i in range(1, 6):
        res = tourist.post("/api/crowd-reports", json={"destination_id": f"dest_{i}", "crowd_level": "Quiet"})
        assert res.status_code == 201
        rep_id = res.json()["report"]["id"]
        admin.patch(f"/api/admin/reports/{rep_id}", json={"status": "approved"})

    balance = tourist.get("/api/rewards/balance").json()
    assert balance["total_points"] == 100

    # 6th report approved awards 0 additional points due to daily cap
    res6 = tourist.post("/api/crowd-reports", json={"destination_id": "dest_6", "crowd_level": "Quiet"})
    assert res6.status_code == 201
    rep6_id = res6.json()["report"]["id"]
    admin.patch(f"/api/admin/reports/{rep6_id}", json={"status": "approved"})
    balance_after = tourist.get("/api/rewards/balance").json()
    assert balance_after["total_points"] == 100

def test_accuracy_voting_and_duplicate_vote_prevention():
    """Feature doc Section 3.4: Accuracy votes adjust trust weight; duplicate vote rejected."""
    user_a = _signup_client("User A", "usera@example.com")
    user_b = _signup_client("User B", "userb@example.com")
    # User A submits a report
    res_sub = user_a.post("/api/crowd-reports", json={"destination_id": "amber", "crowd_level": "Busy"})
    report_id = res_sub.json()["report"]["id"]

    # User A cannot vote on their own report
    self_vote = user_a.post("/api/accuracy-votes", json={"report_id": report_id, "vote": 1})
    assert self_vote.status_code == 400

    # User B votes "Still accurate?" (+1)
    res_vote = user_b.post("/api/accuracy-votes", json={"report_id": report_id, "vote": 1})
    assert res_vote.status_code == 200
    assert res_vote.json()["success"] is True
    assert res_vote.json()["trust_weight"] > 1.0

    # User B cannot vote again
    dup_vote = user_b.post("/api/accuracy-votes", json={"report_id": report_id, "vote": 1})
    assert dup_vote.status_code == 400

def test_live_crowd_adjustment_and_stale_window():
    """Feature doc Section 4: Only approved reports adjust live crowd; 2-hour stale window applies."""
    observer = _signup_client("Observer", "observer@example.com")
    admin = _admin_client()

    # 1. No reports -> Baseline "Estimated"
    res1 = client.get("/api/places/amber/live-crowd")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["adjustment"] == 0
    assert data1["report_count"] == 0
    assert data1["status_label"] == "Estimated"

    # 2. Submit pending "Packed" report -> must NOT affect live crowd yet
    sub = observer.post("/api/crowd-reports", json={"destination_id": "amber", "crowd_level": "Packed"})
    rep_id = sub.json()["report"]["id"]
    pending_live = client.get("/api/places/amber/live-crowd").json()
    assert pending_live["report_count"] == 0
    assert pending_live["adjustment"] == 0

    # 3. Admin approves -> Adjusts live score upwards
    admin.patch(f"/api/admin/reports/{rep_id}", json={"status": "approved"})
    res2 = client.get("/api/places/amber/live-crowd")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["report_count"] == 1
    assert data2["adjustment"] > 0
    assert "Estimated, adjusted by 1 report in the last" in data2["status_label"]

    # 4. Rejecting approved report deactivates its live crowd contribution immediately
    admin.patch(f"/api/admin/reports/{rep_id}", json={"status": "rejected"})
    after_reject = client.get("/api/places/amber/live-crowd").json()
    assert after_reject["report_count"] == 0
    assert after_reject["adjustment"] == 0

    # Re-approve to test stale window
    admin.patch(f"/api/admin/reports/{rep_id}", json={"status": "approved"})

    # 5. Reports older than 2 hours (120 min) become stale and stop affecting live crowd
    db = TestingSessionLocal()
    old_report = db.query(CrowdReport).first()
    old_report.submitted_at = datetime.now(timezone.utc) - timedelta(minutes=130)
    db.commit()
    db.close()

    res3 = client.get("/api/places/amber/live-crowd")
    data3 = res3.json()
    assert data3["report_count"] == 0
    assert data3["adjustment"] == 0
    assert data3["status_label"] == "Estimated"

def test_flagging_and_admin_moderation_security():
    """Feature doc Section 8: Unauthorized users cannot call admin endpoints; admin can moderate."""
    user_x = _signup_client("User X", "userx@example.com")
    user_y = _signup_client("User Y", "usery@example.com")
    admin = _admin_client()

    # 1. Flag a report
    res_sub = user_x.post("/api/crowd-reports", json={"destination_id": "amber", "crowd_level": "Quiet", "tip": "Some text"})
    report_id = res_sub.json()["report"]["id"]

    flag_res = user_y.post(f"/api/reports/{report_id}/flag")
    assert flag_res.status_code == 200

    # 2. Unauthenticated (401) and tourist (403) admin access are rejected
    assert client.get("/api/admin/reports").status_code == 401
    assert user_x.get("/api/admin/reports").status_code == 403

    # 3. Authorized admin access succeeds
    admin_get = admin.get("/api/admin/reports?status_filter=flagged")
    assert admin_get.status_code == 200
    assert len(admin_get.json()["reports"]) == 1

    # 4. Admin rejects report -> revokes points and excludes from feed
    mod_action = admin.patch(f"/api/admin/reports/{report_id}", json={"status": "rejected"})
    assert mod_action.status_code == 200
    assert mod_action.json()["new_status"] == "rejected"

    # User X's points should now be 0 because rejected reports cannot earn rewards
    balance = user_x.get("/api/rewards/balance")
    assert balance.json()["total_points"] == 0

def test_hidden_gem_suggestions_and_alternatives():
    """Feature doc Section 5: Private suggestion queue and on-demand alternatives."""
    scout = _signup_client("Scout", "scout@example.com")
    stranger = _signup_client("Stranger", "stranger@example.com")
    # User submits hidden gem suggestion privately
    res = scout.post("/api/gem-suggestions", json={
        "place_name": "Galta Ji (Monkey Temple)",
        "description": "Historic temple complex in a narrow crevice with natural springs.",
        "similar_to_destination_id": "amber",
        "vibe_tags": ["heritage", "nature"],
        "fragile_flag": True
    })
    assert res.status_code == 201

    # Visible only to submitter
    my_suggs = scout.get("/api/gem-suggestions/mine")
    assert len(my_suggs.json()["suggestions"]) == 1

    other_user = stranger.get("/api/gem-suggestions/mine")
    assert len(other_user.json()["suggestions"]) == 0

    # On-demand alternatives for Amber Fort
    alts = client.get("/api/places/amber/alternatives")
    assert alts.status_code == 200
    assert len(alts.json()["alternatives"]) >= 1
    assert alts.json()["alternatives"][0]["id"] == "jaigarh"
    assert "room_left_score" in alts.json()["alternatives"][0]

def test_destination_search_and_custom_creation():
    """Verify destination search and custom 'Add a new place' creation."""
    explorer = _signup_client("Explorer", "explorer@example.com")
    # 1. Search existing
    res = client.get("/api/destinations?q=amber")
    assert res.status_code == 200
    destinations = res.json()
    assert len(destinations) >= 1
    assert destinations[0]["id"] == "amber"

    # 2. Add custom place
    new_place_payload = {
        "name": "Nahargarh Sunset Ridge",
        "hindi": "नाहरगढ़ सनसेट रिज",
        "category": "nature",
        "tags": ["nature", "photography"],
        "sensitivity": "fragile"
    }
    create_res = explorer.post("/api/destinations", json=new_place_payload)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["name"] == "Nahargarh Sunset Ridge"
    assert "sunset_ridge" in created["id"]

    # 3. Search finding newly created place
    search_res = client.get("/api/destinations?q=sunset")
    assert search_res.status_code == 200
    assert any(d["id"] == created["id"] for d in search_res.json())

def test_travel_social_post_creation_and_feed():
    """Verify Travel Stories / Social feed creation and retrieval."""
    aarav = _signup_client("Aarav", "aarav_social@example.com")
    post_payload = {
        "destination_id": "amber",
        "title": "Magical Sunrise at Amber Gate",
        "content": "Arrived at 7:30 AM before tourist buses. Suraj Pol courtyard was completely quiet and serene.",
        "image_url": "data:image/jpeg;base64,mockphotodata",
        "user_name": "Aarav"
    }
    res = aarav.post("/api/posts", json=post_payload)
    assert res.status_code == 201
    post = res.json()
    assert post["title"] == "Magical Sunrise at Amber Gate"
    assert post["user_name"] == "Aarav"
    assert post["destination_name"] == "Amber Fort"
    assert post["moderation_status"] == "approved"
    assert post["likes_count"] == 0

    # Retrieve feed
    feed_res = aarav.get("/api/posts?destination_id=amber")
    assert feed_res.status_code == 200
    posts = feed_res.json()
    assert len(posts) >= 1
    assert posts[0]["id"] == post["id"]

def test_travel_post_like_and_unlike_toggle():
    """Verify like/unlike toggle and unique like constraint behavior."""
    author = _signup_client("Diya", "diya@example.com")
    liker1 = _signup_client("Liker 1", "liker1@example.com")
    liker2 = _signup_client("Liker 2", "liker2@example.com")
    post_res = author.post("/api/posts", json={
        "content": "Beautiful marble carvings at Royal Gaitor.",
        "user_name": "Diya"
    })
    post_id = post_res.json()["id"]

    # User 1 likes post
    like_res1 = liker1.post(f"/api/posts/{post_id}/like")
    assert like_res1.status_code == 200
    assert like_res1.json()["liked"] is True
    assert like_res1.json()["likes_count"] == 1

    # User 1 toggles like (unlikes)
    unlike_res = liker1.post(f"/api/posts/{post_id}/like")
    assert unlike_res.status_code == 200
    assert unlike_res.json()["liked"] is False
    assert unlike_res.json()["likes_count"] == 0

    # User 1 likes again + User 2 likes
    liker1.post(f"/api/posts/{post_id}/like")
    like_res2 = liker2.post(f"/api/posts/{post_id}/like")
    assert like_res2.status_code == 200
    assert like_res2.json()["likes_count"] == 2

def test_travel_post_comments_flow():
    """Verify commenting on travel posts."""
    creator = _signup_client("Meera", "meera_c@example.com")
    commenter = _signup_client("Rohan", "rohan_c@example.com")
    post_res = creator.post("/api/posts", json={
        "content": "Stepwell steps are symmetrical and stunning in morning light.",
        "user_name": "Meera"
    })
    post_id = post_res.json()["id"]

    # Add comment
    comment_res = commenter.post(f"/api/posts/{post_id}/comments", json={
        "content": "What is the best time to avoid tour buses?",
        "user_name": "Rohan"
    })
    assert comment_res.status_code == 201
    assert comment_res.json()["content"] == "What is the best time to avoid tour buses?"
    assert comment_res.json()["user_name"] == "Rohan"

    # Get comments
    get_res = client.get(f"/api/posts/{post_id}/comments")
    assert get_res.status_code == 200
    comments = get_res.json()
    assert len(comments) == 1
    assert comments[0]["content"] == "What is the best time to avoid tour buses?"

def test_social_content_moderation_abusive_language():
    """Verify that profanity or spam links are flagged for moderation."""
    spammer = _signup_client("Troll", "troll@example.com")
    clean_user = _signup_client("Clean", "clean@example.com")
    # Obfuscated profanity in post
    res = spammer.post("/api/posts", json={
        "content": "Check this out b a s t a r d scam discount",
        "user_name": "Troll"
    })
    assert res.status_code == 201
    assert res.json()["moderation_status"] == "flagged"

    # Spam link in comment
    post = clean_user.post("/api/posts", json={
        "content": "Clean travel story here.",
    }).json()

    comment_res = spammer.post(f"/api/posts/{post['id']}/comments", json={
        "content": "Click http://free-crypto-giveaway.xyz for prizes",
    })
    assert comment_res.status_code == 201
    assert comment_res.json()["moderation_status"] == "flagged"


def _seed_post_with_comment(status_value: str, content: str = "Test comment"):
    db = TestingSessionLocal()
    user = User(id="mod_test_user", username="ModTester", role="traveller")
    db.merge(user)
    post = TravelPost(
        user_id="mod_test_user",
        destination_id="amber",
        title="Parent Travel Story",
        content="Parent post content that must be preserved.",
        moderation_status="approved",
    )
    db.add(post)
    db.flush()
    comment = PostComment(
        user_id="mod_test_user",
        post_id=post.id,
        content=content,
        moderation_status=status_value,
    )
    db.add(comment)
    db.commit()
    db.refresh(post)
    db.refresh(comment)
    post_id, comment_id = post.id, comment.id
    db.close()
    return post_id, comment_id


def test_verify_and_reject_pending_crowd_report_persists():
    """Verify and reject pending CrowdReport (tests SQLAlchemy func import and reward grant/retraction)."""
    admin = _admin_client()
    other_reporter = _signup_client("Other", "other@example.com")
    db = TestingSessionLocal()
    db.add(User(id="pending_reporter", username="PendingUser", role="traveller"))
    pending_rep = CrowdReport(
        user_id="pending_reporter",
        destination_id="amber",
        crowd_level="Moderate",
        tip="Queued for review",
        moderation_status="pending",
    )
    pending_rep_reject = CrowdReport(
        user_id="pending_reporter",
        destination_id="jaigarh",
        crowd_level="Quiet",
        tip="Will be rejected",
        moderation_status="pending",
    )
    db.add_all([pending_rep, pending_rep_reject])
    db.commit()
    rep_approve_id = pending_rep.id
    rep_reject_id = pending_rep_reject.id
    db.close()

    # 1. Verify pending report -> becomes approved and appears in public feed
    res_approve = admin.patch(
        f"/api/admin/reports/{rep_approve_id}",
        json={"status": "approved"},
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["new_status"] == "approved"

    # 2. Reject pending report -> excluded from public feed
    res_reject = admin.patch(
        f"/api/admin/reports/{rep_reject_id}",
        json={"status": "rejected"},
    )
    assert res_reject.status_code == 200
    assert res_reject.json()["new_status"] == "rejected"

    feed = client.get("/api/crowd-reports").json()
    feed_ids = [r["id"] for r in feed["reports"]]
    assert rep_approve_id in feed_ids
    assert rep_reject_id not in feed_ids

    # 3. Rejecting the approved report removes it without affecting a separate approved report
    other_rep_res = other_reporter.post(
        "/api/crowd-reports",
        json={"destination_id": "jaigarh", "crowd_level": "Quiet", "tip": "Other report"},
    )
    other_rep_id = other_rep_res.json()["report"]["id"]
    admin.patch(f"/api/admin/reports/{other_rep_id}", json={"status": "approved"})

    admin.patch(f"/api/admin/reports/{rep_approve_id}", json={"status": "rejected"})
    feed_after = client.get("/api/crowd-reports").json()
    feed_after_ids = [r["id"] for r in feed_after["reports"]]
    assert rep_approve_id not in feed_after_ids
    assert other_rep_id in feed_after_ids


def test_comment_verify_reject_and_public_feed_filtering():
    """Verify pending comment, reject pending comment, reject previously approved comment, and check persistence."""
    admin = _admin_client()
    post_id, pending_id = _seed_post_with_comment("pending", "Pending tip for Amber Fort")

    # Pending comment is NOT in public feed yet
    assert client.get(f"/api/posts/{post_id}/comments").json() == []

    # 1. Verify pending comment -> visible in public feed
    verify_res = admin.patch(
        f"/api/admin/comments/{pending_id}",
        json={"status": "approved"},
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["new_status"] == "approved"
    public_comments = client.get(f"/api/posts/{post_id}/comments").json()
    assert len(public_comments) == 1
    assert public_comments[0]["id"] == pending_id

    # 2. Reject previously approved comment -> excluded from public feed & persists
    reject_approved_res = admin.patch(
        f"/api/admin/comments/{pending_id}",
        json={"status": "rejected"},
    )
    assert reject_approved_res.status_code == 200
    assert reject_approved_res.json()["new_status"] == "rejected"
    assert client.get(f"/api/posts/{post_id}/comments").json() == []

    # 3. Reject a pending comment directly -> excluded from public feed
    _, pending_id_2 = _seed_post_with_comment("pending", "Spammy pending comment")
    reject_pending_res = admin.patch(
        f"/api/admin/comments/{pending_id_2}",
        json={"status": "rejected"},
    )
    assert reject_pending_res.status_code == 200
    assert reject_pending_res.json()["new_status"] == "rejected"

    # Admin list reflects persisted statuses
    admin_list = admin.get("/api/admin/comments?status_filter=rejected").json()
    rejected_ids = {c["id"] for c in admin_list["comments"]}
    assert pending_id in rejected_ids
    assert pending_id_2 in rejected_ids


@pytest.mark.parametrize("initial_status", ["pending", "approved", "rejected"])
def test_admin_delete_comment_any_status_preserves_parent_post(initial_status: str):
    """Delete pending, approved, or rejected comment; verify removal and parent post preservation."""
    admin = _admin_client()
    post_id, comment_id = _seed_post_with_comment(initial_status, f"Comment with status {initial_status}")

    del_res = admin.delete(f"/api/admin/comments/{comment_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted_comment_id"] == comment_id
    assert del_res.json()["post_id"] == post_id

    # Deleting again returns 404 gracefully
    missing_res = admin.delete(f"/api/admin/comments/{comment_id}")
    assert missing_res.status_code == 404

    # Excluded from public feed and admin list
    assert client.get(f"/api/posts/{post_id}/comments").json() == []
    admin_comments = admin.get("/api/admin/comments").json()["comments"]
    assert all(c["id"] != comment_id for c in admin_comments)

    # Parent post is preserved
    posts = client.get("/api/posts").json()
    parent_post = next((p for p in posts if p["id"] == post_id), None)
    assert parent_post is not None
    assert parent_post["title"] == "Parent Travel Story"
    assert parent_post["comments_count"] == 0


def test_non_admin_cannot_moderate_or_delete_comments():
    """Unauthenticated (401) and tourist (403) users cannot perform moderation mutations."""
    post_id, comment_id = _seed_post_with_comment("pending", "Protected comment")
    tourist = _signup_client("Tourist", "tourist_mod@example.com")
    admin = _admin_client()

    assert client.get("/api/admin/comments").status_code == 401
    assert tourist.get("/api/admin/comments").status_code == 403

    assert client.patch(
        f"/api/admin/comments/{comment_id}",
        json={"status": "approved"},
    ).status_code == 401
    assert tourist.patch(
        f"/api/admin/comments/{comment_id}",
        json={"status": "rejected"},
    ).status_code == 403

    assert client.delete(f"/api/admin/comments/{comment_id}").status_code == 401
    assert tourist.delete(f"/api/admin/comments/{comment_id}").status_code == 403

    # Comment still exists unchanged in DB
    admin_comments = admin.get("/api/admin/comments").json()["comments"]
    assert any(c["id"] == comment_id and c["moderation_status"] == "pending" for c in admin_comments)
    assert post_id > 0


def test_cross_device_shared_community_lifecycle():
    """Simulate Device A, Admin Client, and Device B sharing the same backend database."""
    device_a = _signup_client("rohan", "rohan_cross@example.com")
    device_b = TestClient(app)
    admin_client = _admin_client()

    # 1. Device A submits a report -> returns persistent backend ID, starts pending
    sub_res = device_a.post(
        "/api/crowd-reports",
        json={
            "destination_id": "amber",
            "crowd_level": "Moderate",
            "wait_minutes": 5,
            "tip": "Wait time: 5 mins",
            "user_name": "rohan",
        },
    )
    assert sub_res.status_code == 201
    report_id = sub_res.json()["report"]["id"]
    assert isinstance(report_id, int)
    assert sub_res.json()["report"]["moderation_status"] == "pending"

    # 2. Device B does NOT see pending report in public approved feed
    b_feed_pending = device_b.get("/api/crowd-reports").json()
    assert all(r["id"] != report_id for r in b_feed_pending["reports"])

    # 3. Admin queue (default pending) shows the report
    admin_pending = admin_client.get("/api/admin/reports?status_filter=pending").json()
    assert any(r["id"] == report_id and r["user_name"] == "rohan" for r in admin_pending["reports"])

    # 4. Admin approves -> Device B sees it in public feed and rewards are awarded
    approve_res = admin_client.patch(
        f"/api/admin/reports/{report_id}",
        json={"status": "approved"},
    )
    assert approve_res.status_code == 200
    b_feed_approved = device_b.get("/api/crowd-reports").json()
    assert any(r["id"] == report_id and r["moderation_status"] == "approved" for r in b_feed_approved["reports"])

    # 5. Admin rejects previously approved report -> disappears from Device B & persists on fresh client
    reject_res = admin_client.patch(
        f"/api/admin/reports/{report_id}",
        json={"status": "rejected"},
    )
    assert reject_res.status_code == 200

    fresh_device_b = TestClient(app)
    b_feed_after_reject = fresh_device_b.get("/api/crowd-reports").json()
    assert all(r["id"] != report_id for r in b_feed_after_reject["reports"])

