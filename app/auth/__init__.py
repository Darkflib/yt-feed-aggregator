"""Authentication module for YouTube Feed Aggregator."""

from app.auth.router import require_user, router

__all__ = ["router", "require_user"]
