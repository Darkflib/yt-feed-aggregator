"""FastAPI router for Google OAuth authentication."""

import base64
import time
from typing import Annotated

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import encrypt_refresh_token
from app.config import get_settings
from app.db import crud
from app.db.models import User
from app.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])

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
async def login(request: Request):
    """
    Initiate OAuth login flow with Google.

    Redirects to Google OAuth with PKCE enabled and required scopes.
    """
    oauth = _get_oauth()
    settings = get_settings()
    redirect_uri = str(settings.google_redirect_uri)
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
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

    try:
        # Exchange authorization code for tokens
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")

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
        # Decode the token_enc_key from base64 if needed, or use as bytes
        enc_key = settings.token_enc_key
        # Ensure key is bytes and 32 bytes long
        if isinstance(enc_key, str):
            # Try base64 decode first
            try:
                enc_key_bytes = base64.b64decode(enc_key)
            except Exception:
                # If not base64, encode as UTF-8 and pad/truncate to 32 bytes
                enc_key_bytes = enc_key.encode("utf-8")
                if len(enc_key_bytes) < 32:
                    enc_key_bytes = enc_key_bytes.ljust(32, b"\x00")
                elif len(enc_key_bytes) > 32:
                    enc_key_bytes = enc_key_bytes[:32]
        else:
            enc_key_bytes = enc_key

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
async def logout(response: Response):
    """
    Clear the session cookie to log out the user.
    """
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
