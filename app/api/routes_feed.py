"""Feed aggregation endpoints for the YouTube Feed Aggregator API."""

import base64
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from redis.asyncio import Redis
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_redis
from app.auth.router import require_user
from app.config import get_settings
from app.db import crud
from app.db.models import User
from app.db.session import get_session
from app.feed.aggregator import aggregate_feeds
from app.rss.cache import fetch_and_cache_feed

# YouTube channel IDs start with UC and are 24 characters (alphanumeric, -, _)
CHANNEL_ID_PATTERN = re.compile(r"^UC[\w-]{22}$")

router = APIRouter(prefix="/api/feed", tags=["feed"])
limiter = Limiter(key_func=get_remote_address)


@router.get("")
@limiter.limit("120/minute")
async def get_feed(
    request: Request,
    limit: int = Query(default=24, ge=1, le=60, description="Items per page (1-60)"),
    cursor: str | None = Query(default=None, description="Pagination cursor"),
    channel_id: str | None = Query(
        default=None, description="Filter to single channel"
    ),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    """
    Main feed endpoint with pagination and filtering.

    This endpoint:
    1. Fetches feeds from Redis cache (or YouTube if cache miss)
    2. Aggregates all feeds
    3. Filters out shorts (unless configured otherwise)
    4. Paginates results using cursor-based pagination

    Query Parameters:
        - limit: Items per page (default 24, max 60)
        - cursor: Pagination cursor from previous request
        - channel_id: Optional filter to single channel

    Returns:
        JSON response with:
            - items: List of feed items
            - next_cursor: Cursor for next page (null if no more items)
    """
    settings = get_settings()

    # Validate cursor format if provided
    if cursor:
        try:
            # Cursor should be valid base64
            decoded = base64.b64decode(cursor, validate=True)
            # Basic sanity check - should contain timestamp and video_id separated by |
            if b"|" not in decoded:
                raise ValueError("Invalid cursor format")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor format")

    # Validate channel_id format if provided (prevents Redis injection)
    if channel_id:
        if not CHANNEL_ID_PATTERN.match(channel_id):
            raise HTTPException(
                status_code=400,
                detail="Invalid channel_id format. Must be a valid YouTube channel ID (UC...)",
            )

    # Determine which channels to fetch
    if channel_id:
        channels = [channel_id]
    else:
        user_channels = await crud.list_user_channels(db, user.id)
        channels = [ch.channel_id for ch in user_channels]

    # Fetch feeds from cache/RSS
    feeds = []
    for cid in channels:
        try:
            feed = await fetch_and_cache_feed(redis, cid)
            feeds.append(feed)
        except Exception:
            # Skip channels that fail to fetch
            # In production, you might want to log this
            continue

    # Get watched video IDs for the current user
    watched_video_ids = await crud.get_watched_video_ids(db, user.id)

    # Aggregate and paginate
    result = aggregate_feeds(
        feeds, include_shorts=settings.include_shorts, limit=limit, cursor=cursor
    )

    # Serialize items using model_dump(mode='json') for proper datetime handling
    # Add watched status to each item
    items_with_watched = []
    for item in result["items"]:
        item_dict = item.model_dump(mode="json")
        item_dict["watched"] = item.video_id in watched_video_ids
        items_with_watched.append(item_dict)

    return {
        "items": items_with_watched,
        "next_cursor": result["next_cursor"],
    }
