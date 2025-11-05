"""RSS feed fetching and caching with Redis."""

import json
import random
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx
from redis.asyncio import Redis

from app.config import get_settings

from .models import FeedItem

# XML namespaces for YouTube RSS feeds
NAMESPACES = {
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "atom": "http://www.w3.org/2005/Atom",
}


def _key(channel_id: str) -> str:
    """Generate Redis key for a channel's feed cache."""
    return f"yt:feed:{channel_id}"


async def fetch_and_cache_feed(redis: Redis, channel_id: str) -> list[FeedItem]:
    """
    Fetch and cache a YouTube channel's RSS feed.

    First checks Redis cache. If cache hit, returns cached data.
    On cache miss, fetches from YouTube RSS endpoint, parses XML,
    and caches the result with TTL + randomized splay.

    Args:
        redis: Async Redis client
        channel_id: YouTube channel ID

    Returns:
        List of FeedItem objects representing recent videos

    Raises:
        httpx.HTTPError: If the HTTP request fails
        xml.etree.ElementTree.ParseError: If XML parsing fails
    """
    settings = get_settings()
    base_ttl = settings.feed_ttl_seconds
    splay = settings.feed_ttl_splay_max
    ttl = base_ttl + random.randint(0, splay)

    key = _key(channel_id)

    # Check cache first
    if cached_data := await redis.get(key):
        items_data = json.loads(cached_data)
        return [FeedItem(**item) for item in items_data]

    # Cache miss - fetch from YouTube
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url)
        response.raise_for_status()
        response_text = response.text

    # Parse XML
    try:
        xml_root = ET.fromstring(response_text)
    except ET.ParseError:
        # Invalid XML - return empty list
        return []

    # Extract feed items
    items = []
    for entry in xml_root.findall("atom:entry", NAMESPACES):
        try:
            video_id_elem = entry.find("yt:videoId", NAMESPACES)
            link_elem = entry.find("atom:link", NAMESPACES)
            title_elem = entry.find("atom:title", NAMESPACES)
            published_elem = entry.find("atom:published", NAMESPACES)

            # Skip entries with missing required fields
            if (
                video_id_elem is None
                or link_elem is None
                or title_elem is None
                or published_elem is None
            ):
                continue

            video_id = video_id_elem.text
            link = link_elem.attrib.get("href")
            title = title_elem.text
            published_str = published_elem.text

            # Skip if any required text content is missing
            if not video_id or not link or not title or not published_str:
                continue

            # Parse ISO 8601 datetime (convert Z to +00:00 for proper parsing)
            published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))

            items.append(
                FeedItem(
                    video_id=video_id,
                    channel_id=channel_id,
                    title=title,
                    link=link,  # type: ignore[arg-type]  # Pydantic handles str -> HttpUrl
                    published=published,
                )
            )
        except (AttributeError, KeyError, ValueError):
            # Skip malformed entries
            continue

    # Cache the results using mode='json' to handle datetime serialization
    serialized_items = [item.model_dump(mode="json") for item in items]
    await redis.setex(key, ttl, json.dumps(serialized_items))

    return items
