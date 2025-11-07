"""Account management endpoints for data export and account deletion."""

import logging
import secrets
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from redis.asyncio import Redis
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_redis
from app.auth.router import require_user
from app.config import get_settings
from app.db.crud import delete_user_account
from app.db.models import User
from app.db.session import get_session
from app.email_service import send_account_deletion_email
from app.storage import GCSStorageBackend, LocalStorageBackend, get_storage_backend

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
    await redis.hset(job_key, mapping=job_data)  # type: ignore[arg-type]
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
    confirmation_link = f"{settings.export_url_base}/api/account/delete/confirm/{token}"

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


@router.get("/export/status/{job_id}")
@limiter.limit("60/minute")
async def get_export_status(
    request: Request,
    job_id: str,
    user: User = Depends(require_user),
    redis: Redis = Depends(get_redis),
):
    """
    Get the status of an export job.

    Returns job status and download URL if completed.

    Rate limit: 60 requests per minute per IP.
    """
    job_key = f"yt:export:job:{job_id}"
    job_data = await redis.hgetall(job_key)

    if not job_data:
        raise HTTPException(status_code=404, detail="Export job not found")

    # Verify the job belongs to the current user
    job_user_id = job_data.get(b"user_id", b"").decode("utf-8")
    if job_user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Build response
    status = job_data.get(b"status", b"pending").decode("utf-8")
    response = {
        "job_id": job_id,
        "status": status,
        "created_at": job_data.get(b"created_at", b"").decode("utf-8"),
    }

    if status == "completed":
        response["download_url"] = job_data.get(b"download_url", b"").decode("utf-8")
        response["completed_at"] = job_data.get(b"completed_at", b"").decode("utf-8")
    elif status == "failed":
        response["error"] = job_data.get(b"error", b"").decode("utf-8")

    return response


@router.get("/export/download/{filename}")
@limiter.limit("30/minute")
async def download_export(
    request: Request,
    filename: str,
    user: User = Depends(require_user),
    redis: Redis = Depends(get_redis),
):
    """
    Download an export file.

    Uses X-Accel-Redirect for nginx to serve the file efficiently.
    For GCS backend, generates a signed URL and redirects.

    Rate limit: 30 requests per minute per IP.
    """
    settings = get_settings()
    storage = get_storage_backend(settings)

    # Find the job that created this file
    # Filename format: export_{user_id}_{timestamp}_{job_id}.zip
    if not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Parse filename to extract user_id and job_id
    parts = filename.replace(".zip", "").split("_")
    if len(parts) < 4 or parts[0] != "export":
        raise HTTPException(status_code=400, detail="Invalid filename format")

    file_user_id = parts[1]
    job_id = parts[3]

    # Verify the file belongs to the current user
    if file_user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Verify the job exists and belongs to the user
    job_key = f"yt:export:job:{job_id}"
    job_data = await redis.hgetall(job_key)
    if not job_data or job_data.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Invalid or unauthorized export job")

    # Check if file exists in storage
    if isinstance(storage, LocalStorageBackend):
        # Local storage
        if not await storage.exists(filename):
            raise HTTPException(status_code=404, detail="Export file not found")

        # Use X-Accel-Redirect to let nginx serve the file
        # Nginx should have a location block like:
        # location /internal/exports/ {
        #     internal;
        #     alias /path/to/exports/;
        # }
        from fastapi.responses import Response

        return Response(
            status_code=200,
            headers={
                "X-Accel-Redirect": f"/internal/exports/{filename}",
                "Content-Type": "application/zip",
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    elif isinstance(storage, GCSStorageBackend):
        # GCS storage - generate signed URL and redirect
        storage_id = f"gs://{settings.gcs_bucket_name}/exports/{filename}"

        if not await storage.exists(storage_id):
            raise HTTPException(status_code=404, detail="Export file not found")

        # Generate signed URL valid for 1 hour
        signed_url = storage.get_signed_url(storage_id, expiration_seconds=3600)

        # Redirect to signed URL
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url=signed_url, status_code=302)

    else:
        raise HTTPException(status_code=500, detail="Unknown storage backend")
