"""Tests for YouTube client module."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.youtube.client import YouTubeClient


@pytest.fixture
def youtube_client():
    """Create a YouTubeClient instance with test token."""
    return YouTubeClient(access_token="test-access-token")


def create_mock_response(status_code: int, json_data: dict):
    """Helper to create a mock httpx Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json = MagicMock(return_value=json_data)
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


@pytest.mark.asyncio
async def test_list_subscriptions_single_page(youtube_client):
    """Test fetching subscriptions with a single page response."""
    # Mock response data
    mock_response_data = {
        "items": [
            {
                "snippet": {
                    "title": "Channel One",
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": "channel-id-1",
                    },
                }
            },
            {
                "snippet": {
                    "title": "Channel Two",
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": "channel-id-2",
                    },
                }
            },
        ]
        # No nextPageToken means single page
    }

    mock_response = create_mock_response(200, mock_response_data)

    # Patch httpx.AsyncClient
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        # Call the method
        result = await youtube_client.list_subscriptions()

        # Verify results
        assert len(result) == 2
        assert result[0]["channel_id"] == "channel-id-1"
        assert result[0]["title"] == "Channel One"
        assert result[1]["channel_id"] == "channel-id-2"
        assert result[1]["title"] == "Channel Two"

        # Verify API was called correctly
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "https://www.googleapis.com/youtube/v3/subscriptions"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-access-token"
        assert call_args[1]["params"]["part"] == "snippet"
        assert call_args[1]["params"]["mine"] == "true"
        assert call_args[1]["params"]["maxResults"] == 50


@pytest.mark.asyncio
async def test_list_subscriptions_multi_page(youtube_client):
    """Test fetching subscriptions with pagination."""
    # Mock response data for page 1
    mock_response_page1 = {
        "items": [
            {
                "snippet": {
                    "title": "Channel One",
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": "channel-id-1",
                    },
                }
            },
            {
                "snippet": {
                    "title": "Channel Two",
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": "channel-id-2",
                    },
                }
            },
        ],
        "nextPageToken": "page-2-token",
    }

    # Mock response data for page 2
    mock_response_page2 = {
        "items": [
            {
                "snippet": {
                    "title": "Channel Three",
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": "channel-id-3",
                    },
                }
            }
        ]
        # No nextPageToken means last page
    }

    mock_resp1 = create_mock_response(200, mock_response_page1)
    mock_resp2 = create_mock_response(200, mock_response_page2)

    # Patch httpx.AsyncClient and asyncio.sleep
    with (
        patch("httpx.AsyncClient") as mock_client_class,
        patch("app.youtube.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[mock_resp1, mock_resp2])
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        # Call the method
        result = await youtube_client.list_subscriptions()

        # Verify results
        assert len(result) == 3
        assert result[0]["channel_id"] == "channel-id-1"
        assert result[1]["channel_id"] == "channel-id-2"
        assert result[2]["channel_id"] == "channel-id-3"

        # Verify pagination - should be called twice
        assert mock_client.get.call_count == 2

        # Verify second call includes pageToken
        second_call_args = mock_client.get.call_args_list[1]
        assert second_call_args[1]["params"]["pageToken"] == "page-2-token"

        # Verify sleep was called between requests
        mock_sleep.assert_called_once()
        sleep_duration = mock_sleep.call_args[0][0]
        assert 0.1 <= sleep_duration <= 0.3  # 0.1 + random()*0.2


@pytest.mark.asyncio
async def test_list_subscriptions_deduplication(youtube_client):
    """Test that duplicate channel IDs are removed."""
    # Mock response with duplicate channel IDs
    mock_response_data = {
        "items": [
            {
                "snippet": {
                    "title": "Channel One",
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": "channel-id-1",
                    },
                }
            },
            {
                "snippet": {
                    "title": "Channel One Duplicate",
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": "channel-id-1",  # Duplicate
                    },
                }
            },
            {
                "snippet": {
                    "title": "Channel Two",
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": "channel-id-2",
                    },
                }
            },
        ]
    }

    mock_response = create_mock_response(200, mock_response_data)

    # Patch httpx.AsyncClient
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        # Call the method
        result = await youtube_client.list_subscriptions()

        # Verify deduplication - should only have 2 results
        assert len(result) == 2
        assert result[0]["channel_id"] == "channel-id-1"
        assert result[0]["title"] == "Channel One"  # First occurrence kept
        assert result[1]["channel_id"] == "channel-id-2"


@pytest.mark.asyncio
async def test_list_subscriptions_401_error(youtube_client):
    """Test that 401 response raises PermissionError."""
    # Create mock response with 401 status
    mock_response = MagicMock()
    mock_response.status_code = 401
    # Even though we won't reach json(), we need to mock it
    mock_response.json = MagicMock(return_value={})
    mock_response.raise_for_status = MagicMock()

    # Patch httpx.AsyncClient
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        # __aexit__ must return None/False to propagate exceptions
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        # Call the method and expect PermissionError
        with pytest.raises(PermissionError, match="Access token expired"):
            await youtube_client.list_subscriptions()


@pytest.mark.asyncio
async def test_list_subscriptions_http_error(youtube_client):
    """Test that other HTTP errors are raised."""
    # Create mock response with 500 status
    mock_response = MagicMock()
    mock_response.status_code = 500

    # Create a proper httpx error
    mock_request = MagicMock(spec=httpx.Request)
    mock_request.url = "https://www.googleapis.com/youtube/v3/subscriptions"
    mock_request.method = "GET"

    def raise_status_error():
        raise httpx.HTTPStatusError(
            "Server Error", request=mock_request, response=mock_response
        )

    mock_response.raise_for_status = raise_status_error

    # Patch httpx.AsyncClient
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        # __aexit__ must return None/False to propagate exceptions
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        # Call the method and expect HTTPStatusError
        with pytest.raises(httpx.HTTPStatusError):
            await youtube_client.list_subscriptions()


@pytest.mark.asyncio
async def test_list_subscriptions_filters_non_channel_items(youtube_client):
    """Test that non-channel resource types are filtered out."""
    # Mock response with mixed resource types
    mock_response_data = {
        "items": [
            {
                "snippet": {
                    "title": "Channel One",
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": "channel-id-1",
                    },
                }
            },
            {
                "snippet": {
                    "title": "Some Playlist",
                    "resourceId": {
                        "kind": "youtube#playlist",  # Not a channel
                        "playlistId": "playlist-id-1",
                    },
                }
            },
            {
                "snippet": {
                    "title": "Channel Two",
                    "resourceId": {
                        "kind": "youtube#channel",
                        "channelId": "channel-id-2",
                    },
                }
            },
        ]
    }

    mock_response = create_mock_response(200, mock_response_data)

    # Patch httpx.AsyncClient
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        # Call the method
        result = await youtube_client.list_subscriptions()

        # Verify only channel items are returned
        assert len(result) == 2
        assert result[0]["channel_id"] == "channel-id-1"
        assert result[1]["channel_id"] == "channel-id-2"


@pytest.mark.asyncio
async def test_list_subscriptions_empty_response(youtube_client):
    """Test handling of empty subscription list."""
    # Mock empty response
    mock_response_data = {"items": []}

    mock_response = create_mock_response(200, mock_response_data)

    # Patch httpx.AsyncClient
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        # Call the method
        result = await youtube_client.list_subscriptions()

        # Verify empty list is returned
        assert len(result) == 0
        assert result == []
