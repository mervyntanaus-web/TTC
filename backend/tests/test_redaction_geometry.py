from app.services.redaction_geometry import (
    active_boxes_at,
    build_mute_audio_filter,
    interpolate_box,
    merge_overlapping_segments,
)


def test_interpolate_box_midpoint():
    frames = [
        {"t": 0.0, "x": 0.0, "y": 0.0, "w": 10.0, "h": 10.0},
        {"t": 2.0, "x": 20.0, "y": 0.0, "w": 10.0, "h": 10.0},
    ]
    box = interpolate_box(frames, 1.0)
    assert box["x"] == 10.0


def test_interpolate_box_before_and_after_track():
    frames = [{"t": 5.0, "x": 0.0, "y": 0.0, "w": 10.0, "h": 10.0}]
    assert interpolate_box(frames, 3.0, hold_seconds=1.0) is None
    assert interpolate_box(frames, 4.5, hold_seconds=1.0) is not None
    assert interpolate_box(frames, 5.5, hold_seconds=1.0) is not None
    assert interpolate_box(frames, 7.0, hold_seconds=1.0) is None


def test_active_boxes_at_multiple_tracks():
    tracks = [
        {"frames": [{"t": 0.0, "x": 0, "y": 0, "w": 5, "h": 5}]},
        {"frames": [{"t": 10.0, "x": 50, "y": 50, "w": 5, "h": 5}]},
    ]
    assert len(active_boxes_at(tracks, 0.0)) == 1
    assert len(active_boxes_at(tracks, 100.0)) == 0


def test_build_mute_audio_filter_empty():
    assert build_mute_audio_filter([]) is None


def test_build_mute_audio_filter_generates_between_clauses():
    filt = build_mute_audio_filter([{"start": 1.0, "end": 2.0}, {"start": 5.0, "end": 6.0}])
    assert "between(t,1.0,2.0)" in filt
    assert "between(t,5.0,6.0)" in filt


def test_merge_overlapping_segments():
    merged = merge_overlapping_segments(
        [{"start": 0.0, "end": 2.0}, {"start": 1.5, "end": 3.0}, {"start": 10.0, "end": 11.0}]
    )
    assert merged == [{"start": 0.0, "end": 3.0}, {"start": 10.0, "end": 11.0}]
