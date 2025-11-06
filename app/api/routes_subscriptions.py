"""Subscription management endpoints for the YouTube Feed Aggregator API."""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.crypto import validate_encryption_key
from app.auth.router import require_user
from app.auth.security import decrypt_refresh_token
from app.config import get_settings
from app.db import crud
from app.db.models import User
from app.db.session import get_session
from app.youtube.client import YouTubeClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])
limiter = Limiter(key_func=get_remote_address)


async def _get_access_token_from_refresh(refresh_token: str) -> str:
    """Exchange a refresh token for a new access token.

    Args:
        refresh_token: The refresh token

    Returns:
        A fresh access token

    Raises:
        HTTPException: If token refresh fails
    """
    settings = get_settings()

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=401, detail="Failed to refresh access token"
            )

        data = response.json()
        return data["access_token"]


@router.post("/refresh")
@limiter.limit("5/hour")
async def refresh_subscriptions(
    request: Request,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """
    Pull subscriptions from YouTube API and upsert UserChannel records.

    This endpoint:
    1. Decrypts the user's stored refresh token
    2. Exchanges it for a fresh access token
    3. Fetches all YouTube subscriptions via the YouTube Data API
    4. Upserts channel records in the database

    Returns:
        A response with count of channels synced and list of channels
    """
    settings = get_settings()

    # Check if user has a refresh token
    if not user.refresh_token_enc:
        raise HTTPException(
            status_code=400,
            detail="No refresh token available. Please re-authenticate.",
        )

    # Decrypt the refresh token
    try:
        enc_key_bytes = validate_encryption_key(settings.token_enc_key)
    except ValueError:
        logger.error("Invalid encryption key configuration", exc_info=True)
        raise HTTPException(status_code=500, detail="Service configuration error")

    try:
        refresh_token = decrypt_refresh_token(enc_key_bytes, user.refresh_token_enc)
    except Exception:
        logger.error("Failed to decrypt refresh token", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An error occurred processing your request"
        )

    # Get a fresh access token
    try:
        access_token = await _get_access_token_from_refresh(refresh_token)
    except HTTPException:
        raise
    except Exception:
        logger.error("Failed to get access token", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An error occurred processing your request"
        )

    # Fetch subscriptions from YouTube
    youtube = YouTubeClient(access_token)
    try:
        subscriptions = await youtube.list_subscriptions()
    except PermissionError:
        raise HTTPException(status_code=401, detail="YouTube access token expired")
    except Exception:
        logger.error("Failed to fetch subscriptions from YouTube", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An error occurred fetching subscriptions"
        )

    # Upsert channels in the database
    channels = []
    for sub in subscriptions:
        channel = await crud.upsert_user_channel(
            db=db,
            user_id=user.id,
            channel_id=sub["channel_id"],
            channel_title=sub["title"],
        )
        channels.append(
            {
                "id": channel.id,
                "channel_id": channel.channel_id,
                "channel_title": channel.channel_title,
                "active": channel.active,
            }
        )

    return {"count": len(channels), "channels": channels}


@router.get("")
@limiter.limit("60/minute")
async def list_subscriptions(
    request: Request,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """
    List user's subscribed channels for filtering.

    Returns:
        A list of channels the user is subscribed to
    """
    channels = await crud.list_user_channels(db, user.id)

    return {
        "channels": [
            {
                "id": ch.id,
                "channel_id": ch.channel_id,
                "channel_title": ch.channel_title,
                "channel_custom_url": ch.channel_custom_url,
                "active": ch.active,
                "added_at": ch.added_at.isoformat(),
            }
            for ch in channels
        ]
    }
