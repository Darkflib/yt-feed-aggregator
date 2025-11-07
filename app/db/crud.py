"""CRUD utilities for database operations."""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, UserChannel, WatchedVideo


async def get_user_by_sub(db: AsyncSession, sub: str) -> User | None:
    """Get a user by their Google sub (subject identifier)."""
    result = await db.execute(select(User).where(User.google_sub == sub))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Get a user by their ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_or_update_user(
    db: AsyncSession,
    google_sub: str,
    email: str,
    display_name: str,
    avatar_url: str | None = None,
    refresh_token_enc: bytes | None = None,
) -> User:
    """Create a new user or update an existing one."""
    user = await get_user_by_sub(db, google_sub)

    if user:
        # Update existing user
        user.email = email
        user.display_name = display_name
        user.avatar_url = avatar_url
        if refresh_token_enc is not None:
            user.refresh_token_enc = refresh_token_enc
    else:
        # Create new user
        user = User(
            google_sub=google_sub,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
            refresh_token_enc=refresh_token_enc,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)
    return user


async def upsert_user_channel(
    db: AsyncSession,
    user_id: str,
    channel_id: str,
    channel_title: str,
    channel_custom_url: str | None = None,
) -> UserChannel:
    """Create or update a user's channel subscription."""
    result = await db.execute(
        select(UserChannel).where(
            UserChannel.user_id == user_id,
            UserChannel.channel_id == channel_id,
        )
    )
    channel = result.scalar_one_or_none()

    if channel:
        # Update existing channel
        channel.channel_title = channel_title
        channel.channel_custom_url = channel_custom_url
        channel.active = True
    else:
        # Create new channel
        channel = UserChannel(
            user_id=user_id,
            channel_id=channel_id,
            channel_title=channel_title,
            channel_custom_url=channel_custom_url,
        )
        db.add(channel)

    await db.commit()
    await db.refresh(channel)
    return channel


async def list_user_channels(
    db: AsyncSession, user_id: str, active_only: bool = True
) -> list[UserChannel]:
    """List all channels for a user.

    Args:
        db: Database session
        user_id: The user's ID
        active_only: If True, only return active channels (default: True)

    Returns:
        List of UserChannel objects
    """
    query = select(UserChannel).where(UserChannel.user_id == user_id)
    if active_only:
        query = query.where(UserChannel.active)
    result = await db.execute(query.order_by(UserChannel.channel_title))
    return list(result.scalars().all())


async def mark_video_watched(
    db: AsyncSession, user_id: str, video_id: str, channel_id: str
) -> WatchedVideo:
    """Mark a video as watched for a user (upsert).

    Args:
        db: Database session
        user_id: The user's ID
        video_id: YouTube video ID
        channel_id: YouTube channel ID

    Returns:
        WatchedVideo object
    """
    # Check if already watched
    result = await db.execute(
        select(WatchedVideo).where(
            WatchedVideo.user_id == user_id,
            WatchedVideo.video_id == video_id,
        )
    )
    watched = result.scalar_one_or_none()

    if watched:
        # Update watched_at timestamp
        watched.watched_at = datetime.now(timezone.utc)
    else:
        # Create new watched entry
        watched = WatchedVideo(
            user_id=user_id,
            video_id=video_id,
            channel_id=channel_id,
        )
        db.add(watched)

    await db.commit()
    await db.refresh(watched)
    return watched


async def unmark_video_watched(db: AsyncSession, user_id: str, video_id: str) -> bool:
    """Unmark a video as watched for a user.

    Args:
        db: Database session
        user_id: The user's ID
        video_id: YouTube video ID

    Returns:
        True if the video was unmarked, False if it wasn't marked
    """
    result = await db.execute(
        delete(WatchedVideo).where(
            WatchedVideo.user_id == user_id,
            WatchedVideo.video_id == video_id,
        )
    )
    await db.commit()
    return result.rowcount > 0


async def get_watched_video_ids(db: AsyncSession, user_id: str) -> set[str]:
    """Get all watched video IDs for a user.

    Args:
        db: Database session
        user_id: The user's ID

    Returns:
        Set of video IDs
    """
    result = await db.execute(
        select(WatchedVideo.video_id).where(WatchedVideo.user_id == user_id)
    )
    return set(result.scalars().all())


async def get_user_export_data(
    db: AsyncSession, user_id: str
) -> dict[str, dict | list]:
    """Get all user data for export.

    Args:
        db: Database session
        user_id: The user's ID

    Returns:
        Dictionary with user profile, subscriptions, and watched videos
        Note: Encrypted refresh token is excluded for security
    """
    # Get user profile
    user = await get_user_by_id(db, user_id)
    if not user:
        return {"profile": {}, "subscriptions": [], "watched_videos": []}

    # Get subscriptions
    channels = await list_user_channels(db, user_id, active_only=False)

    # Get watched videos
    result = await db.execute(
        select(WatchedVideo)
        .where(WatchedVideo.user_id == user_id)
        .order_by(WatchedVideo.watched_at.desc())
    )
    watched_videos = list(result.scalars().all())

    return {
        "profile": {
            "id": user.id,
            "google_sub": user.google_sub,
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        },
        "subscriptions": [
            {
                "id": ch.id,
                "channel_id": ch.channel_id,
                "channel_title": ch.channel_title,
                "channel_custom_url": ch.channel_custom_url,
                "active": ch.active,
                "added_at": ch.added_at.isoformat() if ch.added_at else None,
            }
            for ch in channels
        ],
        "watched_videos": [
            {
                "id": wv.id,
                "video_id": wv.video_id,
                "channel_id": wv.channel_id,
                "watched_at": wv.watched_at.isoformat() if wv.watched_at else None,
                "created_at": wv.created_at.isoformat() if wv.created_at else None,
                "updated_at": wv.updated_at.isoformat() if wv.updated_at else None,
            }
            for wv in watched_videos
        ],
    }


async def delete_user_account(db: AsyncSession, user_id: str) -> bool:
    """Delete a user account and all related data.

    This will cascade delete:
    - All user_channels (via ondelete="CASCADE")
    - All watched_videos (via ondelete="CASCADE")

    Args:
        db: Database session
        user_id: The user's ID

    Returns:
        True if the user was deleted, False if the user wasn't found
    """
    result = await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
    return result.rowcount > 0
