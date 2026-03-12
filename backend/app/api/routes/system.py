"""System API routes — manual data refresh trigger."""

import logging

from fastapi import APIRouter

router = APIRouter(prefix="/system", tags=["system"])

logger = logging.getLogger(__name__)


@router.post("/refresh")
async def trigger_refresh():
    """Trigger immediate refresh_all(). Return {status, message, summary}."""
    try:
        from app.core.database import async_session
        from app.services.scheduler import refresh_all

        summary = await refresh_all(async_session)
        return {"status": "ok", "message": "Refresh complete", "summary": summary}
    except ImportError:
        logger.warning("Scheduler service not yet available")
        return {
            "status": "error",
            "message": "Scheduler service not yet implemented",
            "summary": None,
        }
    except Exception as e:
        logger.exception("Refresh failed")
        return {"status": "error", "message": str(e), "summary": None}
