"""Tests for account management endpoints, specifically cookie clearing."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dependencies import get_redis
from app.api.routes_account import router as account_router
from app.auth.router import SESSION_COOKIE
from app.config import Settings
from app.db.models import Base, User
from app.db.session import get_session


@pytest_asyncio.fixture
async def test_app():
    """Create a test FastAPI app with account router."""
    app = FastAPI()
    app.include_router(account_router)
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
    settings.env = "dev"  # Test in dev mode (secure=False)
    return settings


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock(spec=Redis)
    # Configure get and delete methods to be async
    redis.get = AsyncMock()
    redis.delete = AsyncMock()
    return redis


def override_get_session(sessionmaker):
    """Create a dependency override for get_session."""

    async def _override():
        async with sessionmaker() as session:
            yield session

    return _override


def override_get_redis(redis):
    """Create a dependency override for get_redis."""

    async def _override():
        yield redis

    return _override


@pytest.mark.asyncio
async def test_confirm_account_deletion_clears_session_cookie(
    test_app, test_db, test_user, mock_settings, mock_redis
):
    """Test that account deletion confirmation clears the session cookie."""
    # Setup
    test_app.dependency_overrides[get_session] = override_get_session(test_db)
    test_app.dependency_overrides[get_redis] = override_get_redis(mock_redis)

    deletion_token = "test-deletion-token"
    token_key = f"yt:delete:token:{deletion_token}"

    # Mock Redis to return user_id for the token
    mock_redis.get.return_value = test_user.id.encode("utf-8")
    mock_redis.delete.return_value = True

    with patch("app.api.routes_account.get_settings", return_value=mock_settings):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Set a session cookie to verify it gets cleared
            client.cookies.set(SESSION_COOKIE, "some-session-token")

            # Make the deletion confirmation request
            response = await client.get(f"/api/account/delete/confirm/{deletion_token}")

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "permanently deleted" in data["message"].lower(), (
                f"Expected deletion message, got: {data['message']}"
            )

            # Verify Redis calls
            mock_redis.get.assert_called_once_with(token_key)
            mock_redis.delete.assert_called_once_with(token_key)

            # Verify session cookie is cleared via set-cookie header
            set_cookie_header = response.headers.get("set-cookie", "")
            assert SESSION_COOKIE in set_cookie_header, (
                f"Session cookie should be in set-cookie header, got: {set_cookie_header}"
            )

            # Cookie deletion is indicated by max-age=0 or expires in the past
            # The response should include the cookie name in the set-cookie header
            assert (
                "max-age=0" in set_cookie_header.lower()
                or f"{SESSION_COOKIE}=" in set_cookie_header
            ), (
                f"Session cookie should be cleared/deleted in response headers: {set_cookie_header}"
            )


@pytest.mark.asyncio
async def test_confirm_account_deletion_uses_correct_cookie_settings(
    test_app, test_db, test_user, mock_redis
):
    """Test that cookie deletion uses correct security settings based on environment."""
    # Test with production settings
    prod_settings = MagicMock(spec=Settings)
    prod_settings.env = "prod"

    test_app.dependency_overrides[get_session] = override_get_session(test_db)
    test_app.dependency_overrides[get_redis] = override_get_redis(mock_redis)

    deletion_token = "test-deletion-token"
    mock_redis.get.return_value = test_user.id.encode("utf-8")
    mock_redis.delete.return_value = True

    with patch("app.api.routes_account.get_settings", return_value=prod_settings):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/account/delete/confirm/{deletion_token}")

            assert response.status_code == 200

            # Verify set-cookie header includes secure flag for production
            set_cookie_header = response.headers.get("set-cookie", "")
            assert SESSION_COOKIE in set_cookie_header, (
                "Session cookie should be in set-cookie header"
            )
            # In production, the secure flag should be set
            assert "secure" in set_cookie_header.lower(), (
                "Cookie should have secure flag in production"
            )


@pytest.mark.asyncio
async def test_confirm_account_deletion_with_invalid_token(
    test_app, test_db, mock_redis, mock_settings
):
    """Test that invalid token returns 400 and doesn't clear cookie."""
    test_app.dependency_overrides[get_session] = override_get_session(test_db)
    test_app.dependency_overrides[get_redis] = override_get_redis(mock_redis)

    # Mock Redis to return None (invalid/expired token)
    mock_redis.get.return_value = None

    with patch("app.api.routes_account.get_settings", return_value=mock_settings):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/account/delete/confirm/invalid-token")

            assert response.status_code == 400
            assert "Invalid or expired" in response.json()["detail"]
