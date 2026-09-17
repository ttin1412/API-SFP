"""Unit tests for the Firestore authentication repository adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.auth.models import NewUser, UserRole
from app.auth.repository import FirestoreAuthRepository
from app.files.models import FileMetadata, FileStatus
from app.files.repository import FirestoreFileRepository


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
        return FakeQuery(self.documents, filter.field_path, filter.value)


class FakeQuery:
    def __init__(
        self,
        documents: dict[str, dict[str, Any]],
        field: str,
        value: object,
    ) -> None:
        self.documents = documents
        self.field = field
        self.value = value

    def limit(self, count: int) -> FakeQuery:
        return self

    def stream(self) -> iter:
        return iter(
            FakeSnapshot(document_id, data)
            for document_id, data in self.documents.items()
            if data[self.field] == self.value
        )


class FakeTransaction:
    def get(self, query: FakeQuery) -> iter:
        return query.stream()

    def create(self, document: FakeDocument, data: dict[str, Any]) -> None:
        document.create(data)

    def update(self, document: FakeDocument, data: dict[str, Any]) -> None:
        document.documents[document.document_id].update(data)

    def delete(self, document: FakeDocument) -> None:
        del document.documents[document.document_id]


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


def test_firestore_file_repository_scopes_reads_and_deletes_to_owner(
    monkeypatch,
) -> None:
    from app.files import repository as repository_module

    monkeypatch.setattr(repository_module.firestore, "transactional", lambda fn: fn)
    client = FakeClient()
    repository = FirestoreFileRepository(lambda: client)  # type: ignore[arg-type]
    now = datetime.now(timezone.utc)
    file_id = repository.new_file_id()
    alice_file = FileMetadata(
        id=file_id,
        owner_id="alice",
        original_filename="photo.jpg",
        storage_key=f"quarantine/alice/{file_id}",
        detected_mime_type=None,
        declared_mime_type="image/jpeg",
        extension=".jpg",
        size=128,
        sha256=None,
        status=FileStatus.PENDING_UPLOAD,
        rejection_reason=None,
        created_at=now,
        updated_at=now,
    )

    repository.create(alice_file)

    assert alice_file.id == "firestore-id-1"
    assert repository.list_for_owner("alice") == [alice_file]
    assert repository.list_for_owner("bob") == []
    assert repository.get_for_owner(alice_file.id, "alice") == alice_file
    assert repository.get_for_owner(alice_file.id, "bob") is None
    assert repository.delete_for_owner(alice_file.id, "bob") is False
    assert repository.get_for_owner(alice_file.id, "alice") == alice_file
    assert repository.delete_for_owner(alice_file.id, "alice") is True
    assert repository.get_for_owner(alice_file.id, "alice") is None
