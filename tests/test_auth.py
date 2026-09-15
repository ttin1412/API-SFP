"""Integration tests for authentication and bearer authorization."""

from fastapi.testclient import TestClient

from app.auth.repository import InMemoryAuthRepository
from app.main import create_app


def make_client() -> tuple[TestClient, InMemoryAuthRepository]:
    repository = InMemoryAuthRepository()
    return TestClient(create_app(repository)), repository


def register(client: TestClient, email: str = "user@example.com") -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct horse battery staple"},
    )
    assert response.status_code == 201


def login(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "user@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_register_normalizes_email_and_hashes_password() -> None:
    client, repository = make_client()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "  User@Example.COM ",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "user@example.com"
    assert response.json()["role"] == "user"
    user = repository.get_user_by_email("user@example.com")
    assert user is not None
    assert user.password_hash != "correct horse battery staple"


def test_register_rejects_invalid_input_and_duplicate_email() -> None:
    client, _ = make_client()

    invalid = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "short"},
    )
    register(client)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "email": "USER@example.com",
            "password": "another secure password",
        },
    )

    assert invalid.status_code == 422
    assert duplicate.status_code == 409


def test_login_returns_tokens_and_rejects_bad_credentials() -> None:
    client, _ = make_client()
    register(client)

    tokens = login(client)
    invalid = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "wrong password"},
    )

    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 900
    assert isinstance(tokens["access_token"], str)
    assert isinstance(tokens["refresh_token"], str)
    assert invalid.status_code == 401


def test_access_token_authorizes_me_but_refresh_token_does_not() -> None:
    client, _ = make_client()
    register(client)
    tokens = login(client)

    anonymous = client.get("/api/v1/auth/me")
    authorized = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    wrong_token_type = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )

    assert anonymous.status_code == 401
    assert anonymous.headers["www-authenticate"] == "Bearer"
    assert authorized.status_code == 200
    assert authorized.json()["email"] == "user@example.com"
    assert wrong_token_type.status_code == 401


def test_refresh_rotates_token_and_rejects_replay() -> None:
    client, _ = make_client()
    register(client)
    original = login(client)

    refreshed = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original["refresh_token"]},
    )
    replay = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original["refresh_token"]},
    )

    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != original["refresh_token"]
    assert replay.status_code == 401


def test_logout_revokes_refresh_token() -> None:
    client, _ = make_client()
    register(client)
    tokens = login(client)

    logout = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )
    refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert logout.status_code == 204
    assert logout.content == b""
    assert refresh.status_code == 401
