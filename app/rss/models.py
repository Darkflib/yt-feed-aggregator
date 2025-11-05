"""Pydantic models for RSS feed items."""

from datetime import datetime

from pydantic import BaseModel, HttpUrl


class FeedItem(BaseModel):
    """Represents a single video item from a YouTube RSS feed."""

    video_id: str
    channel_id: str
    title: str
    link: HttpUrl
    published: datetime
