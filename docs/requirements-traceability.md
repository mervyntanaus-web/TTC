# RFP Requirements Traceability — Video-Related Capabilities

Status legend: **Full** = working code, covered by tests. **Simulated** =
working code standing in for something that needs real infrastructure/vendor
access not available in this environment. **Stub** = interface/extension
point defined, not implemented (documents exactly what real implementation
needs).

## 1. Video Capture & Ingestion

| Requirement | Implementation | Status |
|---|---|---|
| Accept video uploads | `POST /videos/upload` (`app/api/routes/ingestion.py`) | Full |
| Bulk upload of files | `POST /videos/bulk-upload` | Full |
| Multiple video sources | `app/connectors/` — common `VMSConnector` interface | Full (interface) |
| Storage within investigation folders | Upload requires a `folder_id`; `Video.folder_id` FK | Full |
| Upload at speeds up to 1 Gbps | Streamed multipart upload, no artificial throttling; real throughput is infra-bound (network/disk), not app-bound | Full (no bottleneck introduced) |
| Scalable storage for growing volumes | S3-compatible object storage (MinIO/any S3), horizontally scalable independent of the app | Full |
| MP4, AVI, MKV, MPEG-4 | `app/decoders/ffmpeg_decoder.py` via ffmpeg/ffprobe | Full |
| CME (March Networks) | `app/decoders/proprietary_stub.py` — accepted & catalogued, tagged `needs_vendor_decoder`, not decodable without March Networks' export SDK | Stub |
| G64x (Genetec) | Same as above, needs Genetec's Video Export SDK | Stub |
| Genetec Security Center | `app/connectors/genetec.py` | Stub (documents required Security Center SDK calls) |
| March Networks | `app/connectors/march_networks.py` | Stub |
| Axon | `app/connectors/axon.py` | Stub |
| Teleste | `app/connectors/teleste.py` | Stub |
| Sekurflo | `app/connectors/sekurflo.py` | Stub (no public API docs found; contact vendor) |
| Future consolidated Genetec environment | Same `GenetecConnector`, config-driven per-environment credentials | Stub |
| Mock/demo source | `app/connectors/mock.py` — synthesizes a real, playable clip with a burned-in timestamp | Full |

## 2. Video Storage & Organisation

| Requirement | Implementation | Status |
|---|---|---|
| Video folders / subfolders | `Folder` model, self-referencing `parent_id`; `POST /folders`, `GET /folders/{id}/children` | Full |
| Related folder linking | `Folder.linked_folder_ids` | Full |
| Case structures | `Case` model, `Folder.case_id` | Full |
| Folder metadata / video metadata / custom fields | `Folder.metadata_fields`, `Video.metadata_fields` (JSON, arbitrary keys) | Full |
| Folder-level permissions | `FolderPermission` model, `require_folder_access()` dependency | Full |
| File-level permissions | `FolderPermission` scoped per user/role; file-level override point exists on `Video` if finer granularity is needed later | Full (folder-level); file-level is an extension point |
| Storage lifecycle management | `retention_service.py` (archive/delete sweep) | Full |
| Automatic retention categorisation | `RetentionPolicy.category`, assigned per case/video at creation | Full |

## 3. Video Search & Discovery

| Requirement | Implementation | Status |
|---|---|---|
| Search by metadata | `GET /search/videos?metadata_field=&metadata_value=` | Full |
| Search by keywords | `GET /search/videos?q=` — matches filename, metadata, and transcript text | Full |
| Search across investigations | Omit `case_id`/`folder_id` to search globally | Full |
| Search inside folders | `GET /search/videos?folder_id=` | Full |
| Configurable metadata fields | Metadata is arbitrary JSON, not a fixed schema | Full |
| Retrieval of evidence for requests/investigations | Same search endpoint backs the frontend's Search page | Full |

## 4. Video Playback Requirements

| Requirement | Implementation | Status |
|---|---|---|
| View videos directly within DEMS | `GET /videos/{id}/stream`, frontend `PlayerPage` | Full |
| Play TTC proprietary formats | Blocked on vendor decoders (see §1) — UI clearly flags `needs_vendor_decoder` rather than failing silently | Stub (blocked on vendor SDKs) |
| Display date/time stamps during playback | Mock-ingested footage burns in a timestamp; redaction explicitly preserves a reserved timestamp overlay zone (`redaction_service.DEFAULT_RESERVED_ZONE`) | Full |
| Convert unsupported formats when required | `video_pipeline.ensure_playable_mp4()` transcodes any native format to browser-playable MP4 on demand | Full |
| Review without exporting to external tools | Byte-range streaming with seeking, in-browser `<video>` player | Full |

