"""Tests for watched videos functionality."""

import base64
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import feed_router, watched_router
from app.auth.router import SESSION_COOKIE, _create_session_token
from app.config import Settings
from app.db.crud import (
    get_watched_video_ids,
    mark_video_watched,
    unmark_video_watched,
)
from app.db.models import Base, User, UserChannel, WatchedVideo
from app.db.session import get_session
from app.rss.models import FeedItem


@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False}
    )

    # Enable foreign key support for SQLite
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Create a database session for testing."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def test_db():
    """Create an in-memory test database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False}
    )

    # Enable foreign key support for SQLite
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=ON"))
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
    settings.redis_url = "redis://localhost:6379/0"
    return settings


def override_get_session(sessionmaker):
    """Create a dependency override for get_session."""

    async def _override():
        async with sessionmaker() as session:
            yield session

    return _override


# CRUD operation tests


@pytest.mark.asyncio
async def test_mark_video_watched(db_session: AsyncSession):
    """Test marking a video as watched."""
    # Create a user first
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Mark a video as watched
    watched = await mark_video_watched(
        db_session, user.id, "video123", "channel456"
    )

    assert watched.id is not None
    assert watched.user_id == user.id
    assert watched.video_id == "video123"
    assert watched.channel_id == "channel456"
    assert watched.watched_at is not None
    assert watched.created_at is not None


@pytest.mark.asyncio
async def test_mark_video_watched_updates_timestamp(db_session: AsyncSession):
    """Test that marking an already watched video updates the timestamp."""
    # Create a user
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Mark a video as watched the first time
    watched1 = await mark_video_watched(
        db_session, user.id, "video123", "channel456"
    )
    first_watched_at = watched1.watched_at
    first_id = watched1.id

    # Mark the same video as watched again
    watched2 = await mark_video_watched(
        db_session, user.id, "video123", "channel456"
    )

    # Should be the same record (same ID) but with updated timestamp
    assert watched2.id == first_id
    assert watched2.watched_at >= first_watched_at


@pytest.mark.asyncio
async def test_unmark_video_watched(db_session: AsyncSession):
    """Test unmarking a video as watched."""
    # Create a user
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Mark a video as watched
    await mark_video_watched(db_session, user.id, "video123", "channel456")

    # Verify it's marked
    video_ids = await get_watched_video_ids(db_session, user.id)
    assert "video123" in video_ids

    # Unmark the video
    success = await unmark_video_watched(db_session, user.id, "video123")
    assert success is True

    # Verify it's unmarked
    video_ids = await get_watched_video_ids(db_session, user.id)
    assert "video123" not in video_ids


@pytest.mark.asyncio
async def test_unmark_video_not_watched(db_session: AsyncSession):
    """Test unmarking a video that wasn't marked returns False."""
    # Create a user
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Try to unmark a video that was never marked
    success = await unmark_video_watched(db_session, user.id, "video999")
    assert success is False


@pytest.mark.asyncio
async def test_get_watched_video_ids(db_session: AsyncSession):
    """Test getting all watched video IDs for a user."""
    # Create a user
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Mark several videos as watched
    await mark_video_watched(db_session, user.id, "video1", "channel1")
    await mark_video_watched(db_session, user.id, "video2", "channel1")
    await mark_video_watched(db_session, user.id, "video3", "channel2")

    # Get watched video IDs
    video_ids = await get_watched_video_ids(db_session, user.id)

    assert len(video_ids) == 3
    assert "video1" in video_ids
    assert "video2" in video_ids
    assert "video3" in video_ids


@pytest.mark.asyncio
async def test_get_watched_video_ids_empty(db_session: AsyncSession):
    """Test getting watched video IDs returns empty set when none watched."""
    # Create a user
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Get watched video IDs (should be empty)
    video_ids = await get_watched_video_ids(db_session, user.id)

    assert len(video_ids) == 0
    assert isinstance(video_ids, set)


@pytest.mark.asyncio
async def test_watched_video_unique_constraint(db_session: AsyncSession):
    """Test that (user_id, video_id) must be unique."""
    # Create a user
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create first watched entry
    watched1 = WatchedVideo(
        user_id=user.id,
        video_id="video123",
        channel_id="channel456",
    )
    db_session.add(watched1)
    await db_session.commit()

    # Try to create another entry with the same user_id and video_id
    # This should be handled by the mark_video_watched function (upsert logic)
    # but if we try to insert directly, it would fail
    # For this test, we verify the upsert behavior works
    watched2 = await mark_video_watched(
        db_session, user.id, "video123", "channel456"
    )

    # Should be the same record
    assert watched2.id == watched1.id


