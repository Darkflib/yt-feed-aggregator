"""Watched videos endpoints for the YouTube Feed Aggregator API."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import require_user
from app.db import crud
from app.db.models import User
from app.db.session import get_session

router = APIRouter(prefix="/api/watched", tags=["watched"])
limiter = Limiter(key_func=get_remote_address)


class MarkWatchedRequest(BaseModel):
    """Request model for marking a video as watched."""

    video_id: str
    channel_id: str


class WatchedVideoResponse(BaseModel):
    """Response model for a watched video."""

    video_id: str
    channel_id: str
    watched_at: str


class WatchedVideosListResponse(BaseModel):
    """Response model for listing watched video IDs."""

    video_ids: list[str]


@router.post("", status_code=201, response_model=WatchedVideoResponse)
@limiter.limit("60/minute")
async def mark_video_watched(
    request: Request,
    body: MarkWatchedRequest,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """
    Mark a video as watched for the current user.

    This endpoint allows users to mark videos as watched. If the video is already
    marked as watched, it updates the watched_at timestamp.

    Rate limit: 60 requests per minute per IP.

    Args:
        body: Request body containing video_id and channel_id

    Returns:
        Watched video details including video_id, channel_id, and watched_at timestamp

    Raises:
        HTTPException: 400 if video_id or channel_id is empty
    """
    # Validate input
    if not body.video_id or not body.video_id.strip():
        raise HTTPException(status_code=400, detail="video_id cannot be empty")
    if not body.channel_id or not body.channel_id.strip():
        raise HTTPException(status_code=400, detail="channel_id cannot be empty")

    watched = await crud.mark_video_watched(db, user.id, body.video_id, body.channel_id)

    return WatchedVideoResponse(
        video_id=watched.video_id,
        channel_id=watched.channel_id,
        watched_at=watched.watched_at.isoformat(),
    )


@router.delete("/{video_id}", status_code=204)
@limiter.limit("60/minute")
async def unmark_video_watched(
    request: Request,
    video_id: str,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """
    Unmark a video as watched for the current user.

    This endpoint allows users to remove a video from their watched list.

    Rate limit: 60 requests per minute per IP.

    Args:
        video_id: The YouTube video ID to unmark

    Returns:
        204 No Content on success

    Raises:
        HTTPException: 404 if the video was not marked as watched
    """
    if not video_id or not video_id.strip():
        raise HTTPException(status_code=400, detail="video_id cannot be empty")

    success = await crud.unmark_video_watched(db, user.id, video_id)

    if not success:
        raise HTTPException(status_code=404, detail="Video not found in watched list")


@router.get("", response_model=WatchedVideosListResponse)
@limiter.limit("120/minute")
async def get_watched_videos(
    request: Request,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """
    Get all watched video IDs for the current user.

    This endpoint returns a list of all video IDs that the user has marked as watched.

    Rate limit: 120 requests per minute per IP.

    Returns:
        List of watched video IDs
    """
    video_ids = await crud.get_watched_video_ids(db, user.id)

    return WatchedVideosListResponse(video_ids=sorted(video_ids))
