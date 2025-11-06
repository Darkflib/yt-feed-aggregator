"""Tests for authentication flow."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.router import (
    SESSION_COOKIE,
    _create_session_token,
    _verify_session_token,
    require_user,
)
from app.auth.security import decrypt_refresh_token, encrypt_refresh_token
from app.config import Settings
from app.db import crud
from app.db.models import Base, User
from app.db.session import get_session

# Test encryption/decryption


def test_encrypt_decrypt_refresh_token():
    """Test AES-GCM encryption and decryption of refresh tokens."""
    key = b"0" * 32  # 32-byte key for AES-256
    plaintext = "test_refresh_token_abc123"

    # Encrypt
    encrypted = encrypt_refresh_token(key, plaintext)

    # Verify encrypted is different from plaintext
    assert encrypted != plaintext.encode()
    # Verify nonce is prepended (12 bytes + ciphertext)
    assert len(encrypted) > 12

    # Decrypt
    decrypted = decrypt_refresh_token(key, encrypted)
    assert decrypted == plaintext


def test_encrypt_with_invalid_key_length():
    """Test that encryption fails with invalid key length."""
    key = b"short_key"  # Invalid key length
    plaintext = "test_token"

    with pytest.raises(ValueError, match="must be exactly 32 bytes"):
        encrypt_refresh_token(key, plaintext)


def test_decrypt_with_invalid_key_length():
    """Test that decryption fails with invalid key length."""
    key = b"short_key"  # Invalid key length
    blob = b"x" * 20

    with pytest.raises(ValueError, match="must be exactly 32 bytes"):
        decrypt_refresh_token(key, blob)


def test_decrypt_with_short_blob():
    """Test that decryption fails with blob too short for nonce."""
    key = b"0" * 32
    blob = b"short"  # Less than 12 bytes

    with pytest.raises(ValueError, match="too short"):
        decrypt_refresh_token(key, blob)


def test_decrypt_with_wrong_key():
    """Test that decryption fails with wrong key."""
    key1 = b"0" * 32
    key2 = b"1" * 32
    plaintext = "test_token"

    encrypted = encrypt_refresh_token(key1, plaintext)

    # Decryption with wrong key should raise an exception
    with pytest.raises(Exception):  # cryptography.exceptions.InvalidTag
        decrypt_refresh_token(key2, encrypted)


# Test session tokens


def test_create_verify_session_token():
    """Test JWT session token creation and verification."""
    # Mock settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.app_secret_key = "test-secret-key-for-jwt-signing"

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        user_id = "user-123"

        # Create token
        token = _create_session_token(user_id)
        assert isinstance(token, str)
        assert len(token) > 0

        # Verify token
        verified_user_id = _verify_session_token(token)
        assert verified_user_id == user_id


def test_verify_invalid_session_token():
    """Test that invalid tokens are rejected."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.app_secret_key = "test-secret-key"

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        # Invalid token
        result = _verify_session_token("invalid.token.here")
        assert result is None


def test_verify_token_with_wrong_secret(monkeypatch):
    """Test that tokens signed with different secret are rejected."""
    mock_settings_create = MagicMock(spec=Settings)
    mock_settings_create.app_secret_key = "secret-1"

    mock_settings_verify = MagicMock(spec=Settings)
    mock_settings_verify.app_secret_key = "secret-2"

    # Create with secret-1
    with patch("app.auth.router.get_settings", return_value=mock_settings_create):
        token = _create_session_token("user-123")

    # Verify with secret-2
    with patch("app.auth.router.get_settings", return_value=mock_settings_verify):
        result = _verify_session_token(token)
        assert result is None


# Test require_user dependency


@pytest.mark.asyncio
async def test_require_user_with_valid_session():
    """Test require_user dependency with valid session cookie."""
    # Create test database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as db:
        # Create test user
        user = User(
            id="user-123",
            google_sub="google-sub-123",
            email="test@example.com",
            display_name="Test User",
        )
        db.add(user)
        await db.commit()

        # Mock settings
        mock_settings = MagicMock(spec=Settings)
        mock_settings.app_secret_key = "test-secret"

        with patch("app.auth.router.get_settings", return_value=mock_settings):
            # Create valid session token
            token = _create_session_token("user-123")

            # Test require_user with valid session
            result = await require_user(session_cookie=token, db=db)
            assert result.id == "user-123"
            assert result.email == "test@example.com"

    await engine.dispose()


@pytest.mark.asyncio
async def test_require_user_without_cookie():
    """Test require_user raises 401 when no cookie is provided."""
    mock_db = MagicMock(spec=AsyncSession)

    with pytest.raises(HTTPException) as exc_info:
        await require_user(session_cookie=None, db=mock_db)

    assert exc_info.value.status_code == 401
    assert "Not authenticated" in exc_info.value.detail


@pytest.mark.asyncio
async def test_require_user_with_invalid_token():
    """Test require_user raises 401 with invalid token."""
    mock_db = MagicMock(spec=AsyncSession)
    mock_settings = MagicMock(spec=Settings)
    mock_settings.app_secret_key = "test-secret"

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        with pytest.raises(HTTPException) as exc_info:
            await require_user(session_cookie="invalid-token", db=mock_db)

        assert exc_info.value.status_code == 401
        assert "Invalid session" in exc_info.value.detail


