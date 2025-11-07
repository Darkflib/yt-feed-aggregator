"""API routers for the YouTube Feed Aggregator."""

from app.api.routes_feed import router as feed_router
from app.api.routes_health import router as health_router
from app.api.routes_me import router as me_router
from app.api.routes_subscriptions import router as subscriptions_router
from app.api.routes_watched import router as watched_router

__all__ = [
    "health_router",
    "me_router",
    "subscriptions_router",
    "feed_router",
    "watched_router",
]
