# Architecture

## Components

```
                     ┌─────────────┐
   staff / legal /   │   frontend   │  React SPA (Vite)
   investigator ────▶│  (nginx in   │
                      │   prod)     │
                      └──────┬──────┘
                             │ /api (reverse-proxied)
                      ┌──────▼──────┐        ┌─────────────┐
   police / court /   │   backend    │◀──────▶│  PostgreSQL │
   FOI / guest ──────▶│  (FastAPI)   │        │  (catalog,  │
   (public /share     │              │        │  audit, ACL)│
   endpoints)         └──────┬───────┘        └─────────────┘
                             │
                      ┌──────▼───────┐
                      │  MinIO (S3)  │  hot + cold buckets
                      └──────────────┘
                             ▲
                      ┌──────┴───────┐
                      │ ffmpeg/OpenCV │  transcode, blur render,
                      │ faster-whisper│  audio mute, watermark burn-in,
                      └───────────────┘  transcription
```

The backend is a single FastAPI service; there's no separate microservice per
requirement area because the RFP's requirement areas are tightly coupled (a
redaction job needs the video catalog, storage, and audit log all in the same
transaction boundary) and splitting them would add deployment complexity
without a corresponding benefit at this scale.

## Data model

See `backend/app/models/`. The central design decision is **immutable
versioning**: a `Video` row is the catalog entry (metadata, status, retention
category); its actual bytes live in one or more `VideoVersion` rows
(`original`, `redacted`, `disclosure`), each an immutable object in storage.
Redaction never mutates a version in place — it downloads the source version,
renders a new file, and uploads it as a new version linked back to the
`RedactionJob` that produced it. This is what makes "reopen previous
versions", "correct previous redactions", and "republish updated copies" (RFP
§6) possible without extra bookkeeping: the history is just the version
table's `parent_version_id` chain.

Every mutating route calls `audit_service.log()`, writing an append-only
`AuditLog` row. `GET /audit/videos/{id}/chain-of-custody` is just a filtered,
chronological read of that table — there's no separate audit subsystem to
keep in sync.

## Video pipeline

- **Decoders** (`app/decoders/`): a `VideoDecoder` interface with two
  implementations. `FfmpegDecoder` handles MP4/AVI/MKV/MPEG-4 for real.
  `ProprietaryFormatStub` accepts CME/G64x files (so ingestion never rejects
  or loses evidence) but can't decode them — it documents exactly which
  vendor SDK would be needed.
- **Connectors** (`app/connectors/`): a `VMSConnector` interface for pulling
  footage from a VMS. `MockVMSConnector` actually works (it synthesizes a
  short clip with a burned-in timestamp via ffmpeg, standing in for a real
  camera export) so the "automated retrieval" flow is exercised end to end in
  tests and demos. The five real vendor connectors are stubs that raise
  `NotImplementedError` with a docstring describing the real integration
  (auth flow, API calls, retention-lock mechanism) — see each file.
- **Redaction** (`app/services/redaction_service.py`,
  `redaction_geometry.py`): face detection via OpenCV's Haar cascade,
  auto-tracking via a CSRT tracker seeded from one user click, and rendering
  via a frame-by-frame OpenCV pass that Gaussian-blurs active regions while
  masking out a reserved "timestamp overlay" zone so burned-in timestamps
  survive redaction (RFP: "preserve visible timestamps during redaction").
  Audio muting and transcript-based redaction both reduce to the same
  `mute_audio_only`/`mux_with_audio_redaction` ffmpeg step, driven by a list
  of `[start, end]` ranges (transcript redaction just derives that list from
  segments the user marked redacted).
- **Storage tiering** (`app/services/storage_service.py`,
  `retention_service.py`): "hot" and "cold" are two buckets; archiving is a
  copy+delete between them. The 24-hour restore SLA is recorded (a
  `StorageTierEvent.restore_eta` timestamp) but performed immediately in this
  demo rather than backed by a real archival tier with actual retrieval
  latency.

## Auth & permissions

JWT bearer tokens (`app/security.py`). Folder-level ACLs
(`FolderPermission`) are checked by a single `require_folder_access()`
dependency; `admin` and `staff` roles bypass ACL checks (staff is TTC's
internal baseline role per the RFP's internal/external sharing distinction),
everyone else needs an explicit grant. External share-link recipients never
get an account at all — they hit unauthenticated `/share/{token}/*` routes
scoped to exactly one resource.

One deliberate wrinkle: `<video>`/`<img>` elements can't set an `Authorization`
header, so the JWT dependency also accepts a `?token=` query parameter as a
fallback, used only by the frontend's video player. This is a standard,
narrow exception for media streaming, not a general auth bypass — every other
route still requires the header.

## Background jobs

`app/worker/jobs.py` runs an APScheduler `BackgroundScheduler` inside the API
process (no separate worker deployment) that periodically runs
`retention_service.run_sweep()` — archiving/deleting videos per policy,
respecting legal holds. It's also exposed as `POST /retention/run-sweep` for
demos where waiting hours for the schedule isn't practical. Redaction jobs
themselves run synchronously within the request (`create_redaction_job`
blocks until rendering finishes) rather than through a queue — acceptable for
demo-scale clips; a production deployment with longer footage would want to
move this to a real task queue (Celery/RQ) and return `202 Accepted` with a
pollable job status, which the `RedactionJob.status` field is already shaped
for.

## Reporting / Power BI integration

`app/api/routes/reports.py` exposes plain JSON aggregation endpoints
(inventory, storage utilisation, redaction workload, user/evidence activity,
investigation workload). Power BI can point its Web/JSON connector at these,
or connect directly to the Postgres database for richer modeling — there's no
separate data warehouse or ETL step, since the operational database is small
enough to query directly at this scale.
