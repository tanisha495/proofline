"""End-to-end integration test of the full ProofLine governance workflow."""
from __future__ import annotations

from app.services.workflow.seed_service import seed_sample_data


def test_full_content_governance_workflow(client, db_session):
    # Seed demo users and sample sources
    seed_sample_data(db_session)

    # 1. Login as Creator (Studio North writer)
    login_res = client.post(
        "/auth/login",
        json={"email": "writer@studionorth.demo", "password": "proofline-demo"},
    )
    assert login_res.status_code == 200
    creator_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 2. Verify RAG search works over Dhruv's dataset
    rag_res = client.get("/sources/rag-search?query=Asteria%20Greens%20pricing", headers=creator_headers)
    assert rag_res.status_code == 200
    assert rag_res.json()["total_chunks_indexed"] > 0

    # 3. Create draft with deliberate planted errors
    draft_res = client.post(
        "/drafts",
        headers=creator_headers,
        json={
            "title": "Spring Promo",
            "content": (
                "Grab a hot cup of java! Our blend cures all morning fatigue. "
                "We now operate 500 retail locations."
            ),
            "channel": "instagram_post",
            "intent_lock": {
                "key_message": "energetic coffee morning",
                "audience": "coffee lovers",
                "call_to_action": "grab a cup",
            },
        },
    )
    assert draft_res.status_code == 201
    draft_id = draft_res.json()["id"]

    # 4. Run 4-layer review engine
    review_res = client.post(f"/drafts/{draft_id}/review", headers=creator_headers)
    assert review_res.status_code == 202
    rev_data = review_res.json()
    assert rev_data["findings_count"] >= 3
    assert rev_data["blockers_count"] >= 2

    # 5. Fetch findings & verify "No source, no flag"
    findings_res = client.get(f"/drafts/{draft_id}/versions/1/findings", headers=creator_headers)
    assert findings_res.status_code == 200
    findings = findings_res.json()
    assert len(findings) >= 3
    for f in findings:
        assert f["source_ref"] and f["source_ref"].strip()
        assert f["end"] > f["start"]

    # 6. Triage finding
    first_finding = findings[0]
    triage_res = client.patch(
        f"/findings/{first_finding['id']}",
        headers=creator_headers,
        json={"status": "accepted"},
    )
    assert triage_res.status_code == 200
    assert triage_res.json()["status"] == "accepted"

    # 7. Request human review -> Risk Tier Level 3
    req_rev_res = client.post(f"/drafts/{draft_id}/request-review", headers=creator_headers)
    assert req_rev_res.status_code == 202
    assert req_rev_res.json()["status"] == "in_review"
    assert "Level 3: High" in req_rev_res.json()["risk_tier"]

    # 8. Login as Reviewer (Studio North manager) and approve
    rev_login = client.post(
        "/auth/login",
        json={"email": "manager@studionorth.demo", "password": "proofline-demo"},
    )
    assert rev_login.status_code == 200
    reviewer_headers = {"Authorization": f"Bearer {rev_login.json()['access_token']}"}

    comment_res = client.post(
        f"/drafts/{draft_id}/comments",
        headers=reviewer_headers,
        json={"text": "Checked store count and health phrasing.", "range_start": 0, "range_end": 20},
    )
    assert comment_res.status_code == 201

    decision_res = client.post(
        f"/drafts/{draft_id}/decision",
        headers=reviewer_headers,
        json={"decision": "approved", "reason": "Verified all claims."},
    )
    assert decision_res.status_code == 201
    assert decision_res.json()["decision"] == "approved"

    # 9. Verify Claim Receipt generated
    receipt_res = client.get(f"/drafts/{draft_id}/receipt", headers=reviewer_headers)
    assert receipt_res.status_code == 200
    receipt_data = receipt_res.json()
    assert receipt_data["status"] == "approved"
    assert receipt_data["receipts_count"] == 1

    # 10. Insights & Admin Audit Log
    insights_res = client.get("/insights/rules", headers=reviewer_headers)
    assert insights_res.status_code == 200
    assert isinstance(insights_res.json(), list)

    admin_login = client.post(
        "/auth/login",
        json={"email": "admin@proofline.ai", "password": "admin12345"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    audit_res = client.get("/audit", headers=admin_headers)
    assert audit_res.status_code == 200
    assert len(audit_res.json()) >= 4
