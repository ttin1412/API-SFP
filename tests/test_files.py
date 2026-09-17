"""Integration tests for authenticated file metadata endpoints."""

from fastapi.testclient import TestClient

from app.auth.repository import InMemoryAuthRepository
from app.files.repository import InMemoryFileRepository
from app.main import create_app


class FakeObjectStorage:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str]] = []

    def generate_upload_url(self, *, storage_key: str, content_type: str) -> str:
        self.uploads.append((storage_key, content_type))
        return f"https://storage.example.test/{storage_key}?signed=true"


def make_client() -> TestClient:
    return TestClient(
        create_app(
            auth_repository=InMemoryAuthRepository(),
            file_repository=InMemoryFileRepository(),
            object_storage=FakeObjectStorage(),
        )
    )


def register_and_login(client: TestClient, email: str) -> str:
    password = "correct horse battery staple"
    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert register.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_file(client: TestClient, token: str, filename: str = "photo.jpg"):
    return client.post(
        "/api/v1/files/upload-url",
        headers=authorization(token),
        json={
            "filename": filename,
            "content_type": "image/jpeg",
            "size": 1024,
        },
    )


def test_file_routes_require_authentication_and_validate_metadata() -> None:
    client = make_client()
    token = register_and_login(client, "user@example.com")

    anonymous = client.get("/api/v1/files")
    unsupported = create_file(client, token, "payload.exe")
    oversized = client.post(
        "/api/v1/files/upload-url",
        headers=authorization(token),
        json={
            "filename": "photo.jpg",
            "content_type": "image/jpeg",
            "size": 52_428_801,
        },
    )
    traversal = create_file(client, token, "../photo.jpg")

    assert anonymous.status_code == 401
    assert unsupported.status_code == 422
    assert oversized.status_code == 422
    assert traversal.status_code == 422


def test_create_list_get_and_delete_file_metadata() -> None:
    client = make_client()
    token = register_and_login(client, "user@example.com")

    created = create_file(client, token)

    assert created.status_code == 201
    body = created.json()
    assert body["upload_url"].startswith("https://storage.example.test/quarantine/")
    assert body["file"]["status"] == "PENDING_UPLOAD"
    assert body["file"]["extension"] == ".jpg"
    assert body["file"]["storage_key"].startswith("quarantine/")
    assert body["file"]["storage_key"] in body["upload_url"]
    file_id = body["file"]["id"]

    listed = client.get("/api/v1/files", headers=authorization(token))
    fetched = client.get(f"/api/v1/files/{file_id}", headers=authorization(token))
    deleted = client.delete(f"/api/v1/files/{file_id}", headers=authorization(token))
    missing = client.get(f"/api/v1/files/{file_id}", headers=authorization(token))

    assert listed.status_code == 200
    assert [file["id"] for file in listed.json()] == [file_id]
    assert fetched.status_code == 200
    assert fetched.json()["id"] == file_id
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert missing.status_code == 404


def test_users_cannot_list_read_or_delete_another_users_file() -> None:
    client = make_client()
    alice_token = register_and_login(client, "alice@example.com")
    bob_token = register_and_login(client, "bob@example.com")
    created = create_file(client, alice_token)
    file_id = created.json()["file"]["id"]

    bob_list = client.get("/api/v1/files", headers=authorization(bob_token))
    bob_read = client.get(f"/api/v1/files/{file_id}", headers=authorization(bob_token))
    bob_delete = client.delete(
        f"/api/v1/files/{file_id}", headers=authorization(bob_token)
    )
    alice_read = client.get(
        f"/api/v1/files/{file_id}", headers=authorization(alice_token)
    )

    assert bob_list.status_code == 200
    assert bob_list.json() == []
    assert bob_read.status_code == 404
    assert bob_delete.status_code == 404
    assert alice_read.status_code == 200
