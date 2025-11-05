"""Feed aggregator for merging and paginating YouTube RSS feed items."""

import base64
import json
from typing import Sequence

from app.rss.models import FeedItem


def is_short(item: FeedItem) -> bool:
    """Check if a feed item is a YouTube Short.

    Args:
        item: The feed item to check

    Returns:
        True if the item's URL contains "/shorts/", False otherwise
    """
    url = str(item.link)
    return "/shorts/" in url.lower()


def make_cursor(item: FeedItem) -> str:
    """Create a base64-encoded cursor from a feed item.

    The cursor encodes the item's timestamp and video_id for pagination.

    Args:
        item: The feed item to create a cursor from

    Returns:
        A base64-encoded cursor string
    """
    blob = json.dumps({"t": int(item.published.timestamp()), "v": item.video_id})
    return base64.urlsafe_b64encode(blob.encode()).decode()


def decode_cursor(cursor: str) -> tuple[int, str]:
    """Decode a cursor string back to timestamp and video_id.

    Args:
        cursor: The base64-encoded cursor string

    Returns:
        A tuple of (timestamp, video_id)
    """
    d = json.loads(base64.urlsafe_b64decode(cursor))
    return d["t"], d["v"]


def aggregate_feeds(
    feeds: Sequence[Sequence[FeedItem]],
    include_shorts: bool = False,
    limit: int = 24,
    cursor: str | None = None,
) -> dict:
    """Aggregate multiple RSS feeds into a paginated result.

    This function:
    1. Flattens all feeds into a single list
    2. Filters out Shorts unless include_shorts=True
    3. Sorts by published date descending
    4. Applies cursor pagination (items with (timestamp, video_id) < cursor value)
    5. Returns a page of items and a cursor for the next page

    Args:
        feeds: A sequence of feed item sequences to aggregate
        include_shorts: Whether to include YouTube Shorts (default: False)
        limit: Maximum number of items per page (default: 24)
        cursor: Pagination cursor from a previous request (default: None)

    Returns:
        A dict with:
            - "items": List of FeedItem objects for the current page
            - "next_cursor": Cursor string for the next page, or None if no more items
    """
    # Flatten all feeds into a single list
    items = [i for f in feeds for i in f]

    # Filter out shorts unless explicitly included
    if not include_shorts:
        items = [i for i in items if not is_short(i)]

    # Sort by published date descending, then by video_id descending for deterministic ordering
    items.sort(key=lambda i: (i.published, i.video_id), reverse=True)

    # Apply cursor filtering if provided
    if cursor:
        t, v = decode_cursor(cursor)
        items = [i for i in items if (i.published.timestamp(), i.video_id) < (t, v)]

    # Extract the page
    page = items[:limit]

    # Generate next cursor if there are more items
    next_cursor = make_cursor(page[-1]) if len(items) > limit else None

    return {"items": page, "next_cursor": next_cursor}
