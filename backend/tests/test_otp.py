"""Unit and integration tests for finalized OTP rules and verification logic."""

from datetime import timedelta

import pytest
from fastapi import HTTPException

from core.models import OtpCode, OtpPurpose, utc_now
from modules.auth.service import generate_otp, verify_otp


def test_otp_generation_and_verification(seed_data, db_session):
    user = seed_data["cadet1"]
    otp_code = generate_otp(db_session, user, OtpPurpose.EMAIL_MFA)

    assert len(otp_code) == 6
    assert otp_code.isdigit()

    # Verify code is hashed in database, not stored plaintext
    record = (
        db_session.query(OtpCode)
        .filter(OtpCode.user_id == user.id, OtpCode.purpose == OtpPurpose.EMAIL_MFA.value)
        .first()
    )
    assert record is not None
    assert record.code_hash != otp_code
    assert record.attempt_count == 0
    assert record.consumed_at is None

    # Verify OTP successfully
    assert verify_otp(db_session, user, OtpPurpose.EMAIL_MFA, otp_code) is True

    # Single-use enforcement: record should now be consumed
    db_session.refresh(record)
    assert record.consumed_at is not None

    # Subsequent verification must fail (single-use)
    with pytest.raises(HTTPException, match="No active OTP found"):
        verify_otp(db_session, user, OtpPurpose.EMAIL_MFA, otp_code)


def test_otp_five_attempt_limit(seed_data, db_session):
    user = seed_data["cadet1"]
    otp_code = generate_otp(db_session, user, OtpPurpose.PASSWORD_RESET)

    # Attempts 1 through 4 fail with attempts remaining
    for i in range(1, 5):
        with pytest.raises(HTTPException, match="attempt\\(s\\) remaining"):
            verify_otp(db_session, user, OtpPurpose.PASSWORD_RESET, "000000")

    # 5th attempt fails and invalidates the OTP
    with pytest.raises(HTTPException, match="attempt\\(s\\) remaining"):
        verify_otp(db_session, user, OtpPurpose.PASSWORD_RESET, "000000")

    # 6th attempt should report maximum verification attempts exceeded or no active OTP
    with pytest.raises(HTTPException, match="Maximum verification attempts exceeded|No active OTP"):
        verify_otp(db_session, user, OtpPurpose.PASSWORD_RESET, otp_code)


def test_otp_expiration(seed_data, db_session):
    user = seed_data["cadet1"]
    otp_code = generate_otp(db_session, user, OtpPurpose.EMAIL_MFA)

    # Manually expire the OTP (simulate 6 minutes elapsed)
    record = (
        db_session.query(OtpCode)
        .filter(OtpCode.user_id == user.id, OtpCode.purpose == OtpPurpose.EMAIL_MFA.value)
        .first()
    )
    record.expires_at = utc_now() - timedelta(minutes=1)
    db_session.add(record)
    db_session.flush()

    with pytest.raises(HTTPException, match="OTP has expired"):
        verify_otp(db_session, user, OtpPurpose.EMAIL_MFA, otp_code)


def test_previous_otp_invalidation(seed_data, db_session):
    user = seed_data["cadet1"]

    # Issue first OTP
    first_otp = generate_otp(db_session, user, OtpPurpose.PASSWORD_RESET)

    # Issue second OTP for same user and purpose
    second_otp = generate_otp(db_session, user, OtpPurpose.PASSWORD_RESET)

    assert first_otp != second_otp

    # Attempting to use the first OTP must fail because it was invalidated
    with pytest.raises(HTTPException, match="Invalid OTP code"):
        verify_otp(db_session, user, OtpPurpose.PASSWORD_RESET, first_otp)

    # Second OTP succeeds
    assert verify_otp(db_session, user, OtpPurpose.PASSWORD_RESET, second_otp) is True
