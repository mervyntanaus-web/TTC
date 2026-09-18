import copy
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.redaction import RedactionJob, RedactionType
from app.models.transcript import Transcript
from app.models.user import User
from app.models.video import Video, VideoVersion
from app.schemas.transcript import GenerateTranscriptRequest, TranscriptOut, TranscriptSegmentUpdate
from app.security import get_current_user
from app.services import redaction_service, storage_service, transcription_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/videos/{video_id}/transcript", tags=["transcripts"])


def _get_video(db: Session, video_id: uuid.UUID) -> Video:
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


def _get_transcript_or_404(db: Session, video_id: uuid.UUID) -> Transcript:
    transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="No transcript generated for this video yet")
    return transcript


@router.post("/generate", response_model=TranscriptOut, status_code=status.HTTP_201_CREATED)
def generate_transcript(
    video_id: uuid.UUID,
    payload: GenerateTranscriptRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Transcript:
    """Runs ASR over a version's audio track to produce a timestamped
    transcript, which the redaction UI then lets staff edit/redact
    line-by-line before mapping redactions back onto the audio."""
    video = _get_video(db, video_id)
    version = db.get(VideoVersion, payload.version_id)
    if not version or version.video_id != video.id:
        raise HTTPException(status_code=404, detail="Video version not found for this video")

    with tempfile.TemporaryDirectory() as tmp:
        ext = Path(version.storage_key).suffix or ".mp4"
        local_path = Path(tmp) / f"source{ext}"
        storage_service.download_to_path(version.storage_tier, version.storage_key, str(local_path))
        segments, language = transcription_service.transcribe(local_path)

    transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
    if transcript:
        transcript.segments = segments
        transcript.language = language
        transcript.edited = False
    else:
        transcript = Transcript(video_id=video_id, segments=segments, language=language)
        db.add(transcript)
    db.commit()
    db.refresh(transcript)

    log_action(
        db, user, "transcript.generate", "video", video_id,
        {"segment_count": len(segments), "language": language},
    )
    return transcript


@router.get("", response_model=TranscriptOut)
def get_transcript(video_id: uuid.UUID, db: Session = Depends(get_db)) -> Transcript:
    return _get_transcript_or_404(db, video_id)


@router.patch("/segments/{segment_id}", response_model=TranscriptOut)
def update_segment(
    video_id: uuid.UUID,
    segment_id: str,
    payload: TranscriptSegmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Transcript:
    """Edits or marks a single transcript segment as redacted. This is the
    "allow transcript editing/redaction" step of transcript-based audio
    redaction."""
    transcript = _get_transcript_or_404(db, video_id)
    # A shallow copy would share dict references with transcript.segments;
    # mutating those in place makes the "old" and "new" values compare
    # equal by the time we reassign, and SQLAlchemy silently skips the
    # UPDATE. Deep-copy so the reassignment is a genuine, detectable change.
    segments = copy.deepcopy(transcript.segments)
    updated = False
    for seg in segments:
        if seg["id"] == segment_id:
            if payload.text is not None:
                seg["text"] = payload.text
            if payload.redacted is not None:
                seg["redacted"] = payload.redacted
            updated = True
            break
    if not updated:
        raise HTTPException(status_code=404, detail="Segment not found")

    transcript.segments = segments
    transcript.edited = True
    db.commit()
    db.refresh(transcript)
    log_action(
        db, user, "transcript.segment.edit", "video", video_id,
        {"segment_id": segment_id, **payload.model_dump(exclude_unset=True)},
    )
    return transcript


@router.post("/apply-redactions", status_code=status.HTTP_201_CREATED)
def apply_transcript_redactions(
    video_id: uuid.UUID,
    source_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """"Automatically apply transcript redactions to corresponding audio
    segments": collects every segment marked `redacted` and mutes those
    time ranges in the audio, producing a new VideoVersion."""
    video = _get_video(db, video_id)
    transcript = _get_transcript_or_404(db, video_id)
    source_version = db.get(VideoVersion, source_version_id)
    if not source_version or source_version.video_id != video.id:
        raise HTTPException(status_code=404, detail="Video version not found for this video")

    audio_segments = [
        {"start": seg["start"], "end": seg["end"], "reason": "transcript_redaction"}
        for seg in transcript.segments
        if seg.get("redacted")
    ]
    if not audio_segments:
        raise HTTPException(status_code=400, detail="No transcript segments are marked redacted")

    job = RedactionJob(
        video_id=video.id,
        source_version_id=source_version.id,
        type=RedactionType.TRANSCRIPT_BASED_AUDIO,
        regions=[],
        audio_segments=audio_segments,
        created_by=user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        result_version = redaction_service.run_redaction_job(db, job, video, source_version)
    except redaction_service.RedactionRenderError as exc:
        raise HTTPException(status_code=500, detail=f"Redaction render failed: {exc}") from exc

    log_action(
        db, user, "transcript.apply_redactions", "video", video.id,
        {"job_id": str(job.id), "segments_redacted": len(audio_segments)},
    )
    return {"job_id": str(job.id), "result_version_id": str(result_version.id)}
