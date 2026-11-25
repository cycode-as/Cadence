"""Pydantic schemas for authentication and authorization."""


from pydantic import BaseModel, ConfigDict, EmailStr, Field

from core.models import Role


class UserBrief(BaseModel):
    """Brief user representation for authentication responses."""

    id: int
    email: str
    full_name: str
    cadet_number: str | None = None
    rank: str | None = None
    role: Role
    unit_id: int | None = None
    squad_id: int | None = None
    mfa_enabled: bool
    must_change_password: bool

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    """User login request payload."""

    email: EmailStr
    password: str
    mfa_code: str | None = None


class TokenResponse(BaseModel):
    """Successful authentication response containing tokens and user data."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserBrief


class RefreshTokenRequest(BaseModel):
    """Refresh token request payload (if not sent via cookie)."""

    refresh_token: str | None = None


class ChangePasswordRequest(BaseModel):
    """Password change request payload."""

    current_password: str
    new_password: str = Field(min_length=8)


class ResetPasswordRequest(BaseModel):
    """ANO/CO administrative password reset request payload."""

    user_id: int
    new_password: str = Field(min_length=8)


class MFASetupResponse(BaseModel):
    """Response containing MFA provisioning details."""

    secret: str
    provisioning_uri: str
    qr_code_data_uri: str


class MFAVerifyRequest(BaseModel):
    """Payload to verify TOTP code."""

    code: str = Field(min_length=6, max_length=6)
