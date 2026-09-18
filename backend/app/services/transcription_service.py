"""ASR transcription for the audio-redaction workflow. faster-whisper is
imported lazily and the model is cached across calls since loading it is
the expensive part."""
import uuid
from functools import lru_cache
from pathlib import Path

_MODEL_SIZE = "base"


@lru_cache
def _model():
    from faster_whisper import WhisperModel  # noqa: PLC0415

    return WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")


def transcribe(audio_or_video_path: Path) -> tuple[list[dict], str | None]:
    """Returns (segments, detected_language). Each segment is
    {id, start, end, text, speaker: None, redacted: False} — faster-whisper
    doesn't do speaker diarization, so `speaker` is left for a future
    integration (e.g. pyannote) and defaults to null."""
    model = _model()
    segments_iter, info = model.transcribe(str(audio_or_video_path), vad_filter=True)

    segments = [
        {
            "id": str(uuid.uuid4()),
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
            "speaker": None,
            "redacted": False,
        }
        for seg in segments_iter
    ]
    return segments, getattr(info, "language", None)
