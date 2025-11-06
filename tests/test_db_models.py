"""Tests for database models and CRUD operations."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.crud import (
    create_or_update_user,
    get_user_by_id,
    get_user_by_sub,
    upsert_user_channel,
)
from app.db.models import Base, User, UserChannel


@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create all tables
    async with engine.begin() as conn:
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


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """Test creating a new user."""
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
        avatar_url="https://example.com/avatar.jpg",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Verify user was created
    assert user.id is not None
    assert user.google_sub == "12345"
    assert user.email == "test@example.com"
    assert user.display_name == "Test User"
    assert user.avatar_url == "https://example.com/avatar.jpg"
    assert user.created_at is not None
    assert user.updated_at is not None
    assert user.refresh_token_enc is None


@pytest.mark.asyncio
async def test_create_user_channel(db_session: AsyncSession):
    """Test creating a new user channel."""
    # First create a user
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create a channel for the user
    channel = UserChannel(
        user_id=user.id,
        channel_id="UC_test_channel",
        channel_title="Test Channel",
        channel_custom_url="@testchannel",
    )
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)

    # Verify channel was created
    assert channel.id is not None
    assert channel.user_id == user.id
    assert channel.channel_id == "UC_test_channel"
    assert channel.channel_title == "Test Channel"
    assert channel.channel_custom_url == "@testchannel"
    assert channel.active is True
    assert channel.added_at is not None


@pytest.mark.asyncio
async def test_user_channel_relationship(db_session: AsyncSession):
    """Test the relationship between User and UserChannel."""
    # Create a user
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create multiple channels
    channel1 = UserChannel(
        user_id=user.id,
        channel_id="UC_channel1",
        channel_title="Channel 1",
    )
    channel2 = UserChannel(
        user_id=user.id,
        channel_id="UC_channel2",
        channel_title="Channel 2",
    )
    db_session.add_all([channel1, channel2])
    await db_session.commit()

    # Reload user to get relationships
    await db_session.refresh(user)
    result = await db_session.execute(select(User).where(User.id == user.id))
    user_with_channels = result.scalar_one()

    # Access channels relationship
    result = await db_session.execute(
        select(UserChannel).where(UserChannel.user_id == user_with_channels.id)
    )
    channels = result.scalars().all()

    # Verify relationships
    assert len(channels) == 2
    assert channels[0].user_id == user.id
    assert channels[1].user_id == user.id


@pytest.mark.asyncio
async def test_foreign_key_cascade(db_session: AsyncSession):
    """Test that deleting a user cascades to delete their channels."""
    # Create a user
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create channels for the user
    channel1 = UserChannel(
        user_id=user.id,
        channel_id="UC_channel1",
        channel_title="Channel 1",
    )
    channel2 = UserChannel(
        user_id=user.id,
        channel_id="UC_channel2",
        channel_title="Channel 2",
    )
    db_session.add_all([channel1, channel2])
    await db_session.commit()

    # Verify channels exist
    result = await db_session.execute(
        select(UserChannel).where(UserChannel.user_id == user.id)
    )
    channels = result.scalars().all()
    assert len(channels) == 2

    # Delete the user
    await db_session.delete(user)
    await db_session.commit()

    # Verify channels were also deleted (cascade)
    result = await db_session.execute(
        select(UserChannel).where(UserChannel.user_id == user.id)
    )
    channels = result.scalars().all()
    assert len(channels) == 0


@pytest.mark.asyncio
async def test_get_user_by_sub(db_session: AsyncSession):
    """Test getting a user by their Google sub."""
    # Create a user
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()

    # Get user by sub
    found_user = await get_user_by_sub(db_session, "12345")
    assert found_user is not None
    assert found_user.google_sub == "12345"
    assert found_user.email == "test@example.com"

    # Try to get non-existent user
    not_found = await get_user_by_sub(db_session, "99999")
    assert not_found is None


@pytest.mark.asyncio
async def test_get_user_by_id(db_session: AsyncSession):
    """Test getting a user by their ID."""
    # Create a user
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Get user by ID
    found_user = await get_user_by_id(db_session, user.id)
    assert found_user is not None
    assert found_user.id == user.id
    assert found_user.google_sub == "12345"

    # Try to get non-existent user
    not_found = await get_user_by_id(db_session, "non-existent-id")
    assert not_found is None


@pytest.mark.asyncio
async def test_create_or_update_user_create(db_session: AsyncSession):
    """Test creating a new user with create_or_update_user."""
    user = await create_or_update_user(
        db_session,
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
        avatar_url="https://example.com/avatar.jpg",
    )

    assert user.id is not None
    assert user.google_sub == "12345"
    assert user.email == "test@example.com"
    assert user.display_name == "Test User"
    assert user.avatar_url == "https://example.com/avatar.jpg"


@pytest.mark.asyncio
async def test_create_or_update_user_update(db_session: AsyncSession):
    """Test updating an existing user with create_or_update_user."""
    # Create initial user
    user = await create_or_update_user(
        db_session,
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
        avatar_url="https://example.com/avatar.jpg",
    )
    initial_id = user.id

    # Update the user
    updated_user = await create_or_update_user(
        db_session,
        google_sub="12345",
        email="updated@example.com",
        display_name="Updated User",
        avatar_url="https://example.com/new-avatar.jpg",
    )

    # Should be the same user (same ID)
    assert updated_user.id == initial_id
    assert updated_user.google_sub == "12345"
    assert updated_user.email == "updated@example.com"
    assert updated_user.display_name == "Updated User"
    assert updated_user.avatar_url == "https://example.com/new-avatar.jpg"


@pytest.mark.asyncio
async def test_upsert_user_channel_create(db_session: AsyncSession):
    """Test creating a new channel with upsert_user_channel."""
    # Create a user first
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create a channel
    channel = await upsert_user_channel(
        db_session,
        user_id=user.id,
        channel_id="UC_test",
        channel_title="Test Channel",
        channel_custom_url="@testchannel",
    )

    assert channel.id is not None
    assert channel.user_id == user.id
    assert channel.channel_id == "UC_test"
    assert channel.channel_title == "Test Channel"
    assert channel.channel_custom_url == "@testchannel"
    assert channel.active is True


@pytest.mark.asyncio
async def test_upsert_user_channel_update(db_session: AsyncSession):
    """Test updating an existing channel with upsert_user_channel."""
    # Create a user first
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create initial channel
    channel = await upsert_user_channel(
        db_session,
        user_id=user.id,
        channel_id="UC_test",
        channel_title="Test Channel",
        channel_custom_url="@testchannel",
    )
    initial_id = channel.id

    # Update the channel
    updated_channel = await upsert_user_channel(
        db_session,
        user_id=user.id,
        channel_id="UC_test",
        channel_title="Updated Channel",
        channel_custom_url="@updatedchannel",
    )

    # Should be the same channel (same ID)
    assert updated_channel.id == initial_id
    assert updated_channel.channel_id == "UC_test"
    assert updated_channel.channel_title == "Updated Channel"
    assert updated_channel.channel_custom_url == "@updatedchannel"
    assert updated_channel.active is True


@pytest.mark.asyncio
async def test_upsert_user_channel_reactivate(db_session: AsyncSession):
    """Test that upsert reactivates a deactivated channel."""
    # Create a user first
    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create a channel
    channel = UserChannel(
        user_id=user.id,
        channel_id="UC_test",
        channel_title="Test Channel",
        active=False,  # Initially inactive
    )
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)

    # Upsert should reactivate it
    updated_channel = await upsert_user_channel(
        db_session,
        user_id=user.id,
        channel_id="UC_test",
        channel_title="Test Channel",
    )

    assert updated_channel.active is True


@pytest.mark.asyncio
async def test_unique_google_sub(db_session: AsyncSession):
    """Test that google_sub must be unique."""
    # Create first user
    user1 = User(
        google_sub="12345",
        email="test1@example.com",
        display_name="Test User 1",
    )
    db_session.add(user1)
    await db_session.commit()

    # Try to create another user with the same google_sub
    user2 = User(
        google_sub="12345",
        email="test2@example.com",
        display_name="Test User 2",
    )
    db_session.add(user2)

    # Should raise an exception
    with pytest.raises(Exception):  # Will be an IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_user_with_encrypted_token(db_session: AsyncSession):
    """Test storing encrypted refresh token."""
    encrypted_token = b"encrypted_refresh_token_data"

    user = User(
        google_sub="12345",
        email="test@example.com",
        display_name="Test User",
        refresh_token_enc=encrypted_token,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Verify token was stored correctly
    assert user.refresh_token_enc == encrypted_token
    assert isinstance(user.refresh_token_enc, bytes)
