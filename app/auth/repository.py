"""Authentication persistence contracts and repository implementations."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from threading import RLock
from typing import Callable, Protocol
from uuid import uuid4

from google.cloud import firestore
from google.cloud.firestore_v1 import DocumentSnapshot
from google.cloud.firestore_v1.base_query import FieldFilter

from app.auth.models import NewRefreshSession, NewUser, RefreshSession, User, UserRole


class AuthRepository(Protocol):
    """Storage operations required by the authentication service."""

    def get_user_by_id(self, user_id: str) -> User | None: ...

    def get_user_by_email(self, email: str) -> User | None: ...

    def create_user(self, user: NewUser) -> User | None: ...

    def create_refresh_session(self, session: NewRefreshSession) -> RefreshSession: ...

    def get_refresh_session(
        self, user_id: str, session_id: str
    ) -> RefreshSession | None: ...

    def revoke_refresh_session(
        self, user_id: str, session_id: str, revoked_at: datetime
    ) -> bool: ...


class InMemoryAuthRepository:
    """Thread-safe repository for tests and ephemeral local development."""

    def __init__(self) -> None:
        self._users_by_id: dict[str, User] = {}
        self._user_ids_by_email: dict[str, str] = {}
        self._sessions: dict[tuple[str, str], RefreshSession] = {}
        self._lock = RLock()

    def get_user_by_id(self, user_id: str) -> User | None:
        with self._lock:
            return self._users_by_id.get(user_id)

    def get_user_by_email(self, email: str) -> User | None:
        with self._lock:
            user_id = self._user_ids_by_email.get(email)
            return self._users_by_id.get(user_id) if user_id else None

    def create_user(self, user: NewUser) -> User | None:
        with self._lock:
            if user.email in self._user_ids_by_email:
                return None
            stored_user = User(id=str(uuid4()), **vars(user))
            self._users_by_id[stored_user.id] = stored_user
            self._user_ids_by_email[stored_user.email] = stored_user.id
            return stored_user

    def create_refresh_session(self, session: NewRefreshSession) -> RefreshSession:
        with self._lock:
            stored_session = RefreshSession(id=str(uuid4()), **vars(session))
            self._sessions[(stored_session.user_id, stored_session.id)] = stored_session
            return stored_session

    def get_refresh_session(
        self, user_id: str, session_id: str
    ) -> RefreshSession | None:
        with self._lock:
            return self._sessions.get((user_id, session_id))

    def revoke_refresh_session(
        self, user_id: str, session_id: str, revoked_at: datetime
    ) -> bool:
        with self._lock:
            session_key = (user_id, session_id)
            session = self._sessions.get(session_key)
            if session is None or session.revoked_at is not None:
                return False
            self._sessions[session_key] = replace(session, revoked_at=revoked_at)
            return True


class FirestoreAuthRepository:
    """Persist user accounts and refresh sessions in Firestore."""

    USERS_COLLECTION = "users"
    SESSIONS_COLLECTION = "refresh_sessions"

    def __init__(self, client_factory: Callable[[], firestore.Client]) -> None:
        # Lazy creation lets health checks run before cloud credentials are used.
        self._client_factory = client_factory

    @property
    def client(self) -> firestore.Client:
        return self._client_factory()

    def get_user_by_id(self, user_id: str) -> User | None:
        snapshot = self.client.collection(self.USERS_COLLECTION).document(user_id).get()
        return self._user_from_snapshot(snapshot)

    def get_user_by_email(self, email: str) -> User | None:
        snapshots = self._query_by_email(email).stream()
        snapshot = next(iter(snapshots), None)
        return self._user_from_snapshot(snapshot) if snapshot is not None else None

    def create_user(self, user: NewUser) -> User | None:
        client = self.client
        users = client.collection(self.USERS_COLLECTION)
        user_ref = users.document()
        email_query = users.where(filter=FieldFilter("email", "==", user.email)).limit(
            1
        )
        transaction = client.transaction()

        @firestore.transactional
        def create_in_transaction(
            active_transaction: firestore.Transaction,
        ) -> User | None:
            if next(active_transaction.get(email_query), None) is not None:
                return None
            active_transaction.create(
                user_ref,
                {
                    "email": user.email,
                    "password_hash": user.password_hash,
                    "role": user.role.value,
                    "is_active": user.is_active,
                    "created_at": user.created_at,
                },
            )
            return User(id=user_ref.id, **vars(user))

        return create_in_transaction(transaction)

    def create_refresh_session(self, session: NewRefreshSession) -> RefreshSession:
        session_ref = self._session_collection(session.user_id).document()
        stored_session = RefreshSession(id=session_ref.id, **vars(session))
        session_ref.create(
            {
                "user_id": session.user_id,
                "expires_at": session.expires_at,
                "revoked_at": None,
            }
        )
        return stored_session

    def get_refresh_session(
        self, user_id: str, session_id: str
    ) -> RefreshSession | None:
        snapshot = self._session_document(user_id, session_id).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        return RefreshSession(
            id=snapshot.id,
            user_id=data["user_id"],
            expires_at=data["expires_at"],
            revoked_at=data.get("revoked_at"),
        )

    def revoke_refresh_session(
        self, user_id: str, session_id: str, revoked_at: datetime
    ) -> bool:
        client = self.client
        session_ref = self._session_document(user_id, session_id)
        transaction = client.transaction()

        @firestore.transactional
        def revoke_in_transaction(
            active_transaction: firestore.Transaction,
        ) -> bool:
            snapshot = session_ref.get(transaction=active_transaction)
            if not snapshot.exists:
                return False
            data = snapshot.to_dict() or {}
            if data.get("revoked_at") is not None:
                return False
            active_transaction.update(session_ref, {"revoked_at": revoked_at})
            return True

        return revoke_in_transaction(transaction)

    def _session_document(self, user_id: str, session_id: str):
        return self._session_collection(user_id).document(session_id)

    def _session_collection(self, user_id: str):
        return (
            self.client.collection(self.USERS_COLLECTION)
            .document(user_id)
            .collection(self.SESSIONS_COLLECTION)
        )

    def _query_by_email(self, email: str):
        return (
            self.client.collection(self.USERS_COLLECTION)
            .where(filter=FieldFilter("email", "==", email))
            .limit(1)
        )

    @staticmethod
    def _user_from_snapshot(snapshot: DocumentSnapshot | None) -> User | None:
        if snapshot is None or not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        return User(
            id=snapshot.id,
            email=data["email"],
            password_hash=data["password_hash"],
            role=UserRole(data["role"]),
            is_active=data["is_active"],
            created_at=data["created_at"],
        )
