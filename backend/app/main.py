import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import funds, indices, system
from app.core.config import settings
from app.core.database import async_session
from app.data.seed import seed_database
from app.services.scheduler import refresh_all, setup_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed database
    async with async_session() as session:
        await seed_database(session)
    logger.info("Database seeded")

    # Start scheduler — two jobs: indices (fast) and funds (slow)
    scheduler = setup_scheduler(
        async_session,
        index_interval=settings.index_refresh_interval,
        fund_interval=settings.data_refresh_interval,
    )
    scheduler.start()
    logger.info(
        "Scheduler started (indices: %d min, funds: %d min)",
        settings.index_refresh_interval,
        settings.data_refresh_interval,
    )

    # Trigger initial refresh as background task
    asyncio.create_task(refresh_all(async_session))
    logger.info("Initial data refresh triggered")

    yield

    # Shutdown
    scheduler.shutdown()
    logger.info("Scheduler stopped")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(indices.router, prefix="/api")
app.include_router(funds.router, prefix="/api")
app.include_router(system.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
