import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.user import User
from app.models.watermark import Watermark, WatermarkScope

settings = get_settings()


def get_effective_watermark(db: Session, user: User | None) -> Watermark | None:
    """A user-specific watermark (if configured) overrides the global one,
    per the RFP's "user-specific watermarks" + "administrator-controlled
    watermarks" requirements."""
    if user:
        user_wm = (
            db.query(Watermark)
            .filter(Watermark.scope == WatermarkScope.USER, Watermark.user_id == user.id)
            .first()
        )
        if user_wm:
            return user_wm
    return db.query(Watermark).filter(Watermark.scope == WatermarkScope.GLOBAL).first()


def render_template(template: str, *, viewer_name: str, viewer_email: str, case_name: str = "") -> str:
    return template.format(
        viewer_name=viewer_name,
        viewer_email=viewer_email,
        timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        case_name=case_name,
    )


def _escape_drawtext(text: str) -> str:
    # ffmpeg drawtext treats : and ' as special; escape for literal display.
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def burn_in_watermark(source_path: Path, dest_path: Path, text: str) -> None:
    """Burns a semi-transparent, bottom-right text overlay into the video —
    the "security marking identifying the viewer" that travels with any
    exported/disclosure copy, independent of the player used to view it."""
    escaped = _escape_drawtext(text)
    drawtext = (
        f"drawtext=text='{escaped}':fontcolor=white@0.85:fontsize=16:"
        "box=1:boxcolor=black@0.4:boxborderw=6:x=w-tw-12:y=h-th-12"
    )
    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-i",
        str(source_path),
        "-vf",
        drawtext,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-c:a",
        "copy",
        str(dest_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
