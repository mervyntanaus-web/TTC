from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, connectors, folders, ingestion, playback, redaction, search, transcripts

app = FastAPI(
    title="TTC DEMS Video Platform",
    description=(
        "Digital Evidence Management System — video ingestion, storage, search, "
        "playback, redaction, and chain-of-custody for TTC."
    ),
    version="0.1.0",
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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
