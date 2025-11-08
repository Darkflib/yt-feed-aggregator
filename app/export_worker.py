"""Export worker that processes data export jobs from Redis queue."""

import asyncio
import io
import json
import logging
import time
import zipfile
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.crud import get_user_export_data
from app.db.session import get_sessionmaker
from app.email_service import send_data_export_ready_email
from app.storage import get_storage_backend

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def create_export_zip(export_data: dict[str, Any]) -> bytes:
    """
    Create a ZIP file containing the user's export data.

    Args:
        export_data: Dictionary with profile, subscriptions, and watched_videos

    Returns:
        ZIP file as bytes
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Add profile.json
        profile_json = json.dumps(export_data["profile"], indent=2, ensure_ascii=False)
        zip_file.writestr("profile.json", profile_json)

        # Add subscriptions.json
        subscriptions_json = json.dumps(
            export_data["subscriptions"], indent=2, ensure_ascii=False
        )
        zip_file.writestr("subscriptions.json", subscriptions_json)

        # Add watched_videos.json
        watched_json = json.dumps(
            export_data["watched_videos"], indent=2, ensure_ascii=False
        )
        zip_file.writestr("watched_videos.json", watched_json)

        # Add README.txt with explanation
        readme = """YouTube Feed Aggregator - Data Export
========================================

This archive contains your personal data from YouTube Feed Aggregator.

Files included:
- profile.json: Your user profile information
- subscriptions.json: Your YouTube channel subscriptions
- watched_videos.json: Your watched video history

All files are in JSON format and can be opened with any text editor.

For questions or support, please contact the administrator.

