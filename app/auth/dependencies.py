"""FastAPI authentication and role-authorization dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import User, UserRole
from app.auth.service import AuthenticationError, AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service(request: Request) -> AuthService:
    """Return the application-scoped authentication service."""
    return request.app.state.auth_service


def get_current_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)  # noqa: UP045
    ],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    """Authenticate an active user from an Authorization bearer token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        return service.authenticate_access_token(credentials.credentials)
    except AuthenticationError as exc:
        raise _unauthorized() from exc


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed_roles: UserRole) -> Callable[[CurrentUser], User]:
    """Build a dependency that permits only the supplied roles."""

    def authorize(user: CurrentUser) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return authorize


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
