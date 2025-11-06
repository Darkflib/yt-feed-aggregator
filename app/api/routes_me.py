"""User profile endpoints for the YouTube Feed Aggregator API."""

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth.router import require_user
from app.db.models import User

router = APIRouter(prefix="/api", tags=["user"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/me")
@limiter.limit("60/minute")
async def get_current_user_profile(request: Request, user: User = Depends(require_user)):
    """
    Get the current authenticated user's profile.

    Returns:
        User profile with id, email, display_name, avatar_url, and created_at

    Rate limit: 60 requests per minute per IP.
    """
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at.isoformat(),
    }
