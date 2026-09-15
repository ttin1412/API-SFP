"""Authentication domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """Roles understood by API authorization policies."""

    USER = "user"
    ADMIN = "admin"


@dataclass(frozen=True)
class User:
    """A registered API user."""

    id: str
    email: str
    password_hash: str
    role: UserRole
    is_active: bool
    created_at: datetime


@dataclass(frozen=True)
class RefreshSession:
    """Server-side state for a refresh token."""

    id: str
    user_id: str
    expires_at: datetime
    revoked_at: datetime | None = None
