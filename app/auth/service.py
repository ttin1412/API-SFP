"""Password authentication and signed token lifecycle services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.auth.models import RefreshSession, User, UserRole
from app.auth.repository import AuthRepository
from app.auth.schemas import TokenResponse, normalize_email
from app.config.settings import Settings


class AuthenticationError(Exception):
    """Raised when supplied credentials or tokens cannot be authenticated."""


class EmailAlreadyRegisteredError(Exception):
    """Raised when account creation conflicts with an existing email."""


@dataclass(frozen=True)
class TokenClaims:
    """Validated claims needed by the application."""

    subject: str
    token_type: str
    token_id: str
    expires_at: datetime


class AuthService:
    """Coordinate users, password verification, and JWT issuance."""

    def __init__(self, repository: AuthRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self.password_hash = PasswordHash.recommended()
        self._dummy_password_hash = self.password_hash.hash(str(uuid4()))

    def register(self, email: str, password: str) -> User:
        now = self._now()
        user = User(
            id=str(uuid4()),
            email=normalize_email(email),
            password_hash=self.password_hash.hash(password),
            role=UserRole.USER,
            is_active=True,
            created_at=now,
        )
        if not self.repository.create_user(user):
            raise EmailAlreadyRegisteredError
        return user

    def login(self, email: str, password: str) -> TokenResponse:
        user = self.repository.get_user_by_email(normalize_email(email))
        password_matches = self.password_hash.verify(
            password,
            user.password_hash if user is not None else self._dummy_password_hash,
        )
        if user is None or not user.is_active or not password_matches:
            raise AuthenticationError
        return self._issue_token_pair(user)

    def refresh(self, refresh_token: str) -> TokenResponse:
        claims = self.decode_token(refresh_token, expected_type="refresh")
        session = self.repository.get_refresh_session(claims.token_id)
        now = self._now()
        if (
            session is None
            or session.user_id != claims.subject
            or session.revoked_at is not None
            or session.expires_at <= now
        ):
            raise AuthenticationError

        user = self.repository.get_user_by_id(claims.subject)
        if user is None or not user.is_active:
            raise AuthenticationError

        # Refresh tokens are single use. Rotation limits the impact of theft.
        if not self.repository.revoke_refresh_session(session.id, now):
            raise AuthenticationError
        return self._issue_token_pair(user)

    def logout(self, refresh_token: str) -> None:
        claims = self.decode_token(refresh_token, expected_type="refresh")
        session = self.repository.get_refresh_session(claims.token_id)
        if session is None or session.user_id != claims.subject:
            raise AuthenticationError
        # Logging out twice has the same final state and is intentionally idempotent.
        self.repository.revoke_refresh_session(session.id, self._now())

    def authenticate_access_token(self, access_token: str) -> User:
        claims = self.decode_token(access_token, expected_type="access")
        user = self.repository.get_user_by_id(claims.subject)
        if user is None or not user.is_active:
            raise AuthenticationError
        return user

    def decode_token(self, token: str, expected_type: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
                audience=self.settings.jwt_audience,
                issuer=self.settings.jwt_issuer,
                options={"require": ["sub", "type", "jti", "iat", "exp"]},
            )
            if payload["type"] != expected_type:
                raise AuthenticationError
            expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            return TokenClaims(
                subject=payload["sub"],
                token_type=payload["type"],
                token_id=payload["jti"],
                expires_at=expires_at,
            )
        except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError from exc

    def _issue_token_pair(self, user: User) -> TokenResponse:
        now = self._now()
        access_expires = now + timedelta(
            minutes=self.settings.access_token_expire_minutes
        )
        refresh_expires = now + timedelta(days=self.settings.refresh_token_expire_days)
        refresh_id = str(uuid4())

        access_token = self._encode_token(
            user=user,
            token_type="access",
            token_id=str(uuid4()),
            now=now,
            expires_at=access_expires,
        )
        refresh_token = self._encode_token(
            user=user,
            token_type="refresh",
            token_id=refresh_id,
            now=now,
            expires_at=refresh_expires,
        )
        self.repository.create_refresh_session(
            RefreshSession(
                id=refresh_id,
                user_id=user.id,
                expires_at=refresh_expires,
            )
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.settings.access_token_expire_minutes * 60,
        )

    def _encode_token(
        self,
        *,
        user: User,
        token_type: str,
        token_id: str,
        now: datetime,
        expires_at: datetime,
    ) -> str:
        return jwt.encode(
            {
                "sub": user.id,
                "type": token_type,
                "role": user.role.value,
                "jti": token_id,
                "iat": now,
                "exp": expires_at,
                "iss": self.settings.jwt_issuer,
                "aud": self.settings.jwt_audience,
            },
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