@pytest.mark.asyncio
async def test_require_user_with_nonexistent_user():
    """Test require_user raises 401 when user doesn't exist in database."""
    # Create test database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as db:
        # Mock settings
        mock_settings = MagicMock(spec=Settings)
        mock_settings.app_secret_key = "test-secret"

        with patch("app.auth.router.get_settings", return_value=mock_settings):
            # Create token for user that doesn't exist
            token = _create_session_token("nonexistent-user")

            with pytest.raises(HTTPException) as exc_info:
                await require_user(session_cookie=token, db=db)

            assert exc_info.value.status_code == 401
            assert "User not found" in exc_info.value.detail

    await engine.dispose()


# Test OAuth flow endpoints


@pytest.mark.asyncio
async def test_login_endpoint_redirects_to_google():
    """Test that /auth/login redirects to Google OAuth."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.auth.router import router

    app = FastAPI()
    app.include_router(router)

    # Mock settings
    with patch("app.auth.router.get_settings") as mock_settings:
        mock_settings.return_value.google_client_id = "test-client-id"
        mock_settings.return_value.google_client_secret = "test-secret"
        mock_settings.return_value.google_redirect_uri = (
            "http://localhost/auth/callback"
        )

        # Mock OAuth client
        with patch("app.auth.router._get_oauth") as mock_oauth:
            from fastapi.responses import RedirectResponse

            mock_google = MagicMock()
            mock_google.authorize_redirect = AsyncMock(
                return_value=RedirectResponse(url="https://accounts.google.com/oauth")
            )
            mock_oauth.return_value.google = mock_google

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/auth/login", follow_redirects=False)

                # Should redirect
                assert response.status_code in (302, 303, 307)
                mock_google.authorize_redirect.assert_called_once()


@pytest.mark.asyncio
async def test_logout_endpoint_clears_cookie():
    """Test that /auth/logout clears the session cookie."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.auth.router import router

    app = FastAPI()
    app.include_router(router)

    client = TestClient(app)

    # Set a cookie first
    client.cookies.set(SESSION_COOKIE, "test-token")

    # Call logout
    response = client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"message": "Logged out successfully"}

    # Check that cookie is deleted
    set_cookie_header = response.headers.get("set-cookie", "")
    assert SESSION_COOKIE in set_cookie_header
    assert "Max-Age=0" in set_cookie_header or "expires=" in set_cookie_header.lower()


@pytest.mark.asyncio
async def test_callback_creates_user_and_sets_cookie():
    """Test that OAuth callback creates user and sets session cookie."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.auth.router import router

    # Create test database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    app = FastAPI()
    app.include_router(router)

    # Override get_session dependency
    async def override_get_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    # Mock settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.google_client_id = "test-client"
    mock_settings.google_client_secret = "test-secret"
    mock_settings.google_redirect_uri = "http://localhost/auth/callback"
    mock_settings.app_secret_key = "test-jwt-secret"
    mock_settings.token_enc_key = base64.b64encode(b"0" * 32).decode()
    mock_settings.env = "dev"

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        with patch("app.config.get_settings", return_value=mock_settings):
            # Mock OAuth client
            with patch("app.auth.router._get_oauth") as mock_oauth:
                mock_google = MagicMock()
                mock_google.authorize_access_token = AsyncMock(
                    return_value={
                        "access_token": "test-access-token",
                        "refresh_token": "test-refresh-token",
                        "userinfo": {
                            "sub": "google-123",
                            "email": "test@example.com",
                            "name": "Test User",
                            "picture": "https://example.com/avatar.jpg",
                        },
                    }
                )
                mock_oauth.return_value.google = mock_google

                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    # Simulate callback with code
                    response = await client.get(
                        "/auth/callback?code=test-code&state=test-state",
                        follow_redirects=False,
                    )

                    # Should redirect to home
                    assert response.status_code == 302
                    assert SESSION_COOKIE in response.cookies

                    # Verify user was created
                    async with sessionmaker() as db:
                        user = await crud.get_user_by_sub(db, "google-123")
                        assert user is not None
                        assert user.email == "test@example.com"
                        assert user.display_name == "Test User"
                        assert user.refresh_token_enc is not None

    await engine.dispose()


@pytest.mark.asyncio
async def test_me_endpoint_returns_user_info():
    """Test that /auth/me returns current user information."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.auth.router import router

    # Create test database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as db:
        # Create test user
        user = User(
            id="user-456",
            google_sub="google-456",
            email="me@example.com",
            display_name="Me User",
            avatar_url="https://example.com/me.jpg",
        )
        db.add(user)
        await db.commit()

    app = FastAPI()
    app.include_router(router)

    # Override get_session dependency
    async def override_get_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    # Mock settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.app_secret_key = "test-jwt-secret"

    with patch("app.auth.router.get_settings", return_value=mock_settings):
        # Create session token
        token = _create_session_token("user-456")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Call /auth/me with cookie
            response = await client.get("/auth/me", cookies={SESSION_COOKIE: token})

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "user-456"
            assert data["email"] == "me@example.com"
            assert data["display_name"] == "Me User"
            assert data["avatar_url"] == "https://example.com/me.jpg"

    await engine.dispose()
