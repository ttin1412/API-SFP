"""Unit tests for the Firestore authentication repository adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.auth.models import NewUser, UserRole
from app.auth.repository import FirestoreAuthRepository


class FakeSnapshot:
    def __init__(self, document_id: str, data: dict[str, Any] | None) -> None:
        self.id = document_id
        self.exists = data is not None
        self._data = data

    def to_dict(self) -> dict[str, Any] | None:
        return self._data


class FakeDocument:
    def __init__(
        self,
        documents: dict[str, dict[str, Any]],
        document_id: str,
        subcollections: dict[str, dict[str, dict[str, Any]]],
    ) -> None:
        self.documents = documents
        self.document_id = document_id
        self.id = document_id
        self.subcollections = subcollections

    def get(self, transaction: object = None) -> FakeSnapshot:
        return FakeSnapshot(self.document_id, self.documents.get(self.document_id))

    def create(self, data: dict[str, Any]) -> None:
        self.documents[self.document_id] = data.copy()

    def collection(self, name: str) -> FakeCollection:
        path = f"{self.document_id}/{name}"
        return FakeCollection(
            self.subcollections.setdefault(path, {}), self.subcollections
        )


class FakeCollection:
    def __init__(
        self,
        documents: dict[str, dict[str, Any]],
        subcollections: dict[str, dict[str, dict[str, Any]]],
    ) -> None:
        self.documents = documents
        self.subcollections = subcollections

    def document(self, document_id: str | None = None) -> FakeDocument:
        if document_id is None:
            document_id = f"firestore-id-{len(self.documents) + 1}"
        return FakeDocument(self.documents, document_id, self.subcollections)

    def where(self, *, filter: Any) -> FakeQuery:
        return FakeQuery(self.documents, filter.value)


class FakeQuery:
    def __init__(self, documents: dict[str, dict[str, Any]], email: str) -> None:
        self.documents = documents
        self.email = email

    def limit(self, count: int) -> FakeQuery:
        return self

    def stream(self) -> iter:
        return iter(
            FakeSnapshot(document_id, data)
            for document_id, data in self.documents.items()
            if data["email"] == self.email
        )


class FakeTransaction:
    def get(self, query: FakeQuery) -> iter:
        return query.stream()

    def create(self, document: FakeDocument, data: dict[str, Any]) -> None:
        document.create(data)

    def update(self, document: FakeDocument, data: dict[str, Any]) -> None:
        document.documents[document.document_id].update(data)


class FakeClient:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict[str, Any]]] = {}
        self.subcollections: dict[str, dict[str, dict[str, Any]]] = {}

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(
            self.collections.setdefault(name, {}), self.subcollections
        )

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()


def make_repository(monkeypatch) -> tuple[FirestoreAuthRepository, FakeClient]:
    from app.auth import repository as repository_module

    monkeypatch.setattr(repository_module.firestore, "transactional", lambda fn: fn)
    client = FakeClient()
    repository = FirestoreAuthRepository(lambda: client)  # type: ignore[arg-type]
    return repository, client


def test_firestore_repository_persists_account_and_prevents_duplicate_email(
    monkeypatch,
) -> None:
    repository, client = make_repository(monkeypatch)
    created_at = datetime.now(timezone.utc)
    new_user = NewUser(
        email="user@example.com",
        password_hash="$argon2id$hashed-password",
        role=UserRole.USER,
        is_active=True,
        created_at=created_at,
    )

    user = repository.create_user(new_user)

    assert user is not None
    assert user.id == "firestore-id-1"
    assert repository.create_user(new_user) is None
    assert repository.get_user_by_id(user.id) == user
    assert repository.get_user_by_email(user.email) == user
    assert client.collections["users"][user.id]["password_hash"] == user.password_hash
    assert "id" not in client.collections["users"][user.id]
    assert "user_emails" not in client.collections
