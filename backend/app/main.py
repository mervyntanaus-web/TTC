from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    archive,
    audit,
    auth,
    connectors,
    folders,
    ingestion,
    playback,
    redaction,
    reports,
    retention,
    search,
    sharing,
    transcripts,
    watermark,
)
from app.services import storage_service
from app.worker.jobs import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    storage_service.ensure_buckets()
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(
    title="TTC DEMS Video Platform",
    description=(
        "Digital Evidence Management System — video ingestion, storage, search, "
        "playback, redaction, and chain-of-custody for TTC."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(folders.router)
app.include_router(ingestion.router)
app.include_router(connectors.router)
app.include_router(playback.router)
app.include_router(redaction.router)
app.include_router(transcripts.router)
app.include_router(search.router)
app.include_router(sharing.router)
app.include_router(watermark.router)
app.include_router(audit.router)
app.include_router(retention.router)
app.include_router(archive.router)
app.include_router(reports.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
