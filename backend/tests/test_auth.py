"""Integration tests for authentication endpoints."""

import pyotp

from core.security import verify_password
from tests.conftest import auth_headers_for


def test_login_success(client, seed_data):
    response = client.post(
        "/auth/login",
        json={"email": "cadet1@cadence.ncc", "password": "CadencePass123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "cadet1@cadence.ncc"
    assert data["user"]["role"] == "Cadet"


def test_login_invalid_password(client, seed_data):
    response = client.post(
        "/auth/login",
        json={"email": "cadet1@cadence.ncc", "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_get_current_user_profile(client, seed_data):
    cadet1 = seed_data["cadet1"]
    headers = auth_headers_for(cadet1)

    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == cadet1.id
    assert data["email"] == cadet1.email
    assert data["full_name"] == cadet1.full_name


def test_get_current_user_unauthorized(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_refresh_token_rotation(client, seed_data):
    # Step 1: Login to get initial tokens
    login_res = client.post(
        "/auth/login",
        json={"email": "cadet1@cadence.ncc", "password": "CadencePass123!"},
    )
    assert login_res.status_code == 200
    initial_refresh = login_res.json()["refresh_token"]

    # Step 2: Use refresh token to rotate
    refresh_res = client.post(
        "/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    assert refresh_res.status_code == 200
    rotated_data = refresh_res.json()
    new_refresh = rotated_data["refresh_token"]
    assert new_refresh != initial_refresh

    # Step 3: Replaying the old refresh token must be rejected (revoked)
    replay_res = client.post(
        "/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    assert replay_res.status_code == 401


def test_logout(client, seed_data):
    login_res = client.post(
        "/auth/login",
        json={"email": "cadet1@cadence.ncc", "password": "CadencePass123!"},
    )
    refresh_token = login_res.json()["refresh_token"]

    logout_res = client.post(
        "/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Successfully logged out"

    # Refreshing with the logged out token must fail
    refresh_res = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 401


def test_change_password(client, seed_data, db_session):
    cadet1 = seed_data["cadet1"]
    headers = auth_headers_for(cadet1)

    response = client.post(
        "/auth/change-password",
        json={
            "current_password": "CadencePass123!",
            "new_password": "NewSecretPassword987!",
        },
        headers=headers,
    )
    assert response.status_code == 200

    # Verify password updated in database
    db_session.refresh(cadet1)
    assert verify_password("NewSecretPassword987!", cadet1.hashed_password) is True


def test_ano_reset_password(client, seed_data, db_session):
    ano = seed_data["ano"]
    cadet1 = seed_data["cadet1"]
    ano_headers = auth_headers_for(ano)

    response = client.post(
        "/auth/reset-password",
        json={
            "user_id": cadet1.id,
            "new_password": "AdminResetPassword456!",
        },
        headers=ano_headers,
    )
    assert response.status_code == 200

    # Verify cadet's password is reset and must_change_password is True
    db_session.refresh(cadet1)
    assert verify_password("AdminResetPassword456!", cadet1.hashed_password) is True
    assert cadet1.must_change_password is True


def test_cadet_cannot_reset_password(client, seed_data):
    cadet1 = seed_data["cadet1"]
    cadet2 = seed_data["cadet2"]
    cadet_headers = auth_headers_for(cadet1)

    response = client.post(
        "/auth/reset-password",
        json={
            "user_id": cadet2.id,
            "new_password": "UnauthorizedReset!",
        },
        headers=cadet_headers,
    )
    assert response.status_code == 403


def test_mfa_flow(client, seed_data, db_session):
    cadet1 = seed_data["cadet1"]
    headers = auth_headers_for(cadet1)

    # 1. Initiate MFA setup
    setup_res = client.post("/auth/mfa/setup", headers=headers)
    assert setup_res.status_code == 200
    setup_data = setup_res.json()
    secret = setup_data["secret"]
    assert "qr_code_data_uri" in setup_data
    assert setup_data["qr_code_data_uri"].startswith("data:image/png;base64,")

    # 2. Verify with valid TOTP code
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()

    verify_res = client.post(
        "/auth/mfa/verify",
        json={"code": valid_code},
        headers=headers,
    )
    assert verify_res.status_code == 200

    # 3. Next login without MFA code must be blocked
    login_no_mfa = client.post(
        "/auth/login",
        json={"email": "cadet1@cadence.ncc", "password": "CadencePass123!"},
    )
    assert login_no_mfa.status_code == 403

    # 4. Next login with valid MFA code succeeds
    fresh_code = totp.now()
    login_with_mfa = client.post(
        "/auth/login",
        json={
            "email": "cadet1@cadence.ncc",
            "password": "CadencePass123!",
            "mfa_code": fresh_code,
        },
    )
    assert login_with_mfa.status_code == 200
    assert "access_token" in login_with_mfa.json()
