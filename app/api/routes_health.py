"""Health check endpoints for the YouTube Feed Aggregator API."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def health_check():
    """
    Health check endpoint.

    Returns:
        A simple status object indicating the service is healthy
    """
    return {"ok": True}


@router.get("/readyz")
async def readiness_check():
    """
    Readiness check endpoint.

    Returns:
        A simple status object indicating the service is ready to serve requests
    """
    return {"ok": True}
