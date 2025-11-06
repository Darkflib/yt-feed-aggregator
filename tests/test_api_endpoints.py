"""Tests for API endpoints."""

import base64
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import feed_router, health_router, me_router, subscriptions_router
from app.auth.router import SESSION_COOKIE, _create_session_token
from app.config import Settings
from app.db.models import Base, User, UserChannel
from app.db.session import get_session
from app.rss.models import FeedItem


@pytest_asyncio.fixture
async def test_app():
    """Create a test FastAPI app with all routers."""
    app = FastAPI()
    app.include_router(health_router)
    app.include_router(me_router)
    app.include_router(subscriptions_router)
    app.include_router(feed_router)
    return app


@pytest_asyncio.fixture
async def test_db():
    """Create an in-memory test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    yield sessionmaker

    await engine.dispose()


@pytest_asyncio.fixture
async def test_user(test_db):
    """Create a test user in the database."""
    async with test_db() as db:
        user = User(
            id="test-user-123",
            google_sub="google-sub-123",
            email="test@example.com",
            display_name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            refresh_token_enc=b"encrypted_refresh_token",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock(spec=Settings)
    settings.app_secret_key = "test-secret-key"
    settings.token_enc_key = base64.b64encode(b"0" * 32).decode()
    settings.google_client_id = "test-client-id"
    settings.google_client_secret = "test-client-secret"
    settings.include_shorts = False
    settings.page_size_default = 24
    settings.page_size_max = 60
    return settings


def override_get_session(sessionmaker):
    """Create a dependency override for get_session."""

    async def _override():
        async with sessionmaker() as session:
            yield session

    return _override


# Health check tests


@pytest.mark.asyncio
async def test_healthz_returns_200(test_app):
    """Test /healthz endpoint returns 200 with ok status."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

        assert response.status_code == 200
        assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_readyz_returns_200(test_app):
    """Test /readyz endpoint returns 200 with ok status."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/readyz")

        assert response.status_code == 200
        assert response.json() == {"ok": True}


# /api/me tests


@pytest.mark.asyncio
async def test_api_me_returns_user_when_authenticated(
    test_app, test_db, test_user, mock_settings
):
    """Test /api/me returns user data when authenticated."""
    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        token = _create_session_token(test_user.id)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/me", cookies={SESSION_COOKIE: token})

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == test_user.id
            assert data["email"] == test_user.email
            assert data["display_name"] == test_user.display_name
            assert data["avatar_url"] == test_user.avatar_url
            assert "created_at" in data


@pytest.mark.asyncio
async def test_api_me_returns_401_when_not_authenticated(test_app, test_db):
    """Test /api/me returns 401 when not authenticated."""
    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/me")

        assert response.status_code == 401


# /api/subscriptions tests


@pytest.mark.asyncio
async def test_subscriptions_refresh_requires_authentication(test_app, test_db):
    """Test /api/subscriptions/refresh requires authentication."""
    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/subscriptions/refresh")

        assert response.status_code == 401


@pytest.mark.asyncio
async def test_subscriptions_list_returns_user_channels(
    test_app, test_db, test_user, mock_settings
):
    """Test /api/subscriptions lists user channels."""
    # Add some channels to the database
    async with test_db() as db:
        channel1 = UserChannel(
            user_id=test_user.id,
            channel_id="UC111",
            channel_title="Channel A",
            active=True,
        )
        channel2 = UserChannel(
            user_id=test_user.id,
            channel_id="UC222",
            channel_title="Channel B",
            active=True,
        )
        db.add(channel1)
        db.add(channel2)
        await db.commit()

    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        token = _create_session_token(test_user.id)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/subscriptions", cookies={SESSION_COOKIE: token}
            )

            assert response.status_code == 200
            data = response.json()
            assert "channels" in data
            assert len(data["channels"]) == 2
            assert data["channels"][0]["channel_id"] == "UC111"
            assert data["channels"][1]["channel_id"] == "UC222"


# /api/feed tests


@pytest.mark.asyncio
async def test_feed_merges_and_paginates_correctly(
    test_app, test_db, test_user, mock_settings
):
    """Test /api/feed merges and paginates correctly."""
    # Add channels to database
    async with test_db() as db:
        channel1 = UserChannel(
            user_id=test_user.id,
            channel_id="UC111",
            channel_title="Channel A",
            active=True,
        )
        db.add(channel1)
        await db.commit()

    # Mock feed items
    now = datetime.now(timezone.utc)
    feed_items = [
        FeedItem(
            video_id=f"video{i}",
            channel_id="UC111",
            title=f"Video {i}",
            link=f"https://youtube.com/watch?v=video{i}",
            published=now,
        )
        for i in range(30)
    ]

    # Mock Redis
    mock_redis = MagicMock()

    async def mock_get_redis():
        yield mock_redis

    test_app.dependency_overrides[get_session] = override_get_session(test_db)
    test_app.dependency_overrides["app.api.dependencies.get_redis"] = mock_get_redis

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        with patch("app.api.routes_feed.get_settings", return_value=mock_settings):
            with patch(
                "app.api.routes_feed.fetch_and_cache_feed",
                new=AsyncMock(return_value=feed_items),
            ):
                token = _create_session_token(test_user.id)

                transport = ASGITransport(app=test_app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.get(
                        "/api/feed?limit=10", cookies={SESSION_COOKIE: token}
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert "items" in data
                    assert "next_cursor" in data
                    assert len(data["items"]) == 10
                    assert data["next_cursor"] is not None  # More items available


@pytest.mark.asyncio
async def test_feed_filters_to_single_channel(
    test_app, test_db, test_user, mock_settings
):
    """Test /api/feed?channel_id=X filters to single channel."""
    # Add multiple channels to database (use valid YouTube channel ID format)
    async with test_db() as db:
        channel1 = UserChannel(
            user_id=test_user.id,
            channel_id="UCxxxxxxxxxxxxxxxxxxxx01",  # Valid format: UC + 22 chars = 24 total
            channel_title="Channel A",
            active=True,
        )
        channel2 = UserChannel(
            user_id=test_user.id,
            channel_id="UCxxxxxxxxxxxxxxxxxxxx02",  # Valid format: UC + 22 chars = 24 total
            channel_title="Channel B",
            active=True,
        )
        db.add(channel1)
        db.add(channel2)
        await db.commit()

    # Mock feed items for specific channel
    now = datetime.now(timezone.utc)
    feed_items_channel1 = [
        FeedItem(
            video_id=f"video_ch1_{i}",
            channel_id="UCxxxxxxxxxxxxxxxxxxxx01",
            title=f"Video {i}",
            link=f"https://youtube.com/watch?v=video_ch1_{i}",
            published=now,
        )
        for i in range(5)
    ]

    # Mock Redis
    mock_redis = MagicMock()

    async def mock_get_redis():
        yield mock_redis

    test_app.dependency_overrides[get_session] = override_get_session(test_db)
    test_app.dependency_overrides["app.api.dependencies.get_redis"] = mock_get_redis

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        with patch("app.api.routes_feed.get_settings", return_value=mock_settings):
            with patch(
                "app.api.routes_feed.fetch_and_cache_feed",
                new=AsyncMock(return_value=feed_items_channel1),
            ):
                token = _create_session_token(test_user.id)

                transport = ASGITransport(app=test_app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.get(
                        "/api/feed?channel_id=UCxxxxxxxxxxxxxxxxxxxx01", cookies={SESSION_COOKIE: token}
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert len(data["items"]) == 5
                    # Verify all items are from the requested channel
                    for item in data["items"]:
                        assert item["channel_id"] == "UCxxxxxxxxxxxxxxxxxxxx01"


@pytest.mark.asyncio
async def test_feed_respects_limit_parameter(
    test_app, test_db, test_user, mock_settings
):
    """Test /api/feed respects limit parameter."""
    async with test_db() as db:
        channel = UserChannel(
            user_id=test_user.id,
            channel_id="UC111",
            channel_title="Channel A",
            active=True,
        )
        db.add(channel)
        await db.commit()

    now = datetime.now(timezone.utc)
    feed_items = [
        FeedItem(
            video_id=f"video{i}",
            channel_id="UC111",
            title=f"Video {i}",
            link=f"https://youtube.com/watch?v=video{i}",
            published=now,
        )
        for i in range(50)
    ]

    mock_redis = MagicMock()

    async def mock_get_redis():
        yield mock_redis

    test_app.dependency_overrides[get_session] = override_get_session(test_db)
    test_app.dependency_overrides["app.api.dependencies.get_redis"] = mock_get_redis

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        with patch("app.api.routes_feed.get_settings", return_value=mock_settings):
            with patch(
                "app.api.routes_feed.fetch_and_cache_feed",
                new=AsyncMock(return_value=feed_items),
            ):
                token = _create_session_token(test_user.id)

                transport = ASGITransport(app=test_app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    # Test with custom limit
                    response = await client.get(
                        "/api/feed?limit=15", cookies={SESSION_COOKIE: token}
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert len(data["items"]) == 15


@pytest.mark.asyncio
async def test_feed_requires_authentication(test_app, test_db):
    """Test /api/feed requires authentication."""
    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/feed")

        assert response.status_code == 401
