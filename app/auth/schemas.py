"""Authentication request and response schemas."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.auth.models import User, UserRole

EMAIL_PATTERN = re.compile(
    r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$",
    re.IGNORECASE,
)


def normalize_email(value: str) -> str:
    """Apply a small, dependency-free email normalization and validation."""
    normalized = value.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("invalid email address")
    return normalized


class RegisterRequest(BaseModel):
    """New-account credentials."""

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class LoginRequest(BaseModel):
    """Existing-account credentials."""

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class RefreshRequest(BaseModel):
    """Request containing a refresh token to rotate."""

    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    """Request containing the refresh token to revoke."""

    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """Bearer access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """Public user representation."""

    id: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> UserResponse:
        return cls(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        )
