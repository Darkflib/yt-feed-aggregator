"""Account management endpoints for data export and account deletion."""

import logging
import secrets
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from redis.asyncio import Redis
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_redis
from app.auth.router import require_user
from app.config import get_settings
from app.db.crud import delete_user_account, get_user_export_data
from app.db.models import User
from app.db.session import get_session
from app.email_service import send_account_deletion_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/account", tags=["account"])
limiter = Limiter(key_func=get_remote_address)


class ExportResponse(BaseModel):
    """Response model for export request."""

    job_id: str
    message: str


class DeleteResponse(BaseModel):
    """Response model for delete request."""

    message: str


@router.post("/export", response_model=ExportResponse)
@limiter.limit("3/hour")
async def request_data_export(
    request: Request,
    user: User = Depends(require_user),
    redis: Redis = Depends(get_redis),
) -> ExportResponse:
    """
    Request a data export.

    Creates a job in Redis queue to be processed by a separate worker.
    The user will receive an email when the export is ready.

    Rate limit: 3 requests per hour per IP.
    """
    # Generate unique job ID
    job_id = secrets.token_urlsafe(16)

    # Create job metadata in Redis
    job_key = f"yt:export:job:{job_id}"
    job_data = {
        "user_id": user.id,
        "email": user.email,
        "created_at": str(int(time.time())),
        "status": "pending",
    }

    # Store job metadata (24 hour TTL)
    await redis.hset(job_key, mapping=job_data)  # type: ignore
    await redis.expire(job_key, 86400)  # 24 hours

    # Add job to queue (FIFO)
    await redis.lpush("yt:export:queue", job_id)

    return ExportResponse(
        job_id=job_id,
        message="Export request queued. You will receive an email when your data is ready.",
    )


@router.post("/delete", response_model=DeleteResponse)
@limiter.limit("5/hour")
async def request_account_deletion(
    request: Request,
    user: User = Depends(require_user),
    redis: Redis = Depends(get_redis),
) -> DeleteResponse:
    """
    Request account deletion.

    Sends a confirmation email with a secure token.
    The user must click the link in the email to complete the deletion.

    Rate limit: 5 requests per hour per IP.
    """
    # Generate secure token
    token = secrets.token_urlsafe(32)

    # Store token in Redis (1 hour TTL)
    token_key = f"yt:delete:token:{token}"
    await redis.setex(token_key, 3600, user.id)  # 1 hour

    # Build confirmation link
    settings = get_settings()
    # This endpoint is accessed directly (not through frontend), so use backend URL pattern
    confirmation_link = f"{settings.frontend_origin}/api/account/delete/confirm/{token}"

    # Send confirmation email
    try:
        email_sent = await send_account_deletion_email(
            email=user.email,
            display_name=user.display_name,
            confirmation_link=confirmation_link,
        )

        if not email_sent:
            logger.warning(
                f"Failed to send deletion confirmation email to {user.email}. "
                "Token stored in Redis but user won't receive link."
            )
            # Still return success to prevent information disclosure
            # The user will need to try again if they don't receive the email

    except ValueError as e:
        # Mailgun not configured
        logger.error(f"Email service not configured: {e}")
        raise HTTPException(
            status_code=503,
            detail="Email service is not available. Please contact support or try again later.",
        )
    except Exception as e:
        logger.error(f"Unexpected error sending deletion email: {e}", exc_info=True)
        # Continue anyway - user might have received the email despite the exception

    return DeleteResponse(
        message="A confirmation email has been sent. Please check your inbox and click the link to complete account deletion."
    )


@router.get("/delete/confirm/{token}", response_model=DeleteResponse)
@limiter.limit("10/hour")
async def confirm_account_deletion(
    request: Request,
    token: str,
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_session),
) -> DeleteResponse:
    """
    Confirm account deletion.

    Validates the token and permanently deletes the user account.
    This action cannot be undone.

    Rate limit: 10 requests per hour per IP.
    """
    # Validate token
    token_key = f"yt:delete:token:{token}"
    user_id = await redis.get(token_key)

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired confirmation token. Please request account deletion again.",
        )

    # Decode user_id (Redis returns bytes)
    if isinstance(user_id, bytes):
        user_id = user_id.decode("utf-8")

    # Delete user account (cascades to related data)
    deleted = await delete_user_account(db, user_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="User account not found. It may have already been deleted.",
        )

    # Remove token from Redis
    await redis.delete(token_key)

    # TODO: Clear session cookie
    # This should be handled by the frontend redirecting to /auth/logout

    return DeleteResponse(
        message="Your account has been permanently deleted. All your data has been removed from our systems."
    )
