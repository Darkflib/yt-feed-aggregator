"""User profile endpoints for the YouTube Feed Aggregator API."""

from fastapi import APIRouter, Depends

from app.auth.router import require_user
from app.db.models import User

router = APIRouter(prefix="/api", tags=["user"])


@router.get("/me")
async def get_current_user_profile(user: User = Depends(require_user)):
    """
    Get the current authenticated user's profile.

    Returns:
        User profile with id, email, display_name, avatar_url, and created_at
    """
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at.isoformat(),
    }
