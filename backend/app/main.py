from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import funds, indices, system
from app.core.config import settings

app = FastAPI(title=settings.app_name, version="0.1.0")

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