## 5. Evidence Retrieval Requirements

| Requirement | Implementation | Status |
|---|---|---|
| Automated retrieval after approval | `POST /connectors/{name}/retrieve` — pulls footage, associates it with a case/folder | Full (via `MockVMSConnector`); real vendors are stubs |
| Associate footage with investigation case | `ingest_local_file()` sets `folder_id` on ingest | Full |
| Preserve footage from deletion | Automated retrieval sets `legal_hold=True` automatically; `connector.protect_source_from_deletion()` best-effort protects the source system's copy too | Full (app-side); source-system protection depends on the real connector |
| Manual retrieval (systems not connected) | `POST /videos/upload` associates an uploaded file to a folder/case | Full |
| Preserve chain of custody | Every ingestion path logs to `AuditLog` | Full |

## 6. Video Redaction Requirements

### Core redaction

| Requirement | Implementation | Status |
|---|---|---|
| Redact video directly within DEMS | `POST /videos/{id}/redaction-jobs`, frontend Redaction Studio | Full |
| Redact without removing evidentiary information | Original `VideoVersion` is never modified or deleted; redaction always produces a *new* version | Full |
| Preserve visible timestamps during redaction | Reserved-zone masking in `render_video_blur()` — pixel-verified in `tests/test_redaction.py` | Full |

### Auto tracking

| Requirement | Implementation | Status |
|---|---|---|
| Select individual, system follows, redaction follows | `POST /videos/{id}/auto-track` (CSRT tracker seeded from one click) → track fed into a redaction job | Full |

### Audio redaction

| Requirement | Implementation | Status |
|---|---|---|
| Redact audio | `RedactionType.AUDIO_MUTE`, `mute_audio_only()` | Full |
| Handle video + audio evidence | A single redaction job can carry both `regions` and `audio_segments` | Full |
| Combined audio/video workflows | `run_redaction_job()` renders both in one pass when both are present | Full |

### Transcript-based audio redaction

| Requirement | Implementation | Status |
|---|---|---|
| Create transcript from audio | `POST /videos/{id}/transcript/generate` (faster-whisper) | Full |
| Allow transcript editing/redaction | `PATCH /videos/{id}/transcript/segments/{id}` | Full |
| Auto-apply transcript redactions to audio | `POST /videos/{id}/transcript/apply-redactions` maps redacted segments to mute ranges | Full |

### Version management

| Requirement | Implementation | Status |
|---|---|---|
| Save redaction work | Every job produces a persisted `VideoVersion` | Full |
| Preserve original evidence | Original version is immutable and always retrievable | Full |
| Reopen previous versions | `GET /videos/{id}/redaction-jobs/{job_id}` returns the regions/segments used; frontend's "Reopen / correct" loads them back into the editor | Full |
| Correct previous redactions | Re-submitting a job against the same/earlier source version | Full |
| Republish updated copies | `POST /videos/{id}/versions/{version_id}/publish-disclosure` | Full |

## 7. AI / Automation Requirements

| Requirement | Implementation | Status |
|---|---|---|
| Automated redaction | Face detection + auto-tracking (§6) | Full |
| Auto-tracking of individuals | CSRT tracker (§6) | Full |
| Transcript generation | faster-whisper (§6) | Full |
| (Explicitly out of scope per RFP: facial recognition/ID, license-plate recognition, object detection, behaviour analytics, threat detection, video summarisation) | Not built — correctly out of scope | N/A |

## 8. Video Sharing & Distribution

| Requirement | Implementation | Status |
|---|---|---|
| Internal sharing (staff, investigation teams, legal) | `RecipientType.INTERNAL_STAFF` / `LEGAL_TEAM` | Full |
| External sharing (police, insurance, court, FOI, guest) | `RecipientType.POLICE/INSURANCE/COURT/FOI/GUEST`, unauthenticated `GET /share/{token}/*` | Full |
| View-only access | `ShareScope.VIEW_ONLY` blocks `/share/{token}/download` (403) | Full |
| Download permissions | `ShareScope.DOWNLOAD` | Full |
| Temporary / expiry-based sharing | `ShareLink.expires_at`, checked on every access | Full |
| Folder sharing | `ShareResourceType.FOLDER` (metadata lookup); streaming is currently video-scoped only | Full (metadata); folder content streaming is a straightforward extension |
| File sharing | `ShareResourceType.VIDEO` | Full |

