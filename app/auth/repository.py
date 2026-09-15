"""Persistence contracts and an in-memory authentication repository."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from threading import RLock
from typing import Protocol

from app.auth.models import RefreshSession, User


class AuthRepository(Protocol):
    """Storage operations required by the authentication service."""

    def get_user_by_id(self, user_id: str) -> User | None: ...

    def get_user_by_email(self, email: str) -> User | None: ...

    def create_user(self, user: User) -> bool: ...

    def create_refresh_session(self, session: RefreshSession) -> None: ...

    def get_refresh_session(self, session_id: str) -> RefreshSession | None: ...

    def revoke_refresh_session(self, session_id: str, revoked_at: datetime) -> bool: ...


class InMemoryAuthRepository:
    """Thread-safe repository used until persistent storage is introduced."""

    def __init__(self) -> None:
        self._users_by_id: dict[str, User] = {}
        self._user_ids_by_email: dict[str, str] = {}
        self._sessions: dict[str, RefreshSession] = {}
        self._lock = RLock()

    def get_user_by_id(self, user_id: str) -> User | None:
        with self._lock:
            return self._users_by_id.get(user_id)

    def get_user_by_email(self, email: str) -> User | None:
        with self._lock:
            user_id = self._user_ids_by_email.get(email)
            return self._users_by_id.get(user_id) if user_id else None

    def create_user(self, user: User) -> bool:
        with self._lock:
            if user.email in self._user_ids_by_email:
                return False
            self._users_by_id[user.id] = user
            self._user_ids_by_email[user.email] = user.id
            return True

    def create_refresh_session(self, session: RefreshSession) -> None:
        with self._lock:
            self._sessions[session.id] = session

    def get_refresh_session(self, session_id: str) -> RefreshSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def revoke_refresh_session(self, session_id: str, revoked_at: datetime) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.revoked_at is not None:
                return False
            self._sessions[session_id] = replace(session, revoked_at=revoked_at)
            return True