Export generated: {timestamp}
""".format(timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))
        zip_file.writestr("README.txt", readme)

    return zip_buffer.getvalue()


async def process_export_job(
    job_id: str,
    redis: Redis,
    db: AsyncSession,
) -> bool:
    """
    Process a single export job.

    Args:
        job_id: Job ID from Redis queue
        redis: Redis client
        db: Database session

    Returns:
        True if successful, False otherwise
    """
    settings = get_settings()
    storage = get_storage_backend(settings)

    try:
        # Get job metadata
        job_key = f"yt:export:job:{job_id}"
        job_data = await redis.hgetall(job_key)  # type: ignore[misc]

        if not job_data:
            logger.error(f"Job {job_id} not found in Redis")
            return False

        # Decode job data
        user_id = job_data.get(b"user_id", b"").decode("utf-8")
        email = job_data.get(b"email", b"").decode("utf-8")

        if not user_id or not email:
            logger.error(f"Job {job_id} missing user_id or email")
            return False

        logger.info(f"Processing export job {job_id} for user {user_id}")

        # Update job status to processing
        await redis.hset(job_key, "status", "processing")  # type: ignore[misc]

        # Fetch user data
        export_data = await get_user_export_data(db, user_id)

        if not export_data["profile"]:
            logger.error(f"User {user_id} not found for export job {job_id}")
            await redis.hset(job_key, "status", "failed")  # type: ignore[misc]
            await redis.hset(job_key, "error", "User not found")  # type: ignore[misc]
            return False

        # Create ZIP file
        logger.info(f"Creating ZIP archive for job {job_id}")
        zip_data = await create_export_zip(export_data)

        # Generate filename
        timestamp = int(time.time())
        filename = f"export_{user_id}_{timestamp}_{job_id}.zip"

        # Save to storage
        logger.info(
            f"Saving export to storage backend: {settings.export_storage_backend}"
        )
        storage_id = await storage.save(filename, zip_data)

        # Get download URL
        download_url = await storage.get_download_url(storage_id)

        # Store download URL in Redis
        await redis.hset(job_key, "storage_id", storage_id)  # type: ignore[misc]
        await redis.hset(job_key, "download_url", download_url)  # type: ignore[misc]
        await redis.hset(job_key, "completed_at", str(int(time.time())))  # type: ignore[misc]
        await redis.hset(job_key, "status", "completed")  # type: ignore[misc]

        # Extend TTL to match export retention
        ttl_seconds = settings.export_ttl_hours * 3600
        await redis.expire(job_key, ttl_seconds)

        logger.info(f"Export job {job_id} completed successfully")

        # Send email notification
        display_name = export_data["profile"].get("display_name", email.split("@")[0])  # type: ignore[union-attr]

        try:
            await send_data_export_ready_email(email, display_name, download_url)
            logger.info(f"Sent export ready email to {email}")
        except Exception as e:
            logger.error(f"Failed to send export email to {email}: {e}", exc_info=True)
            # Don't fail the job if email fails - data is still available

        return True

    except Exception as e:
        logger.error(f"Error processing export job {job_id}: {e}", exc_info=True)

        # Update job status to failed
        job_key = f"yt:export:job:{job_id}"
        await redis.hset(job_key, "status", "failed")  # type: ignore[misc]
        await redis.hset(job_key, "error", str(e))  # type: ignore[misc]

        return False


async def cleanup_expired_exports(redis: Redis) -> None:
    """
    Clean up expired export files from storage.

    Scans Redis for completed export jobs and deletes files older than TTL.
    """
    settings = get_settings()
    storage = get_storage_backend(settings)
    ttl_seconds = settings.export_ttl_hours * 3600
    current_time = int(time.time())

    logger.info("Running export cleanup task")

    # Scan for export job keys
    cursor = 0
    deleted_count = 0

    while True:
        cursor, keys = await redis.scan(cursor, match="yt:export:job:*", count=100)

        for key in keys:
            job_data = await redis.hgetall(key)  # type: ignore[misc]

            if not job_data:
                continue

            status = job_data.get(b"status", b"").decode("utf-8")
            completed_at = job_data.get(b"completed_at", b"").decode("utf-8")
            storage_id = job_data.get(b"storage_id", b"").decode("utf-8")

            if status == "completed" and completed_at and storage_id:
                try:
                    completed_timestamp = int(completed_at)
                    age_seconds = current_time - completed_timestamp

                    if age_seconds > ttl_seconds:
                        # Delete from storage
                        if await storage.delete(storage_id):
                            logger.info(f"Deleted expired export: {storage_id}")
                            deleted_count += 1

                        # Delete job from Redis
                        await redis.delete(key)

                except (ValueError, TypeError) as e:
                    logger.error(f"Error parsing timestamp for {key}: {e}")

        if cursor == 0:
            break

    if deleted_count > 0:
        logger.info(f"Cleanup completed. Deleted {deleted_count} expired exports.")


async def worker_loop() -> None:
    """Main worker loop that processes export jobs from Redis queue."""
    settings = get_settings()

    # Initialize Redis
    redis = Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=False,
    )

    logger.info("Export worker started")
    logger.info(f"Storage backend: {settings.export_storage_backend}")
    logger.info(f"Export TTL: {settings.export_ttl_hours} hours")

    cleanup_interval = 3600  # Run cleanup every hour
    last_cleanup = time.time()

    while True:
        try:
            # Check if it's time to run cleanup
            if time.time() - last_cleanup > cleanup_interval:
                await cleanup_expired_exports(redis)
                last_cleanup = time.time()

            # Pop job from queue (blocking with 5 second timeout)
            result = await redis.brpop("yt:export:queue", timeout=5)

            if result is None:
                # No job available, continue loop
                continue

            # Extract job_id
            _, job_id_bytes = result
            job_id = job_id_bytes.decode("utf-8")

            logger.info(f"Picked up export job: {job_id}")

            # Process the job
            # Get database session using context manager
            async with get_sessionmaker()() as db:
                success = await process_export_job(job_id, redis, db)

                if success:
                    logger.info(f"Job {job_id} processed successfully")
                else:
                    logger.error(f"Job {job_id} failed")

        except KeyboardInterrupt:
            logger.info("Worker received shutdown signal")
            break
        except Exception as e:
            logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
            # Sleep a bit before retrying to avoid tight loop on persistent errors
            await asyncio.sleep(5)

    await redis.close()
    logger.info("Export worker stopped")


def main():
    """Entry point for the export worker."""
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker shutting down...")


if __name__ == "__main__":
    main()
