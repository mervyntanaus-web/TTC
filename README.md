# TTC Digital Evidence Management System (DEMS)

A working prototype of the video-related capabilities described in the TTC DEMS
RFP: ingestion from CCTV/VMS systems, organised storage, search, in-platform
playback, video/audio redaction (including auto-tracking and transcript-based
audio redaction), version management, sharing with external parties,
watermarking, chain-of-custody auditing, retention/legal-hold lifecycle
management, cold-storage archival, and reporting.

See [`docs/requirements-traceability.md`](docs/requirements-traceability.md)
for a line-by-line mapping of every RFP requirement to the code that
implements it, and what's genuinely working versus simulated/stubbed pending
real vendor access. See [`docs/architecture.md`](docs/architecture.md) for the
system design and key decisions. See
[`docs/demo-script.md`](docs/demo-script.md) for a walkthrough of the full
Request → Dispose evidence lifecycle.

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL.
- **Video processing**: ffmpeg (transcode, blur rendering, audio muting,
  watermark burn-in), OpenCV (face detection, CSRT auto-tracking),
  faster-whisper (transcription).
- **Storage**: S3-compatible object storage (MinIO in this stack) with
  simulated hot/cold tiering.
- **Frontend**: React + TypeScript + Vite.
- **Auth**: JWT, role-based (admin / staff / legal / investigator / external).

## Quickstart (Docker)

```bash
docker compose up --build
```

- Backend API + docs: http://localhost:8000/docs
- Frontend: http://localhost:5173
- MinIO console: http://localhost:9001 (user `ttc-admin`, password
  `ttc-admin-secret`)

Seed demo data (users, a demo case, folders) once the stack is up:

```bash
docker compose run --rm seed
```

Log in at http://localhost:5173 with `staff@ttc.demo` /
`demo-password-123` (see `seed/seed_data.py` for all seeded accounts and
their roles).

## Running without Docker

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export TTC_DATABASE_URL=postgresql+psycopg2://ttc:ttc@localhost:5432/ttc
export TTC_S3_ENDPOINT_URL=http://localhost:9000
export TTC_S3_ACCESS_KEY=ttc-admin
export TTC_S3_SECRET_KEY=ttc-admin-secret
alembic upgrade head
uvicorn app.main:app --reload
```

You'll need a Postgres instance and an S3-compatible store (MinIO, or even
[moto's mock S3 server](https://github.com/getmoto/moto) for local
experimentation) reachable at those URLs. `ffmpeg` must be installed and on
`PATH`. Then, from the repo root: `python -m seed.seed_data`.

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_PROXY_TARGET` (see `frontend/.env.example`) if your backend
isn't on `http://localhost:8000`.

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

The suite exercises the real ffmpeg/OpenCV pipeline (pixel-verified video
blurring, silence-detection-verified audio muting, byte-range streaming, CSRT
auto-tracking) against a local fake object store standing in for MinIO/S3, so
no external services are required to run it.

## Project layout

```
backend/     FastAPI app: models, routes, services (video pipeline,
             redaction, storage, retention, watermark, sharing), Alembic
             migrations, tests
frontend/    React SPA: case/folder browser, player, redaction studio,
             sharing, audit, retention, reports
seed/        Demo data seeder (users, case, folders, retention policies)
docs/        Architecture notes, RFP requirements-traceability matrix,
             demo script
```

## What's simulated vs. real

Real vendor systems (Genetec, March Networks, Axon, Teleste, Sekurflo) and
their proprietary export formats (CME, G64x) aren't accessible in this
environment. The connector and decoder interfaces are built to plug real
implementations in later; a working `MockVMSConnector` and real ffmpeg
decoding for MP4/AVI/MKV/MPEG-4 stand in for now. Cold-storage tiering and
the 24-hour restore SLA are simulated (instant copy between two buckets,
timestamped) rather than backed by a real archival tier. Everything else —
ingestion, organisation, search, playback, redaction (video and audio),
transcript-based redaction, versioning, sharing, watermarking, audit/chain of
custody, and retention lifecycle logic — is fully working code, covered by
tests that exercise the real ffmpeg/OpenCV pipeline. Full detail in
[`docs/requirements-traceability.md`](docs/requirements-traceability.md).