## 9. Watermarking Requirements

| Requirement | Implementation | Status |
|---|---|---|
| User-specific watermarks | `Watermark(scope=USER)`, `PUT /watermarks/me` | Full |
| Watermarking during playback | Template rendering is playback-ready (`enabled_for_playback` flag); burned-in overlay currently applies at disclosure-publish time, not live-decoded playback | Full (export); live playback overlay is a frontend canvas-overlay extension |
| Configurable watermark controls | Template string with `{viewer_name}`/`{viewer_email}`/`{timestamp}`/`{case_name}` placeholders | Full |
| Administrator-controlled watermarks | `Watermark(scope=GLOBAL)`, `PUT /watermarks/global` (admin-only) | Full |
| Security markings identifying the viewer | Burned into every disclosure copy via `watermark_service.burn_in_watermark()`, pixel-verified in tests | Full |

## 10. Chain of Custody & Audit

| Requirement | Implementation | Status |
|---|---|---|
| Every interaction auditable (upload, retrieval, viewing, redaction, sharing, download, retention changes, deletion) | `audit_service.log()` called from every mutating route across ingestion/playback/redaction/sharing/retention | Full |
| Chain of custody reports | `GET /audit/videos/{id}/chain-of-custody` | Full |
| Audit reports | `GET /audit/logs` (filterable) | Full |
| Compliance reports | Same audit log, filterable by action/resource/actor | Full |
| Exportable evidence histories | `GET /audit/export` (CSV) | Full |

## 11. Retention & Lifecycle

| Requirement | Implementation | Status |
|---|---|---|
| Retention by category | `RetentionPolicy.category` | Full |
| Retention by folder / by file | `Video.retention_category` set per video (inheritable from case/folder at creation) | Full |
| Retention overrides | Per-video `retention_category` can differ from its case's default | Full |
| Legal hold capability | `Video.legal_hold`, `POST /videos/{id}/legal-hold` — overrides all other retention rules | Full |
| Automatic retention enforcement | `retention_service.run_sweep()`, scheduled via APScheduler | Full |
| Automatic deletion | Sweep soft-deletes past expiry when `auto_delete=True` | Full |
| Preservation of metadata after deletion | `delete_video()` removes storage objects but keeps the `Video` row (tombstone) with all metadata intact | Full |

## 12. Cold Storage

| Requirement | Implementation | Status |
|---|---|---|
| Archive storage | `StorageTier.COLD` (separate S3 bucket) | Full |
| Cold storage lifecycle | `retention_service.archive_video()`, auto-triggered by `auto_archive_after_days` | Full |
| Automated storage tiering | Sweep job archives eligible videos automatically | Full |
| Retrieval within 24 hours | `POST /videos/{id}/restore` records a `restore_eta` (now + `TTC_COLD_STORAGE_RESTORE_SLA_HOURS`, default 24h) | Simulated (restore completes immediately in this demo; ETA is tracked as it would be for a real tiered store) |
| Archived evidence searchability | Search/catalog queries are storage-tier-agnostic — archived videos remain fully searchable | Full |
| Restoration of archived video | `POST /videos/{id}/restore` moves objects back to hot storage | Full |

## 13. Reporting & Analytics

| Requirement | Implementation | Status |
|---|---|---|
| Video inventory | `GET /reports/inventory` | Full |
| Storage utilisation | `GET /reports/storage-utilization` | Full |
| Redaction workload | `GET /reports/redaction-workload` | Full |
| User activity | `GET /reports/user-activity` | Full |
| Evidence access | `GET /reports/evidence-access` | Full |
| Investigation workload | `GET /reports/investigation-workload` | Full |
| Audit reporting | `GET /audit/logs`, `/audit/export` | Full |
| Chain of custody reporting | `GET /audit/videos/{id}/chain-of-custody` | Full |
| Power BI integration | All `/reports/*` endpoints return plain JSON consumable by Power BI's Web connector; Power BI can also connect directly to the Postgres database | Full (as an integration point; no Power BI workspace configured in this environment) |
