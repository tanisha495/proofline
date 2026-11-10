"""Authentication and authorization tests for ProofLine API."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from jose import jwt
from sqlalchemy import select

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.models.audit_log import AuditLog
from app.models.organisation import Organisation
from app.models.user import User


def _create_user(
    db_session,
    email: str = "test@example.com",
    role: str = "creator",
    password: str = "ValidPassword123!",
    is_active: bool = True,
    org_name: str | None = None,
) -> User:
    """Helper to create an organisation and user in the test database."""
    org_name = org_name or f"Org-{uuid.uuid4().hex[:8]}"
    org = Organisation(name=org_name)
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    user = User(
        organisation_id=org.id,
        email=email.strip().lower(),
        password_hash=hash_password(password),
        full_name="Test User",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_login_success(client, db_session):
    """Login success returns an access token, token_type bearer, and user fields."""
    user = _create_user(db_session, email="creator@proofline.ai", password="SecretPassword123!")

    # Test that email is trimmed and lowercased
    res = client.post(
        "/auth/login",
        json={"email": "  CREATOR@ProofLine.AI  ", "password": "SecretPassword123!"},
    )
    assert res.status_code == 200
    data = res.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data

    u = data["user"]
    assert u["id"] == str(user.id)
    assert u["email"] == "creator@proofline.ai"
    assert u["role"] == "creator"
    assert u["organisation_id"] == str(user.organisation_id)
    assert u["full_name"] == "Test User"


def test_login_failure_identical_message(client, db_session):
    """Wrong password and unknown email both return 401 with the identical message."""
    _create_user(db_session, email="existing@proofline.ai", password="CorrectPassword123!")

    # 1. Unknown email
    res_unknown = client.post(
        "/auth/login",
        json={"email": "nonexistent@proofline.ai", "password": "AnyPassword123!"},
    )
    assert res_unknown.status_code == 401

    # 2. Wrong password for existing user
    res_wrong_pw = client.post(
        "/auth/login",
        json={"email": "existing@proofline.ai", "password": "WrongPassword123!"},
    )
    assert res_wrong_pw.status_code == 401

    # Both error details MUST be identical
    assert res_unknown.json() == res_wrong_pw.json()
    assert res_unknown.json()["detail"] == "Invalid email or password"


def test_inactive_user_cannot_login(client, db_session):
    """Inactive user cannot log in and gets identical 401 error message."""
    _create_user(
        db_session,
        email="inactive@proofline.ai",
        password="ValidPassword123!",
        is_active=False,
    )

    res = client.post(
        "/auth/login",
        json={"email": "inactive@proofline.ai", "password": "ValidPassword123!"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"


def test_token_validation(client, db_session):
    """Missing, expired or tampered token returns 401 on protected endpoints."""
    user = _create_user(db_session, email="active@proofline.ai")

    # 1. Missing token
    res_missing = client.get("/auth/me")
    assert res_missing.status_code == 401

    # 2. Tampered token
    valid_token = create_access_token(user)
    tampered_token = valid_token[:-4] + "xxxx"
    res_tampered = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert res_tampered.status_code == 401

    # 3. Expired token
    expired_payload = {
        "sub": str(user.id),
        "org": str(user.organisation_id),
        "role": user.role,
        "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
        "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
    }
    expired_token = jwt.encode(expired_payload, settings.jwt_secret, algorithm="HS256")
    res_expired = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res_expired.status_code == 401

    # 4. Valid token succeeds
    res_valid = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["id"] == str(user.id)


def test_role_from_database_not_token(client, db_session):
    """A token for a user whose role was changed in the database uses the NEW role."""
    user = _create_user(db_session, email="promoted@proofline.ai", role="creator")
    token = create_access_token(user)

    # Decode token payload to confirm token itself has role 'creator'
    decoded = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], options={"verify_exp": False})
    assert decoded["role"] == "creator"

    # Now change user role in database to admin
    user.role = "admin"
    db_session.commit()

    # /auth/me must return 'admin' because it loads from database
    res_me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["role"] == "admin"

    # /audit requires 'admin'; with updated DB role it returns 200 (not 403)
    res_audit = client.get("/audit", headers={"Authorization": f"Bearer {token}"})
    assert res_audit.status_code == 200


def test_login_audit_log(client, db_session):
    """Login writes a login_success row, and failed login for known user writes login_failed."""
    user = _create_user(db_session, email="audited@proofline.ai", password="GoodPassword123!")

    # Successful login
    res_success = client.post(
        "/auth/login",
        json={"email": "audited@proofline.ai", "password": "GoodPassword123!"},
    )
    assert res_success.status_code == 200

    success_log = db_session.scalars(
        select(AuditLog)
        .where(AuditLog.user_id == user.id, AuditLog.action == "login_success")
    ).first()
    assert success_log is not None
    assert success_log.organisation_id == user.organisation_id
    assert "password" not in str(success_log.details)
    assert "token" not in str(success_log.details)

    # Failed login for known user
    res_fail = client.post(
        "/auth/login",
        json={"email": "audited@proofline.ai", "password": "BadPassword123!"},
    )
    assert res_fail.status_code == 401

    fail_log = db_session.scalars(
        select(AuditLog)
        .where(
            AuditLog.organisation_id == user.organisation_id,
            AuditLog.action == "login_failed",
            AuditLog.user_id.is_(None),
        )
    ).first()
    assert fail_log is not None
    assert "password" not in str(fail_log.details)


def test_password_hashes_never_returned(client, db_session):
    """Password and password hashes never appear in any API response."""
    _create_user(db_session, email="sensitive@proofline.ai", password="SecretPassphrase123!")

    login_res = client.post(
        "/auth/login",
        json={"email": "sensitive@proofline.ai", "password": "SecretPassphrase123!"},
    )
    token = login_res.json()["access_token"]
    login_text = login_res.text.lower()
    assert "password_hash" not in login_text
    assert "hashed_password" not in login_text
    assert "secretpassphrase123!" not in login_text

    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    me_text = me_res.text.lower()
    assert "password" not in me_text
    assert "password_hash" not in me_text


# ---------------------------------------------------------------------------
# Parametrised permission matrix tests
# ---------------------------------------------------------------------------

MATRIX_ENDPOINTS = [
    ("GET", "/health", {"creator", "reviewer", "admin", "unauthenticated"}, 200),
    ("POST", "/auth/login", {"creator", "reviewer", "admin", "unauthenticated"}, 200),
    ("GET", "/auth/me", {"creator", "reviewer", "admin"}, 200),
    ("GET", "/sources", {"creator", "reviewer", "admin"}, 200),
    ("POST", "/sources/guidelines", {"admin"}, 422),
    ("POST", "/sources/facts", {"admin"}, 422),
    ("POST", "/sources/terms", {"admin"}, 422),
    ("POST", "/drafts", {"creator"}, 422),
    ("POST", "/drafts/11111111-1111-1111-1111-111111111111/review", {"creator"}, 404),
    ("GET", "/drafts/11111111-1111-1111-1111-111111111111/versions/1/findings", {"creator", "reviewer"}, 404),
    ("PATCH", "/findings/11111111-1111-1111-1111-111111111111", {"creator"}, 404),
    ("POST", "/drafts/11111111-1111-1111-1111-111111111111/request-review", {"creator"}, 404),
    ("POST", "/drafts/11111111-1111-1111-1111-111111111111/comments", {"creator", "reviewer"}, 422),
    ("POST", "/drafts/11111111-1111-1111-1111-111111111111/decision", {"reviewer"}, 422),
    ("GET", "/drafts/11111111-1111-1111-1111-111111111111/receipt", {"creator", "reviewer", "admin"}, 404),
    ("GET", "/insights/rules", {"reviewer", "admin"}, 200),
    ("GET", "/audit", {"admin"}, 200),
]

ROLES = ["creator", "reviewer", "admin"]


@pytest.mark.parametrize("method,path,allowed_roles,success_status", MATRIX_ENDPOINTS)
@pytest.mark.parametrize("test_role", ROLES)
def test_permission_matrix_authenticated(
    client, db_session, method, path, allowed_roles, success_status, test_role
):
    """Verify that for each endpoint and role, allowed roles get 200/501 and others get 403."""
    user = _create_user(db_session, email=f"{test_role}_{uuid.uuid4().hex[:6]}@proofline.ai", role=test_role)
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"email": user.email, "password": "ValidPassword123!"} if path == "/auth/login" else {}

    res = client.request(method, path, headers=headers, json=payload if method != "GET" else None)

    if test_role in allowed_roles:
        assert res.status_code == success_status, (
            f"Expected {success_status} for {method} {path} with role {test_role}, got {res.status_code}: {res.text}"
        )
    else:
        assert res.status_code == 403, (
            f"Expected 403 for {method} {path} with role {test_role}, got {res.status_code}: {res.text}"
        )
        assert res.json()["detail"] == "Not allowed for your role"


@pytest.mark.parametrize("method,path,allowed_roles,success_status", MATRIX_ENDPOINTS)
def test_permission_matrix_unauthenticated(client, method, path, allowed_roles, success_status):
    """Verify that unauthenticated access returns 200 for public and 401 for protected."""
    payload = {"email": "public@proofline.ai", "password": "wrong"} if path == "/auth/login" else {}
    res = client.request(method, path, json=payload if method != "GET" else None)

    if "unauthenticated" in allowed_roles:
        # Public endpoint
        if path == "/auth/login":
            assert res.status_code == 401
            assert res.json()["detail"] == "Invalid email or password"
        else:
            assert res.status_code == success_status
    else:
        # Protected endpoint without token must return 401
        assert res.status_code == 401
        assert res.json()["detail"] == "Not authenticated"
