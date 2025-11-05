"""Tests for RSS feed caching functionality."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from redis.asyncio import Redis

from app.rss.cache import fetch_and_cache_feed
from app.rss.models import FeedItem


# Sample YouTube RSS feed XML
SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <title>Channel Title</title>
  <entry>
    <yt:videoId>dQw4w9WgXcQ</yt:videoId>
    <yt:channelId>UCuAXFkgsw1L7xaCfnd5JJOw</yt:channelId>
    <title xmlns="http://www.w3.org/2005/Atom">Test Video 1</title>
    <link xmlns="http://www.w3.org/2005/Atom" rel="alternate" href="https://www.youtube.com/watch?v=dQw4w9WgXcQ"/>
    <published xmlns="http://www.w3.org/2005/Atom">2024-01-15T10:30:00+00:00</published>
  </entry>
  <entry>
    <yt:videoId>jNQXAC9IVRw</yt:videoId>
    <yt:channelId>UCuAXFkgsw1L7xaCfnd5JJOw</yt:channelId>
    <title xmlns="http://www.w3.org/2005/Atom">Test Video 2</title>
    <link xmlns="http://www.w3.org/2005/Atom" rel="alternate" href="https://www.youtube.com/watch?v=jNQXAC9IVRw"/>
    <published xmlns="http://www.w3.org/2005/Atom">2024-01-14T15:45:00+00:00</published>
  </entry>
</feed>
"""

# Invalid XML for error handling tests
INVALID_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <title>Channel Title</title>
  <entry>
    <yt:videoId>incomplete