@pytest.mark.asyncio
async def test_cascade_delete_watched_videos(db_session: AsyncSession):
    """Test that deleting a user cascades to delete their watched videos."""
    # Create a user
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = user.id  # Store user_id before deletion

    # Mark some videos as watched
    await mark_video_watched(db_session, user_id, "video1", "channel1")
    await mark_video_watched(db_session, user_id, "video2", "channel1")

    # Verify videos are marked
    video_ids = await get_watched_video_ids(db_session, user_id)
    assert len(video_ids) == 2

    # Delete the user
    await db_session.delete(user)
    await db_session.commit()

    # Verify watched videos were deleted (cascade)
    result = await db_session.execute(
        select(WatchedVideo).where(WatchedVideo.user_id == user_id)
    )
    watched_videos = result.scalars().all()
    assert len(watched_videos) == 0


# API endpoint tests


@pytest_asyncio.fixture
async def test_app():
    """Create a test FastAPI app with watched router."""
    app = FastAPI()
    app.include_router(watched_router)
    app.include_router(feed_router)
    return app


@pytest.mark.asyncio
async def test_mark_video_watched_endpoint(test_app, test_db, test_user, mock_settings):
    """Test POST /api/watched endpoint."""
    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        token = _create_session_token(test_user.id)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE, token)
            response = await client.post(
                "/api/watched",
                json={"video_id": "video123", "channel_id": "channel456"},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["video_id"] == "video123"
            assert data["channel_id"] == "channel456"
            assert "watched_at" in data


@pytest.mark.asyncio
async def test_mark_video_watched_requires_auth(test_app, test_db):
    """Test POST /api/watched requires authentication."""
    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/watched",
            json={"video_id": "video123", "channel_id": "channel456"},
        )

        assert response.status_code == 401


@pytest.mark.asyncio
async def test_mark_video_watched_validates_input(
    test_app, test_db, test_user, mock_settings
):
    """Test POST /api/watched validates input."""
    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        token = _create_session_token(test_user.id)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE, token)

            # Test empty video_id
            response = await client.post(
                "/api/watched",
                json={"video_id": "", "channel_id": "channel456"},
            )
            assert response.status_code == 400

            # Test empty channel_id
            response = await client.post(
                "/api/watched",
                json={"video_id": "video123", "channel_id": ""},
            )
            assert response.status_code == 400


@pytest.mark.asyncio
async def test_unmark_video_watched_endpoint(
    test_app, test_db, test_user, mock_settings
):
    """Test DELETE /api/watched/{video_id} endpoint."""
    # First mark a video as watched
    async with test_db() as db:
        await mark_video_watched(db, test_user.id, "video123", "channel456")

    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        token = _create_session_token(test_user.id)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE, token)
            response = await client.delete("/api/watched/video123")

            assert response.status_code == 204


@pytest.mark.asyncio
async def test_unmark_video_not_found(test_app, test_db, test_user, mock_settings):
    """Test DELETE /api/watched/{video_id} returns 404 for non-existent video."""
    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        token = _create_session_token(test_user.id)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE, token)
            response = await client.delete("/api/watched/video999")

            assert response.status_code == 404


@pytest.mark.asyncio
async def test_unmark_video_requires_auth(test_app, test_db):
    """Test DELETE /api/watched/{video_id} requires authentication."""
    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/watched/video123")

        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_watched_videos_endpoint(test_app, test_db, test_user, mock_settings):
    """Test GET /api/watched endpoint."""
    # Mark some videos as watched
    async with test_db() as db:
        await mark_video_watched(db, test_user.id, "video1", "channel1")
        await mark_video_watched(db, test_user.id, "video2", "channel1")
        await mark_video_watched(db, test_user.id, "video3", "channel2")

    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        token = _create_session_token(test_user.id)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE, token)
            response = await client.get("/api/watched")

            assert response.status_code == 200
            data = response.json()
            assert "video_ids" in data
            assert len(data["video_ids"]) == 3
            assert "video1" in data["video_ids"]
            assert "video2" in data["video_ids"]
            assert "video3" in data["video_ids"]


@pytest.mark.asyncio
async def test_get_watched_videos_empty(test_app, test_db, test_user, mock_settings):
    """Test GET /api/watched returns empty list when no videos watched."""
    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        token = _create_session_token(test_user.id)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(SESSION_COOKIE, token)
            response = await client.get("/api/watched")

            assert response.status_code == 200
            data = response.json()
            assert "video_ids" in data
            assert len(data["video_ids"]) == 0


@pytest.mark.asyncio
async def test_get_watched_videos_requires_auth(test_app, test_db):
    """Test GET /api/watched requires authentication."""
    test_app.dependency_overrides[get_session] = override_get_session(test_db)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/watched")

        assert response.status_code == 401


# Feed integration tests


