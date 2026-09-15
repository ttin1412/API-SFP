"""Authentication API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.dependencies import CurrentUser, get_auth_service
from app.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.service import (
    AuthenticationError,
    AuthService,
    EmailAlreadyRegisteredError,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
Service = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: RegisterRequest, service: Service) -> UserResponse:
    """Create a user account."""
    try:
        user = service.register(payload.email, payload.password)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from exc
    return UserResponse.from_user(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, service: Service) -> TokenResponse:
    """Exchange valid credentials for a token pair."""
    try:
        return service.login(payload.email, payload.password)
    except AuthenticationError as exc:
        raise _invalid_credentials() from exc


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, service: Service) -> TokenResponse:
    """Rotate a valid refresh token and return a new token pair."""
    try:
        return service.refresh(payload.refresh_token)
    except AuthenticationError as exc:
        raise _invalid_credentials() from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, service: Service) -> Response:
    """Revoke a refresh token."""
    try:
        service.logout(payload.refresh_token)
    except AuthenticationError as exc:
        raise _invalid_credentials() from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def get_me(user: CurrentUser) -> UserResponse:
    """Return the user represented by the access token."""
    return UserResponse.from_user(user)


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