"""


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    return redis


@pytest.fixture
def mock_settings():
    """Mock settings with test values."""
    with patch("app.rss.cache.get_settings") as mock_get_settings:
        settings = MagicMock()
        settings.feed_ttl_seconds = 1800
        settings.feed_ttl_splay_max = 300
        mock_get_settings.return_value = settings
        yield settings


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_data_without_http_call(mock_redis, mock_settings):
    """Test that cache hit returns cached data without making HTTP request."""
    channel_id = "UCuAXFkgsw1L7xaCfnd5JJOw"

    # Prepare cached data
    cached_items = [
        {
            "video_id": "cached_video_1",
            "channel_id": channel_id,
            "title": "Cached Video 1",
            "link": "https://www.youtube.com/watch?v=cached_video_1",
            "published": "2024-01-15T10:30:00+00:00",
        },
        {
            "video_id": "cached_video_2",
            "channel_id": channel_id,
            "title": "Cached Video 2",
            "link": "https://www.youtube.com/watch?v=cached_video_2",
            "published": "2024-01-14T15:45:00+00:00",
        },
    ]
    mock_redis.get.return_value = json.dumps(cached_items)

    # Mock httpx to ensure no HTTP call is made
    with patch("httpx.AsyncClient") as mock_client:
        result = await fetch_and_cache_feed(mock_redis, channel_id)

        # Verify no HTTP call was made
        mock_client.assert_not_called()

        # Verify cache was checked
        mock_redis.get.assert_called_once_with(f"yt:feed:{channel_id}")

        # Verify results
        assert len(result) == 2
        assert result[0].video_id == "cached_video_1"
        assert result[0].title == "Cached Video 1"
        assert result[1].video_id == "cached_video_2"
        assert result[1].title == "Cached Video 2"


@pytest.mark.asyncio
async def test_cache_miss_fetches_from_http_and_caches(mock_redis, mock_settings):
    """Test that cache miss fetches from HTTP and caches the result."""
    channel_id = "UCuAXFkgsw1L7xaCfnd5JJOw"

    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.text = SAMPLE_RSS_XML
    mock_response.raise_for_status = MagicMock()

    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        result = await fetch_and_cache_feed(mock_redis, channel_id)

        # Verify cache was checked
        mock_redis.get.assert_called_once_with(f"yt:feed:{channel_id}")

        # Verify HTTP request was made
        mock_client_instance.get.assert_called_once_with(
            f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        )

        # Verify data was cached
        assert mock_redis.setex.called
        call_args = mock_redis.setex.call_args
        cache_key = call_args[0][0]
        cache_ttl = call_args[0][1]
        cache_data = call_args[0][2]

        assert cache_key == f"yt:feed:{channel_id}"
        # TTL should be base_ttl + random splay
        assert 1800 <= cache_ttl <= 2100

        # Verify cached data structure
        cached_items = json.loads(cache_data)
        assert len(cached_items) == 2

        # Verify results
        assert len(result) == 2
        assert result[0].video_id == "dQw4w9WgXcQ"
        assert result[0].channel_id == channel_id
        assert result[0].title == "Test Video 1"
        assert str(result[0].link) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert result[1].video_id == "jNQXAC9IVRw"
        assert result[1].title == "Test Video 2"


@pytest.mark.asyncio
async def test_ttl_randomization_in_expected_range(mock_redis, mock_settings):
    """Test that TTL is randomized within the expected range."""
    channel_id = "UCuAXFkgsw1L7xaCfnd5JJOw"

    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.text = SAMPLE_RSS_XML
    mock_response.raise_for_status = MagicMock()

    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        # Call multiple times to verify randomization
        ttls = []
        for _ in range(10):
            mock_redis.setex.reset_mock()
            await fetch_and_cache_feed(mock_redis, channel_id)

            if mock_redis.setex.called:
                ttl = mock_redis.setex.call_args[0][1]
                ttls.append(ttl)

        # Verify all TTLs are in the expected range
        base_ttl = mock_settings.feed_ttl_seconds
        splay_max = mock_settings.feed_ttl_splay_max

        for ttl in ttls:
            assert base_ttl <= ttl <= base_ttl + splay_max

        # Verify there's some variation (not all the same)
        # This could theoretically fail due to random chance, but very unlikely
        assert len(set(ttls)) > 1


@pytest.mark.asyncio
async def test_invalid_xml_returns_empty_list(mock_redis, mock_settings):
    """Test that invalid XML is handled gracefully and returns empty list."""
    channel_id = "UCuAXFkgsw1L7xaCfnd5JJOw"

    # Mock HTTP response with invalid XML
    mock_response = MagicMock()
    mock_response.text = INVALID_XML
    mock_response.raise_for_status = MagicMock()

    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        result = await fetch_and_cache_feed(mock_redis, channel_id)

        # Should return empty list instead of raising exception
        assert result == []

        # Should not cache invalid data
        mock_redis.setex.assert_not_called()


@pytest.mark.asyncio
async def test_http_error_raises_exception(mock_redis, mock_settings):
    """Test that HTTP errors are properly raised."""
    channel_id = "UCuAXFkgsw1L7xaCfnd5JJOw"

    # Create a proper mock for HTTPStatusError
    mock_request = MagicMock()
    mock_error_response = MagicMock()
    mock_error_response.status_code = 404

    http_error = httpx.HTTPStatusError(
        "404 Not Found", request=mock_request, response=mock_error_response
    )

    # Mock the get method to raise the exception
    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(side_effect=http_error)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)  # Don't suppress exception

    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_and_cache_feed(mock_redis, channel_id)


@pytest.mark.asyncio
async def test_malformed_entries_are_skipped(mock_redis, mock_settings):
    """Test that malformed feed entries are skipped gracefully."""
    channel_id = "UCuAXFkgsw1L7xaCfnd5JJOw"

    # XML with one valid entry and one missing required fields
    malformed_xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <title>Channel Title</title>
  <entry>
    <yt:videoId>valid_video</yt:videoId>
    <title xmlns="http://www.w3.org/2005/Atom">Valid Video</title>
    <link xmlns="http://www.w3.org/2005/Atom" rel="alternate" href="https://www.youtube.com/watch?v=valid_video"/>
    <published xmlns="http://www.w3.org/2005/Atom">2024-01-15T10:30:00+00:00</published>
  </entry>
  <entry>
    <yt:videoId>missing_link</yt:videoId>
    <title xmlns="http://www.w3.org/2005/Atom">Missing Link</title>
    <published xmlns="http://www.w3.org/2005/Atom">2024-01-14T15:45:00+00:00</published>
  </entry>
  <entry>
    <title xmlns="http://www.w3.org/2005/Atom">Missing Video ID</title>
    <link xmlns="http://www.w3.org/2005/Atom" rel="alternate" href="https://www.youtube.com/watch?v=missing_id"/>
    <published xmlns="http://www.w3.org/2005/Atom">2024-01-13T12:00:00+00:00</published>
  </entry>
</feed>
"""

    mock_response = MagicMock()
    mock_response.text = malformed_xml
    mock_response.raise_for_status = MagicMock()

    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        result = await fetch_and_cache_feed(mock_redis, channel_id)

        # Should return only the valid entry
        assert len(result) == 1
        assert result[0].video_id == "valid_video"
        assert result[0].title == "Valid Video"


@pytest.mark.asyncio
async def test_datetime_parsing_with_z_suffix(mock_redis, mock_settings):
    """Test that datetime strings with Z suffix are parsed correctly."""
    channel_id = "UCuAXFkgsw1L7xaCfnd5JJOw"

    # XML with Z suffix in published date
    xml_with_z = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>test_video</yt:videoId>
    <title xmlns="http://www.w3.org/2005/Atom">Test Video</title>
    <link xmlns="http://www.w3.org/2005/Atom" rel="alternate" href="https://www.youtube.com/watch?v=test_video"/>
    <published xmlns="http://www.w3.org/2005/Atom">2024-01-15T10:30:00Z</published>
  </entry>
</feed>
"""

    mock_response = MagicMock()
    mock_response.text = xml_with_z
    mock_response.raise_for_status = MagicMock()

    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        result = await fetch_and_cache_feed(mock_redis, channel_id)

        # Should parse successfully
        assert len(result) == 1
        assert result[0].video_id == "test_video"
        assert isinstance(result[0].published, datetime)
        # Verify it's UTC timezone aware
        assert result[0].published.tzinfo is not None
