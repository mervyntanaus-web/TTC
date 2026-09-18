# Demo Script: the full evidence lifecycle

Walks the RFP's own workflow end to end:

```
Request → Retrieve → Store → Organise → Review → Generate Transcript →
Redact Video → Redact Audio → Track Redactions → Create Disclosure Copy →
Apply Watermark → Share Securely → Track Chain of Custody → Archive →
Retrieve → Dispose
```

Prerequisites: `docker compose up --build`, then `docker compose run --rm
seed`. Log in at http://localhost:5173 as `staff@ttc.demo` /
`demo-password-123`.

## 1. Request → Retrieve (automated)

A request for footage from a connected camera, after approval, is an
automated retrieval:

```bash
curl -X POST http://localhost:8000/connectors/mock_vms/retrieve \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"camera_id": "MOCK-CAM-01", "start": "2026-09-18T08:00:00Z",
       "end": "2026-09-18T08:00:30Z", "folder_id": "'"$FOLDER_ID"'"}'
```

This synthesizes a clip (standing in for a real camera export), stores it,
associates it with the folder/case, sets `legal_hold=true` to preserve it,
and logs `video.retrieve.automated` to the audit trail — all in one call.

## 2. Store → Organise (UI: Cases & Evidence)

In the UI, create a case, add nested folders ("Evidence" → "Platform CCTV"),
and either use the auto-retrieved clip above or manually upload one (also
covers the RFP's "manual retrieval where systems aren't connected" path —
bulk upload works the same way with multiple files selected).

## 3. Review (UI: video player)

Click the video to open the player. It streams with seeking (byte-range
requests), shows all catalog metadata, checksum, retention status, and
storage tier.

## 4. Generate Transcript → Redact Audio (UI: Redaction Studio → Transcript panel)

Click "Open Redaction Studio", then "Generate transcript". Once segments
appear, tick the ones to redact and click "Apply transcript redactions to
audio" — this creates a `transcript_based_audio` redaction job that mutes
exactly those time ranges.

## 5. Redact Video → Track Redactions (UI: Redaction Studio → canvas)

Pause the video, drag a box over a face. Either:
- **"Apply box to entire clip"** for a static region (e.g. a fixed camera
  overlay), or
- **"Auto-track N seconds from here"** to let a CSRT tracker follow the
  person for the given duration.

Click "Run redaction job". The result is a new, immutable `VideoVersion`
whose region is blurred (and audio muted, if segments were also added) —
verify by switching the player's "Version" dropdown between `original` and
`redacted`.

## 6. Create Disclosure Copy → Apply Watermark

As an admin, set a global watermark template once:

```bash
curl -X PUT http://localhost:8000/watermarks/global \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"template": "{viewer_name} • {timestamp}", "enabled_for_playback": true, "enabled_for_export": true}'
```

Back in the player, click "Publish disclosure copy" — this burns the
watermark into a new `disclosure` version, ready to hand off externally.

## 7. Share Securely (UI: Sharing)

Create a share link scoped to the disclosure copy: pick a recipient type
(police/insurance/court/FOI/guest), view-only or download, and an expiry.
The resulting `/share/{token}/stream` URL works with no TTC login — open it
in a private browser window to confirm.

## 8. Track Chain of Custody (UI: Chain of Custody)

Load the video's chain of custody: every step above — retrieval, view,
redaction, disclosure publish, share creation, and the external party's
access — appears in order, exportable as CSV.

## 9. Archive → Retrieve (UI: player page retention controls)

Click "Archive to cold storage" (moves the object to the cold bucket,
records a `StorageTierEvent`), then "Restore from archive" (records a
24-hour SLA ETA, completes immediately in this demo). The video remains
streamable throughout — try it right after archiving.

## 10. Dispose

Set a short retention policy and either wait for the scheduled sweep or
trigger it manually as an admin:

```bash
curl -X PUT http://localhost:8000/retention-policies \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"category": "demo_short", "retention_days": 0, "auto_delete": true}'
# set the video's retention_category to "demo_short" first, then:
curl -X POST http://localhost:8000/retention/run-sweep -H "Authorization: Bearer $ADMIN_TOKEN"
```

The video's status flips to `deleted` and its storage objects are removed —
but its catalog row, metadata, and full audit trail remain, satisfying
"preservation of metadata after deletion". Note a video under `legal_hold`
(like the one auto-retrieved in step 1) is never touched by the sweep,
regardless of its retention category.
