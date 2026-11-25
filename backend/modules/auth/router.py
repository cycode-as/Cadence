"""FastAPI Router for authentication and authorization workflows."""


from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_user, require_roles
from core.models import Role, User
from core.security import hash_password, verify_password
from modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserBrief,
)
from modules.auth.service import (
    authenticate_user,
    issue_tokens,
    revoke_tokens,
    rotate_refresh_token,
    setup_mfa,
    verify_and_enable_mfa,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate user with email, password, and optional TOTP MFA code."""
    user = authenticate_user(
        db,
        email=payload.email,
        password=payload.password,
        mfa_code=payload.mfa_code,
    )
    return issue_tokens(db, user, response=response)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = None,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Rotate and refresh an existing session using a valid refresh token."""
    token_str = None
    if payload and payload.refresh_token:
        token_str = payload.refresh_token
    elif "refresh_token" in request.cookies:
        token_str = request.cookies.get("refresh_token")

    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
        )

    return rotate_refresh_token(db, token_str, response=response)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = None,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Logout user, revoke stored refresh token, and clear cookies."""
    token_str = None
    if payload and payload.refresh_token:
        token_str = payload.refresh_token
    elif "refresh_token" in request.cookies:
        token_str = request.cookies.get("refresh_token")

    revoke_tokens(db, token_str, response=response)
    return {"message": "Successfully logged out"}


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Allow an authenticated user to change their password."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    current_user.hashed_password = hash_password(payload.new_password)
    current_user.must_change_password = False
    db.add(current_user)
    db.flush()
    return {"message": "Password updated successfully"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(
    payload: ResetPasswordRequest,
    current_user: User = Depends(require_roles(Role.CO, Role.ANO)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Administrative password reset initiated by ANO or CO."""
    target_user = db.query(User).filter(User.id == payload.user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Scoped unit check: Officers can only reset passwords within their own unit
    if current_user.unit_id and target_user.unit_id != current_user.unit_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot reset password for a user outside your unit",
        )

    target_user.hashed_password = hash_password(payload.new_password)
    target_user.must_change_password = True
    db.add(target_user)
    db.flush()
    return {"message": f"Password reset successfully for user {target_user.email}"}


@router.post("/mfa/setup", response_model=MFASetupResponse)
def mfa_setup(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MFASetupResponse:
    """Generate TOTP secret and QR code for MFA enrollment."""
    return setup_mfa(db, current_user)


@router.post("/mfa/verify", status_code=status.HTTP_200_OK)
def mfa_verify(
    payload: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Verify TOTP code and activate MFA on the current user's account."""
    verify_and_enable_mfa(db, current_user, payload.code)
    return {"message": "MFA has been successfully activated"}


@router.get("/me", response_model=UserBrief)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserBrief:
    """Retrieve authenticated user's profile and active session scope."""
    return UserBrief.model_validate(current_user)
