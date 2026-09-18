import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet, apiPatch, apiPost, apiStreamUrl, ApiError } from "../api/client";
import type {
  AudioSegment,
  RedactionJob,
  RedactionType,
  RegionTrack,
  Transcript,
  Video,
  VideoVersion,
} from "../api/types";
import Badge from "../components/Badge";

function tokenParam(): Record<string, string> {
  const token = localStorage.getItem("ttc_token");
  return token ? { token } : {};
}

interface Box { x: number; y: number; w: number; h: number }

export default function RedactionStudio() {
  const { videoId } = useParams<{ videoId: string }>();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [video, setVideo] = useState<Video | null>(null);
  const [versions, setVersions] = useState<VideoVersion[]>([]);
  const [sourceVersionId, setSourceVersionId] = useState<string>("");
  const [jobs, setJobs] = useState<RedactionJob[]>([]);
  const [transcript, setTranscript] = useState<Transcript | null>(null);

  const [drawing, setDrawing] = useState<Box | null>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [pendingTracks, setPendingTracks] = useState<RegionTrack[]>([]);
  const [audioSegments, setAudioSegments] = useState<AudioSegment[]>([]);
  const [segmentStart, setSegmentStart] = useState<number | null>(null);
  const [jobType, setJobType] = useState<RedactionType>("manual_region");
  const [trackSeconds, setTrackSeconds] = useState(3);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!videoId) return;
    apiGet<Video>(`/videos/${videoId}`).then(setVideo);
    apiGet<VideoVersion[]>(`/videos/${videoId}/versions`).then((vv) => {
      setVersions(vv);
      const original = vv.find((v) => v.kind === "original");
      setSourceVersionId(original?.id ?? vv[0]?.id ?? "");
    });
    refreshJobs();
    apiGet<Transcript>(`/videos/${videoId}/transcript`).then(setTranscript).catch(() => setTranscript(null));
  }, [videoId]);

  function refreshJobs() {
    if (!videoId) return;
    apiGet<RedactionJob[]>(`/videos/${videoId}/redaction-jobs`).then(setJobs);
  }

  function canvasScale() {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return { x: 1, y: 1 };
    return { x: v.videoWidth / v.clientWidth, y: v.videoHeight / v.clientHeight };
  }

  function onCanvasMouseDown(e: ReactMouseEvent<HTMLCanvasElement>) {
    const rect = canvasRef.current!.getBoundingClientRect();
    setDragStart({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    setDrawing(null);
  }

  function onCanvasMouseMove(e: ReactMouseEvent<HTMLCanvasElement>) {
    if (!dragStart) return;
    const rect = canvasRef.current!.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setDrawing({
      x: Math.min(dragStart.x, x),
      y: Math.min(dragStart.y, y),
      w: Math.abs(x - dragStart.x),
      h: Math.abs(y - dragStart.y),
    });
  }

  function onCanvasMouseUp() {
    setDragStart(null);
  }

  useEffect(() => {
    const canvas = canvasRef.current;
    const v = videoRef.current;
    if (!canvas || !v) return;
    canvas.width = v.clientWidth;
    canvas.height = v.clientHeight;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2;
    if (drawing) ctx.strokeRect(drawing.x, drawing.y, drawing.w, drawing.h);
  }, [drawing]);

  function nativeBox(box: Box): Box {
    const scale = canvasScale();
    return { x: box.x * scale.x, y: box.y * scale.y, w: box.w * scale.x, h: box.h * scale.y };
  }

  function addManualWholeClipTrack() {
    if (!drawing || !video?.duration_seconds) return;
    const b = nativeBox(drawing);
    const track: RegionTrack = {
      track_id: crypto.randomUUID(),
      label: `manual-${pendingTracks.length + 1}`,
      frames: [
        { t: 0, ...b },
        { t: video.duration_seconds, ...b },
      ],
    };
    setPendingTracks((prev) => [...prev, track]);
    setDrawing(null);
  }

  async function autoTrackFromDrawing() {
    if (!drawing || !videoRef.current || !sourceVersionId) return;
    setBusy(true);
    setError(null);
    try {
      const b = nativeBox(drawing);
      const track = await apiPost<RegionTrack>(`/videos/${videoId}/auto-track`, {
        version_id: sourceVersionId,
        start_t: videoRef.current.currentTime,
        x: b.x,
        y: b.y,
        w: b.w,
        h: b.h,
        label: `person-${pendingTracks.length + 1}`,
        max_seconds: trackSeconds,
      });
      setPendingTracks((prev) => [...prev, track]);
      setDrawing(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Auto-track failed");
    } finally {
      setBusy(false);
    }
  }

  function removeTrack(trackId: string) {
    setPendingTracks((prev) => prev.filter((t) => t.track_id !== trackId));
  }

  function markSegmentStart() {
    if (videoRef.current) setSegmentStart(videoRef.current.currentTime);
  }

  function markSegmentEnd() {
    if (videoRef.current && segmentStart !== null) {
      setAudioSegments((prev) => [...prev, { start: segmentStart, end: videoRef.current!.currentTime, reason: "manual" }]);
      setSegmentStart(null);
    }
  }

  async function runRedactionJob() {
    if (!sourceVersionId) return;
    setBusy(true);
    setError(null);
    try {
      const job = await apiPost<RedactionJob>(`/videos/${videoId}/redaction-jobs`, {
        video_id: videoId,
        source_version_id: sourceVersionId,
        type: jobType,
        regions: pendingTracks,
        audio_segments: audioSegments,
      });
      setJobs((prev) => [job, ...prev]);
      setPendingTracks([]);
      setAudioSegments([]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Redaction job failed");
    } finally {
      setBusy(false);
    }
  }

  async function generateTranscript() {
    setBusy(true);
    setError(null);
    try {
      const t = await apiPost<Transcript>(`/videos/${videoId}/transcript/generate`, { version_id: sourceVersionId });
      setTranscript(t);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Transcript generation failed (is Whisper installed?)");
    } finally {
      setBusy(false);
    }
  }

  async function toggleSegmentRedacted(segmentId: string, redacted: boolean) {
    const t = await apiPatch<Transcript>(`/videos/${videoId}/transcript/segments/${segmentId}`, { redacted });
    setTranscript(t);
  }

  async function applyTranscriptRedactions() {
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/videos/${videoId}/transcript/apply-redactions`, undefined, { source_version_id: sourceVersionId });
      refreshJobs();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to apply transcript redactions");
    } finally {
      setBusy(false);
    }
  }

  function reopenJob(job: RedactionJob) {
    setSourceVersionId(job.source_version_id);
    setPendingTracks(job.regions);
    setAudioSegments(job.audio_segments);
    setJobType(job.type);
  }

  if (!video) return <div>Loading…</div>;

  const streamUrl = apiStreamUrl(`/videos/${video.id}/stream`, { ...tokenParam(), version_id: sourceVersionId });

  return (
    <div>
      <div className="toolbar">
        <Link to={`/videos/${video.id}`}>← Back to evidence</Link>
      </div>
      <h2>Redaction Studio — {video.filename}</h2>
      {error && <div className="error-banner">{error}</div>}

      <div className="grid cols-2">
        <div className="card">
          <div className="field">
            <label>Source version (draw against / correct from)</label>
            <select value={sourceVersionId} onChange={(e) => setSourceVersionId(e.target.value)}>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.kind} — {new Date(v.created_at).toLocaleString()}
                </option>
              ))}
            </select>
          </div>

          <div className="redaction-canvas-wrap">
            <video key={streamUrl} ref={videoRef} className="player" src={streamUrl} controls />
            <canvas
              ref={canvasRef}
              onMouseDown={onCanvasMouseDown}
              onMouseMove={onCanvasMouseMove}
              onMouseUp={onCanvasMouseUp}
            />
          </div>
          <p style={{ fontSize: 12, color: "var(--muted)" }}>
            Pause the video, drag a box over a face or region, then choose an action below.
          </p>
          <div className="toolbar">
            <button onClick={addManualWholeClipTrack} disabled={!drawing}>
              Apply box to entire clip
            </button>
            <button onClick={autoTrackFromDrawing} disabled={!drawing || busy} className="secondary">
              Auto-track {trackSeconds}s from here
            </button>
            <input
              type="number"
              min={1}
              style={{ width: 60 }}
              value={trackSeconds}
              onChange={(e) => setTrackSeconds(Number(e.target.value))}
            />
          </div>

          <h4>Pending regions ({pendingTracks.length})</h4>
          <div className="track-list">
            {pendingTracks.map((t) => (
              <div key={t.track_id} className="track-item">
                <span>{t.label} — {t.frames.length} keyframe(s)</span>
                <button className="danger" onClick={() => removeTrack(t.track_id)}>Remove</button>
              </div>
            ))}
            {pendingTracks.length === 0 && <p style={{ color: "var(--muted)" }}>No regions drawn yet.</p>}
          </div>

          <h4>Audio mute segments</h4>
          <div className="toolbar">
            <button className="secondary" onClick={markSegmentStart}>Mark start (at playhead)</button>
            <button className="secondary" onClick={markSegmentEnd} disabled={segmentStart === null}>
              Mark end
            </button>
            {segmentStart !== null && <span>Start marked at {segmentStart.toFixed(1)}s…</span>}
          </div>
          <ul style={{ fontSize: 13 }}>
            {audioSegments.map((s, i) => (
              <li key={i}>{s.start.toFixed(1)}s – {s.end.toFixed(1)}s</li>
            ))}
          </ul>

          <div className="field">
            <label>Redaction job type</label>
            <select value={jobType} onChange={(e) => setJobType(e.target.value as RedactionType)}>
              <option value="manual_region">Manual region (visual blur)</option>
              <option value="face_tracked">Face tracked (auto-tracked visual blur)</option>
              <option value="audio_mute">Audio mute only</option>
            </select>
          </div>
          <button
            onClick={runRedactionJob}
            disabled={busy || (pendingTracks.length === 0 && audioSegments.length === 0)}
          >
            {busy ? "Rendering…" : "Run redaction job"}
          </button>
        </div>

        <div className="card">
          <h3>Transcript &amp; audio redaction</h3>
          {!transcript ? (
            <button onClick={generateTranscript} disabled={busy}>Generate transcript</button>
          ) : (
            <>
              <div style={{ maxHeight: 300, overflowY: "auto" }}>
                {transcript.segments.map((seg) => (
                  <div key={seg.id} className={`transcript-segment ${seg.redacted ? "redacted" : ""}`}>
                    <span className="ts">{seg.start.toFixed(1)}s–{seg.end.toFixed(1)}s</span>
                    <span style={{ flex: 1 }}>{seg.text}</span>
                    <input
                      type="checkbox"
                      checked={seg.redacted}
                      onChange={(e) => toggleSegmentRedacted(seg.id, e.target.checked)}
                      title="Redact this segment"
                    />
                  </div>
                ))}
              </div>
              <button style={{ marginTop: 10 }} onClick={applyTranscriptRedactions} disabled={busy}>
                Apply transcript redactions to audio
              </button>
            </>
          )}

          <h3 style={{ marginTop: 20 }}>Redaction job history</h3>
          <table>
            <thead>
              <tr><th>Type</th><th>Status</th><th>Result</th><th></th></tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>{j.type}</td>
                  <td><Badge value={j.status} /></td>
                  <td>{j.result_version_id ? "new version" : "—"}</td>
                  <td><button className="secondary" onClick={() => reopenJob(j)}>Reopen / correct</button></td>
                </tr>
              ))}
              {jobs.length === 0 && (
                <tr><td colSpan={4} style={{ color: "var(--muted)" }}>No redaction jobs yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
