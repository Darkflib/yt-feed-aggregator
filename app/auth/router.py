"""FastAPI router for Google OAuth authentication."""

import logging
import time
from typing import Annotated

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.crypto import validate_encryption_key
from app.auth.security import encrypt_refresh_token
from app.config import get_settings
from app.db import crud
from app.db.models import User
from app.db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

SESSION_COOKIE = "yt_simple_sess"


def _get_oauth() -> OAuth:
    """Create and configure OAuth client for Google."""
    settings = get_settings()
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile https://www.googleapis.com/auth/youtube.readonly"
        },
    )
    return oauth


def _create_session_token(user_id: str) -> str:
    """Create a signed JWT session token containing the user ID."""
    settings = get_settings()
    payload = {
        "sub": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400 * 7,  # 7 days
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm="HS256")


def _verify_session_token(token: str) -> str | None:
    """Verify a session token and return the user ID, or None if invalid."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=["HS256"])
        return payload.get("sub")
    except JWTError:
        return None


async def require_user(
    session_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    db: AsyncSession = Depends(get_session),
) -> User:
    """
    FastAPI dependency that requires a valid authenticated user.

    Args:
        session_cookie: The session cookie value
        db: Database session

    Returns:
        The authenticated User object

    Raises:
        HTTPException: 401 if session is missing or invalid
    """
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = _verify_session_token(session_cookie)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session")

    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


@router.get("/login")
@limiter.limit("10/minute")
async def login(request: Request):
    """
    Initiate OAuth login flow with Google.

    Redirects to Google OAuth with PKCE enabled and required scopes.

    Rate limit: 10 requests per minute per IP to prevent abuse.
    """
    ip_address = request.client.host if request.client else "unknown"
    logger.info(f"Login attempt initiated from IP: {ip_address}")

    oauth = _get_oauth()
    settings = get_settings()
    redirect_uri = str(settings.google_redirect_uri)
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
@limiter.limit("10/minute")
async def callback(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
):
    """
    Handle OAuth callback from Google.

    Exchanges authorization code for tokens, creates or updates user,
    and issues a session cookie.
    """
    oauth = _get_oauth()
    settings = get_settings()
    ip_address = request.client.host if request.client else "unknown"

    try:
        # Exchange authorization code for tokens
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        logger.error(f"OAuth authorization failed from IP: {ip_address}", exc_info=True)
        raise HTTPException(status_code=400, detail="Authentication failed")

    # Extract user information from ID token
    userinfo = token.get("userinfo")
    if not userinfo:
        raise HTTPException(status_code=400, detail="Failed to get user info")

    google_sub = userinfo.get("sub")
    email = userinfo.get("email")
    name = userinfo.get("name", email)
    picture = userinfo.get("picture")

    if not google_sub or not email:
        raise HTTPException(status_code=400, detail="Missing required user information")

    # Encrypt refresh token if present
    refresh_token = token.get("refresh_token")
    refresh_token_enc = None
    if refresh_token:
        # Validate and convert encryption key (must be 32 bytes, base64-encoded)
        try:
            enc_key_bytes = validate_encryption_key(settings.token_enc_key)
        except ValueError:
            logger.error("Invalid encryption key configuration", exc_info=True)
            raise HTTPException(
                status_code=500, detail="Service configuration error"
            )

        refresh_token_enc = encrypt_refresh_token(enc_key_bytes, refresh_token)

    # Create or update user
    user = await crud.create_or_update_user(
        db=db,
        google_sub=google_sub,
        email=email,
        display_name=name,
        avatar_url=picture,
        refresh_token_enc=refresh_token_enc,
    )

    # Create session token
    session_token = _create_session_token(user.id)

    # Log successful authentication
    logger.info(
        f"User authenticated successfully: user_id={user.id}, email={user.email}, ip={ip_address}"
    )

    # Determine if we're in production
    is_prod = settings.env == "prod"

    # Set session cookie
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        max_age=86400 * 7,  # 7 days
    )

    # Redirect to frontend
    response.status_code = 302
    response.headers["Location"] = "/"
    return response


@router.post("/logout")
@limiter.limit("20/minute")
async def logout(
    request: Request,
    response: Response,
    session_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
):
    """
    Clear the session cookie to log out the user.

    Does not require authentication to allow logout even with invalid tokens.

    Rate limit: 20 requests per minute per IP.
    """
    ip_address = request.client.host if request.client else "unknown"

    # Try to extract user info from token for logging, but don't fail if invalid
    if session_cookie:
        try:
            settings = get_settings()
            payload = jwt.decode(session_cookie, settings.app_secret_key, algorithms=["HS256"])
            user_id = payload.get("sub")
            logger.info(f"User logged out: user_id={user_id}, ip={ip_address}")
        except JWTError:
            logger.info(f"Logout attempt with invalid token from ip={ip_address}")
    else:
        logger.info(f"Logout attempt without token from ip={ip_address}")

    response.delete_cookie(key=SESSION_COOKIE, httponly=True, samesite="lax")
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_current_user(user: User = Depends(require_user)):
    """
    Get current authenticated user information.

    Returns basic user profile without sensitive data.
    """
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at.isoformat(),
    }
