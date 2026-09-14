"""End-to-end API tests: auth, report submission -> analysis -> retrieval,
review workflow, dashboard, and RBAC enforcement."""
import io


def test_login_rejects_bad_password(client, analyst_user):
    resp = client.post("/api/auth/login", json={"email": analyst_user.email, "password": "wrong"})
    assert resp.status_code == 401


def test_login_succeeds_and_returns_user(client, analyst_user):
    resp = client.post("/api/auth/login", json={"email": analyst_user.email, "password": "TestPass@123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == analyst_user.email
    assert "access_token" in body


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/api/reports")
    assert resp.status_code == 401


def test_create_report_runs_full_analysis_pipeline(client, auth_headers):
    resp = client.post("/api/reports", json={
        "report_type": "NEAR_MISS",
        "title": "Flange isolation near miss",
        "narrative": (
            "Technician opened a flange before confirming isolation. "
            "Residual pressure was released. No injury occurred."
        ),
        "site": "Test Site 1",
        "activity": "Pipeline Maintenance",
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["analysis"] is not None
    assert body["analysis"]["sif_classification"] == "HIGH"
    assert body["analysis"]["primary_lsr"] == "Energy Isolation"
    assert body["analysis"]["explanation_text"]
    assert len(body["analysis"]["barriers"]) >= 1


def test_get_report_fingerprint(client, auth_headers):
    create_resp = client.post("/api/reports", json={
        "narrative": "Worker leaned out from a scaffold platform without re-anchoring the fall-arrest lanyard.",
        "site": "Test Site 2", "activity": "Working at Height",
    }, headers=auth_headers)
    report_id = create_resp.json()["id"]

    fp_resp = client.get(f"/api/reports/{report_id}/fingerprint", headers=auth_headers)
    assert fp_resp.status_code == 200
    fingerprint = fp_resp.json()
    assert fingerprint["report_id"] == report_id
    assert "sif_potential" in fingerprint
    assert "barriers" in fingerprint


def test_report_creation_rejects_empty_narrative(client, auth_headers):
    resp = client.post("/api/reports", json={"narrative": "   "}, headers=auth_headers)
    assert resp.status_code == 422


def test_csv_upload_validates_and_processes_rows(client, auth_headers):
    csv_content = (
        "narrative,site,activity,report_type\n"
        "Worker entered the confined space without a standby attendant posted at the entry point.,Site X,Confined Space Entry,NEAR_MISS\n"
        ",Site X,General Maintenance,NEAR_MISS\n"  # missing narrative -> should fail
    )
    files = {"file": ("upload.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    resp = client.post("/api/reports/upload", files=files, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_rows"] == 2
    assert body["successful"] == 1
    assert body["failed"] == 1


def test_review_workflow_approve(client, auth_headers):
    create_resp = client.post("/api/reports", json={
        "narrative": "Unusual noise heard near rotating equipment; area was cleared as a precaution.",
        "site": "Test Site 3", "activity": "General Maintenance",
    }, headers=auth_headers)
    report_id = create_resp.json()["id"]

    review_resp = client.post(f"/api/review/{report_id}", json={"action": "APPROVE"}, headers=auth_headers)
    assert review_resp.status_code == 200, review_resp.text
    assert review_resp.json()["action"] == "APPROVE"

    report_resp = client.get(f"/api/reports/{report_id}", headers=auth_headers)
    assert report_resp.json()["analysis"]["review_required"] is False


def test_review_workflow_modify_records_feedback(client, auth_headers):
    create_resp = client.post("/api/reports", json={
        "narrative": "A minor observation with unclear evidence was logged during the shift.",
        "site": "Test Site 4", "activity": "General Maintenance",
    }, headers=auth_headers)
    report_id = create_resp.json()["id"]

    resp = client.post(f"/api/review/{report_id}", json={
        "action": "MODIFY",
        "reason": "Analyst determined this is actually MEDIUM risk.",
        "corrected_fields": {"sif_classification": "MEDIUM"},
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["corrected_fields"].get("sif_classification", {}).get("new") == "MEDIUM"

    report_resp = client.get(f"/api/reports/{report_id}", headers=auth_headers)
    assert report_resp.json()["analysis"]["sif_classification"] == "MEDIUM"


def test_dashboard_summary_reflects_created_reports(client, auth_headers):
    resp = client.get("/api/dashboard/summary", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_reports"] >= 1
    assert "sif_high" in body


def test_viewer_role_cannot_create_reports(client, db_session):
    from app.models.user import User, UserRole
    from app.core.security import hash_password

    viewer = db_session.query(User).filter(User.email == "test.viewer@sifguard-oil.com").first()
    if not viewer:
        viewer = User(email="test.viewer@sifguard-oil.com", full_name="Test Viewer",
                       role=UserRole.VIEWER, hashed_password=hash_password("TestPass@123"))
        db_session.add(viewer)
        db_session.commit()

    login = client.post("/api/auth/login", json={"email": viewer.email, "password": "TestPass@123"})
    token = login.json()["access_token"]
    resp = client.post("/api/reports", json={"narrative": "test"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_evaluation_endpoint_returns_disclaimer(client, auth_headers):
    resp = client.get("/api/evaluation", headers=auth_headers)
    assert resp.status_code == 200
    assert "disclaimer" in resp.json()
    assert "synthetic" in resp.json()["disclaimer"].lower()
