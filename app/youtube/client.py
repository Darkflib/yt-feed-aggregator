"""YouTube Data API v3 client for fetching user subscriptions."""

import asyncio
import random
from typing import Any

import httpx


class YouTubeClient:
    """Client for interacting with YouTube Data API v3.

    Handles pagination, deduplication, and error handling for subscription retrieval.
    """

    BASE = "https://www.googleapis.com/youtube/v3"

    def __init__(self, access_token: str):
        """Initialize the YouTube client with an OAuth access token.

        Args:
            access_token: Valid OAuth 2.0 access token with YouTube scopes
        """
        self._headers = {"Authorization": f"Bearer {access_token}"}

    async def list_subscriptions(self) -> list[dict[str, Any]]:
        """Fetch all YouTube channel subscriptions for the authenticated user.

        This method paginates through all subscription pages, extracts channel
        information, and returns a deduplicated list.

        Returns:
            List of subscription dicts with keys:
                - channel_id (str): YouTube channel ID
                - title (str): Channel title

        Raises:
            PermissionError: If the access token is expired (401 response)
            httpx.HTTPStatusError: For other HTTP errors
        """
        items: list[dict[str, Any]] = []
        token: str | None = None

        async with httpx.AsyncClient(timeout=15) as client:
            while True:
                # Build request parameters
                params = {"part": "snippet", "mine": "true", "maxResults": 50}
                if token:
                    params["pageToken"] = token

                # Make API request
                r = await client.get(
                    f"{self.BASE}/subscriptions", headers=self._headers, params=params
                )

                # Handle expired token
                if r.status_code == 401:
                    raise PermissionError("Access token expired")

                # Raise for other HTTP errors
                r.raise_for_status()

                # Parse response
                data = r.json()

                # Extract channel information
                for it in data.get("items", []):
                    snippet = it.get("snippet", {})
                    rid = snippet.get("resourceId", {})

                    # Only include channel subscriptions
                    if rid.get("kind") == "youtube#channel":
                        items.append(
                            {
                                "channel_id": rid["channelId"],
                                "title": snippet.get("title"),
                            }
                        )

                # Check for next page
                token = data.get("nextPageToken")
                if not token:
                    break

                # Add delay with jitter between pagination requests
                await asyncio.sleep(0.1 + random.random() * 0.2)

        # Deduplicate results
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for it in items:
            channel_id = it["channel_id"]
            if channel_id in seen:
                continue
            seen.add(channel_id)
            unique.append(it)

        return unique
