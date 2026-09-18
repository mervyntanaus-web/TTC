"""Pure math/data helpers for the redaction pipeline, kept free of cv2/ffmpeg
dependencies so they're cheap to unit test."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    t: float
    x: float
    y: float
    w: float
    h: float


def interpolate_box(frames: list[dict], t: float, hold_seconds: float = 1.0) -> dict | None:
    """Given a track's recorded keyframes (each {t,x,y,w,h}, sorted or not),
    returns the box active at time `t` by linear interpolation between the
    two nearest keyframes straddling it. If `t` is before the first
    keyframe or after the last by more than `hold_seconds`, returns None
    (the track isn't active at that time). If `t` is within `hold_seconds`
    of the last keyframe, the last box is held rather than interpolated,
    so a track doesn't vanish one frame early."""
    if not frames:
        return None
    ordered = sorted(frames, key=lambda f: f["t"])

    if t <= ordered[0]["t"]:
        return dict(ordered[0]) if t >= ordered[0]["t"] - hold_seconds else None
    if t >= ordered[-1]["t"]:
        return dict(ordered[-1]) if t <= ordered[-1]["t"] + hold_seconds else None

    for prev, nxt in zip(ordered, ordered[1:]):
        if prev["t"] <= t <= nxt["t"]:
            span = nxt["t"] - prev["t"]
            ratio = 0.0 if span == 0 else (t - prev["t"]) / span
            return {
                "t": t,
                "x": prev["x"] + (nxt["x"] - prev["x"]) * ratio,
                "y": prev["y"] + (nxt["y"] - prev["y"]) * ratio,
                "w": prev["w"] + (nxt["w"] - prev["w"]) * ratio,
                "h": prev["h"] + (nxt["h"] - prev["h"]) * ratio,
            }
    return None


def active_boxes_at(tracks: list[dict], t: float, hold_seconds: float = 1.0) -> list[dict]:
    """Returns the interpolated box for every track active at time t."""
    boxes = []
    for track in tracks:
        box = interpolate_box(track.get("frames", []), t, hold_seconds)
        if box:
            boxes.append(box)
    return boxes


def clip_box_to_frame(box: dict, frame_width: int, frame_height: int) -> tuple[int, int, int, int]:
    x = max(0, min(int(box["x"]), frame_width - 1))
    y = max(0, min(int(box["y"]), frame_height - 1))
    w = max(1, min(int(box["w"]), frame_width - x))
    h = max(1, min(int(box["h"]), frame_height - y))
    return x, y, w, h


def build_mute_audio_filter(segments: list[dict]) -> str | None:
    """Builds an ffmpeg `-af` volume filter string that silences the given
    [start,end] second ranges, leaving everything else untouched. Returns
    None if there's nothing to mute."""
    if not segments:
        return None
    parts = []
    for seg in segments:
        start, end = seg["start"], seg["end"]
        if end <= start:
            continue
        parts.append(f"volume=enable='between(t,{start},{end})':volume=0")
    return ",".join(parts) if parts else None


def merge_overlapping_segments(segments: list[dict]) -> list[dict]:
    """Coalesces overlapping/adjacent [start,end] audio-mute ranges so the
    generated ffmpeg filter (and stored audit trail) stays minimal."""
    if not segments:
        return []
    ordered = sorted(segments, key=lambda s: s["start"])
    merged = [dict(ordered[0])]
    for seg in ordered[1:]:
        last = merged[-1]
        if seg["start"] <= last["end"]:
            last["end"] = max(last["end"], seg["end"])
        else:
            merged.append(dict(seg))
    return merged