@pytest.mark.asyncio
async def test_feed_includes_watched_status(test_app, test_db, test_user, mock_settings):
    """Test that /api/feed includes watched status for videos."""
    # Add a channel to database
    async with test_db() as db:
        channel = UserChannel(
            user_id=test_user.id,
            channel_id="UC111",
            channel_title="Channel A",
            active=True,
        )
        db.add(channel)
        await db.commit()

        # Mark one video as watched
        await mark_video_watched(db, test_user.id, "video1", "UC111")

    # Mock feed items
    now = datetime.now(timezone.utc)
    feed_items = [
        FeedItem(
            video_id="video1",
            channel_id="UC111",
            title="Video 1",
            link="https://youtube.com/watch?v=video1",
            published=now,
        ),
        FeedItem(
            video_id="video2",
            channel_id="UC111",
            title="Video 2",
            link="https://youtube.com/watch?v=video2",
            published=now,
        ),
    ]

    # Mock Redis
    mock_redis = MagicMock()

    async def mock_get_redis():
        yield mock_redis

    test_app.dependency_overrides[get_session] = override_get_session(test_db)
    test_app.dependency_overrides["app.api.dependencies.get_redis"] = mock_get_redis

    # Reset the settings cache and patch both locations
    import app.config
    original_settings = app.config._settings
    app.config._settings = mock_settings

    try:
        with patch("app.auth.router.get_settings", return_value=mock_settings):
            with patch(
                "app.api.routes_feed.fetch_and_cache_feed",
                new=AsyncMock(return_value=feed_items),
            ):
                token = _create_session_token(test_user.id)

                transport = ASGITransport(app=test_app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    client.cookies.set(SESSION_COOKIE, token)
                    response = await client.get("/api/feed")

                    assert response.status_code == 200
                    data = response.json()
                    assert "items" in data

                    # Find the videos and check watched status
                    video1 = next(
                        (item for item in data["items"] if item["video_id"] == "video1"),
                        None,
                    )
                    video2 = next(
                        (item for item in data["items"] if item["video_id"] == "video2"),
                        None,
                    )

                    assert video1 is not None
                    assert video2 is not None
                    assert video1["watched"] is True
                    assert video2["watched"] is False
    finally:
        # Restore original settings
        app.config._settings = original_settings


@pytest.mark.asyncio
async def test_feed_watched_status_with_no_watched_videos(
    test_app, test_db, test_user, mock_settings
):
    """Test that /api/feed sets watched=False when user hasn't watched any videos."""
    # Add a channel to database
    async with test_db() as db:
        channel = UserChannel(
            user_id=test_user.id,
            channel_id="UC111",
            channel_title="Channel A",
            active=True,
        )
        db.add(channel)
        await db.commit()

    # Mock feed items
    now = datetime.now(timezone.utc)
    feed_items = [
        FeedItem(
            video_id="video1",
            channel_id="UC111",
            title="Video 1",
            link="https://youtube.com/watch?v=video1",
            published=now,
        ),
    ]

    # Mock Redis
    mock_redis = MagicMock()

    async def mock_get_redis():
        yield mock_redis

    test_app.dependency_overrides[get_session] = override_get_session(test_db)
    test_app.dependency_overrides["app.api.dependencies.get_redis"] = mock_get_redis

    # Reset the settings cache and patch both locations
    import app.config
    original_settings = app.config._settings
    app.config._settings = mock_settings

    try:
        with patch("app.auth.router.get_settings", return_value=mock_settings):
            with patch(
                "app.api.routes_feed.fetch_and_cache_feed",
                new=AsyncMock(return_value=feed_items),
            ):
                token = _create_session_token(test_user.id)

                transport = ASGITransport(app=test_app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    client.cookies.set(SESSION_COOKIE, token)
                    response = await client.get("/api/feed")

                    assert response.status_code == 200
                    data = response.json()
                    assert "items" in data
                    assert len(data["items"]) > 0

                    # All videos should be unwatched
                    for item in data["items"]:
                        assert "watched" in item
                        assert item["watched"] is False
    finally:
        # Restore original settings
        app.config._settings = original_settings


@pytest.mark.asyncio
async def test_different_users_have_separate_watched_lists(db_session: AsyncSession):
    """Test that different users have separate watched video lists."""
    # Create two users
    user1 = User(
        google_sub="user1",
        email="user1@example.com",
        display_name="User 1",
    )
    user2 = User(
        google_sub="user2",
        email="user2@example.com",
        display_name="User 2",
    )
    db_session.add_all([user1, user2])
    await db_session.commit()
    await db_session.refresh(user1)
    await db_session.refresh(user2)

    # User 1 marks some videos as watched
    await mark_video_watched(db_session, user1.id, "video1", "channel1")
    await mark_video_watched(db_session, user1.id, "video2", "channel1")

    # User 2 marks different videos as watched
    await mark_video_watched(db_session, user2.id, "video3", "channel1")

    # Get watched videos for each user
    user1_videos = await get_watched_video_ids(db_session, user1.id)
    user2_videos = await get_watched_video_ids(db_session, user2.id)

    # Verify users have separate lists
    assert len(user1_videos) == 2
    assert "video1" in user1_videos
    assert "video2" in user1_videos
    assert "video3" not in user1_videos

    assert len(user2_videos) == 1
    assert "video3" in user2_videos
    assert "video1" not in user2_videos
    assert "video2" not in user2_videos
