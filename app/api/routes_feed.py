"""Feed aggregation endpoints for the YouTube Feed Aggregator API."""

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_redis
from app.auth.router import require_user
from app.config import get_settings
from app.db import crud
from app.db.models import User
from app.db.session import get_session
from app.feed.aggregator import aggregate_feeds
from app.rss.cache import fetch_and_cache_feed

router = APIRouter(prefix="/api/feed", tags=["feed"])


@router.get("")
async def get_feed(
    limit: int = Query(default=24, le=60, description="Items per page (max 60)"),
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

    # Aggregate and paginate
    result = aggregate_feeds(
        feeds, include_shorts=settings.include_shorts, limit=limit, cursor=cursor
    )

    # Serialize items using model_dump(mode='json') for proper datetime handling
    return {
        "items": [item.model_dump(mode="json") for item in result["items"]],
        "next_cursor": result["next_cursor"],
    }
