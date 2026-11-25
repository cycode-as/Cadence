"""Authentication service implementing token rotation, M3 persistence, and OTP rules."""

import base64
import hashlib
import io
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
import qrcode
from fastapi import HTTPException, Response, status
from sqlalchemy.orm import Session

from core.config import settings
from core.models import OtpCode, OtpPurpose, RefreshToken, Role, User, new_uuid, utc_now
from core.security import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from modules.auth.schemas import MFASetupResponse, TokenResponse, UserBrief


def hash_token_or_code(value: str) -> str:
    """Compute SHA-256 hash of a token string or OTP code."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def authenticate_user(
    db: Session,
    email: str,
    password: str,
    mfa_code: str | None = None,
) -> User:
    """Verify user credentials, Argon2 password hash, and TOTP MFA if enabled."""
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Rehash password if algorithm parameters updated
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(password)
        db.add(user)
        db.flush()

    # Mandatory MFA for CO and ANO, or any user with MFA enabled
    requires_mfa = user.mfa_enabled or user.role in (Role.CO, Role.ANO)
    if requires_mfa and user.mfa_secret:
        if not mfa_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MFA code required for this account",
            )
        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(mfa_code.strip(), valid_window=1):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA code",
            )

    return user


def issue_tokens(
    db: Session,
    user: User,
    response: Response | None = None,
    replaced_token_id: str | None = None,
) -> TokenResponse:
    """Generate access and refresh tokens, store refresh session, and set cookies."""
    scopes = {
        "unit_id": user.unit_id,
        "squad_id": user.squad_id,
    }
    access_token = create_access_token(
        subject=user.id,
        role=user.role.value,
        scopes=scopes,
    )
    refresh_token = create_refresh_token(subject=user.id)

    # Decode refresh token to get exp
    payload = decode_token(refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    exp_ts = payload["exp"]
    expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc).replace(tzinfo=None)

    # Store hashed refresh token in database
    token_hash = hash_token_or_code(refresh_token)
    stored_token = RefreshToken(
        id=new_uuid(),
        user_id=user.id,
        unit_id=user.unit_id,
        token_hash=token_hash,
        expires_at=expires_at,
        revoked_at=None,
        replaced_by_token_id=None,
    )
    db.add(stored_token)
    db.flush()

    # Link previous token if this was a rotation
    if replaced_token_id:
        old_token = db.query(RefreshToken).filter(RefreshToken.id == replaced_token_id).first()
        if old_token:
            old_token.replaced_by_token_id = stored_token.id
            db.add(old_token)
            db.flush()

    # Set HTTP-only secure cookies if response object is provided
    if response:
        is_secure = not settings.debug
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=is_secure,
            samesite="lax",
            max_age=settings.access_token_expire_minutes * 60,
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=is_secure,
            samesite="lax",
            max_age=settings.refresh_token_expire_days * 86400,
        )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserBrief.model_validate(user),
    )


def rotate_refresh_token(
    db: Session,
    refresh_token: str,
    response: Response | None = None,
) -> TokenResponse:
    """Validate old refresh token, revoke it, and issue a fresh pair (with reuse detection)."""
    try:
        payload = decode_token(refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed refresh token",
        )

    token_hash = hash_token_or_code(refresh_token)
    token_record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )

    if not token_record or token_record.revoked_at is not None:
        # Reuse detection: an already-revoked or non-existent token was submitted!
        # Invalidate all active tokens for this user as a security measure.
        now = utc_now()
        db.query(RefreshToken).filter(
            RefreshToken.user_id == int(sub),
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": now})
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Revoked refresh token presented. Security alert: session terminated.",
        )

    # Revoke current token
    token_record.revoked_at = utc_now()
    db.add(token_record)
    db.flush()

    user = db.query(User).filter(User.id == int(sub)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer active",
        )

    return issue_tokens(db, user, response=response, replaced_token_id=token_record.id)


def revoke_tokens(
    db: Session,
    refresh_token: str | None = None,
    response: Response | None = None,
) -> None:
    """Revoke refresh token session and clear authentication cookies."""
    if refresh_token:
        try:
            token_hash = hash_token_or_code(refresh_token)
            token_record = (
                db.query(RefreshToken)
                .filter(RefreshToken.token_hash == token_hash)
                .first()
            )
            if token_record and token_record.revoked_at is None:
                token_record.revoked_at = utc_now()
                db.add(token_record)
                db.flush()
        except Exception:
            pass

    if response:
        response.delete_cookie(key="access_token")
        response.delete_cookie(key="refresh_token")


# =========================================================================
# Finalized OTP Service Rules (EMAIL_MFA & PASSWORD_RESET)
# =========================================================================

def generate_otp(
    db: Session,
    user: User,
    purpose: OtpPurpose | str,
) -> str:
    """Generate a single-use 6-digit OTP adhering to finalized requirements:

    - 5 minutes expiration.
    - Invalidates any previous active OTP for the same user and purpose.
    - Stores SHA-256 hash of the OTP code in database.
    - Returns the plaintext code to be delivered to the user.
    """
    purpose_str = purpose.value if isinstance(purpose, OtpPurpose) else str(purpose)
    now = utc_now()

    # Rule: Issuing a new OTP invalidates the previous active OTP for the same user and purpose
    db.query(OtpCode).filter(
        OtpCode.user_id == user.id,
        OtpCode.purpose == purpose_str,
        OtpCode.consumed_at.is_(None),
    ).update({"consumed_at": now})
    db.flush()

    # Generate 6-digit secure numerical OTP
    code = f"{secrets.randbelow(1_000_000):06d}"
    code_hash = hash_token_or_code(code)
    expires_at = now + timedelta(minutes=5)

    otp_record = OtpCode(
        id=new_uuid(),
        user_id=user.id,
        unit_id=user.unit_id,
        code_hash=code_hash,
        purpose=purpose_str,
        expires_at=expires_at,
        consumed_at=None,
        attempt_count=0,
    )
    db.add(otp_record)
    db.flush()

    return code


def verify_otp(
    db: Session,
    user: User,
    purpose: OtpPurpose | str,
    code: str,
) -> bool:
    """Verify an OTP adhering to finalized verification rules:

    - Maximum 5 attempts per OTP.
    - Invalidate OTP after 5 failed attempts.
    - Expiration: 5 minutes.
    - Single-use verification.
    - Reject expired or consumed OTPs.
    """
    purpose_str = purpose.value if isinstance(purpose, OtpPurpose) else str(purpose)
    now = utc_now()

    otp_record = (
        db.query(OtpCode)
        .filter(
            OtpCode.user_id == user.id,
            OtpCode.purpose == purpose_str,
            OtpCode.consumed_at.is_(None),
        )
        .order_by(OtpCode.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active OTP found. Please request a new OTP.",
        )

    # Check 5-minute expiration
    record_expires_at = otp_record.expires_at
    if record_expires_at.tzinfo is None:
        record_expires_at = record_expires_at.replace(tzinfo=timezone.utc)

    if now > record_expires_at:
        otp_record.consumed_at = now
        db.add(otp_record)
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new OTP.",
        )

    # Check 5-attempt limit
    if otp_record.attempt_count >= 5:
        otp_record.consumed_at = now
        db.add(otp_record)
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts exceeded. Please request a new OTP.",
        )

    # Increment attempt count
    otp_record.attempt_count += 1
    input_hash = hash_token_or_code(code.strip())

    if input_hash != otp_record.code_hash:
        if otp_record.attempt_count >= 5:
            otp_record.consumed_at = now
        db.add(otp_record)
        db.flush()
        remaining = max(0, 5 - otp_record.attempt_count)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OTP code. {remaining} attempt(s) remaining.",
        )

    # Single-use enforcement: mark as consumed
    otp_record.consumed_at = now
    db.add(otp_record)
    db.flush()
    return True


# =========================================================================
# PyOTP TOTP MFA (Authenticator app)
# =========================================================================

def setup_mfa(db: Session, user: User) -> MFASetupResponse:
    """Generate a TOTP secret and QR code for authenticator setup."""
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    db.add(user)
    db.flush()

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.email,
        issuer_name="Cadence NCC Platform",
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=2,
    )
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_qr = base64.b64encode(buffer.getvalue()).decode("utf-8")
    qr_data_uri = f"data:image/png;base64,{b64_qr}"

    return MFASetupResponse(
        secret=secret,
        provisioning_uri=provisioning_uri,
        qr_code_data_uri=qr_data_uri,
    )


def verify_and_enable_mfa(db: Session, user: User, code: str) -> bool:
    """Verify code and officially activate MFA on the user account."""
    if not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup has not been initiated for this account",
        )

    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(code.strip(), valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA verification code",
        )

    user.mfa_enabled = True
    db.add(user)
    db.flush()
    return True
