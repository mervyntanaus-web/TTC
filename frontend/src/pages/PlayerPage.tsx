import { useEffect, useState, useCallback } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet, apiPost, apiStreamUrl, ApiError } from "../api/client";
import type { RetentionStatus, StorageTierEvent, Video, VideoVersion } from "../api/types";
import Badge from "../components/Badge";

function tokenParam(): Record<string, string> {
  const token = localStorage.getItem("ttc_token");
  return token ? { token } : {};
}

export default function PlayerPage() {
  const { videoId } = useParams<{ videoId: string }>();
  const [video, setVideo] = useState<Video | null>(null);
  const [versions, setVersions] = useState<VideoVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [retention, setRetention] = useState<RetentionStatus | null>(null);
  const [tierEvents, setTierEvents] = useState<StorageTierEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!videoId) return;
    const [v, vv, rs, te] = await Promise.all([
      apiGet<Video>(`/videos/${videoId}`),
      apiGet<VideoVersion[]>(`/videos/${videoId}/versions`),
      apiGet<RetentionStatus>(`/videos/${videoId}/retention-status`),
      apiGet<StorageTierEvent[]>(`/videos/${videoId}/storage-tier-events`),
    ]);
    setVideo(v);
    setVersions(vv);
    setRetention(rs);
    setTierEvents(te);
    if (!selectedVersionId && vv.length > 0) setSelectedVersionId(vv[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]);

  useEffect(() => {
    load().catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [load]);

  async function toggleLegalHold() {
    if (!video) return;
    setBusy(true);
    try {
      await apiPost(`/videos/${video.id}/legal-hold`, { legal_hold: !video.legal_hold });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update legal hold");
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/videos/${videoId}/archive`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Archive failed");
    } finally {
      setBusy(false);
    }
  }

  async function restore() {
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/videos/${videoId}/restore`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Restore failed");
    } finally {
      setBusy(false);
    }
  }

  async function publishDisclosure() {
    if (!selectedVersionId) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/videos/${videoId}/versions/${selectedVersionId}/publish-disclosure`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Publish failed");
    } finally {
      setBusy(false);
    }
  }

  if (!video) return <div>{error || "Loading…"}</div>;

  const streamUrl = apiStreamUrl(`/videos/${video.id}/stream`, {
    ...tokenParam(),
    ...(selectedVersionId ? { version_id: selectedVersionId } : {}),
  });

  return (
    <div>
      <div className="toolbar">
        <Link to="/cases">← Back to cases</Link>
      </div>
      <h2>{video.filename}</h2>
      {error && <div className="error-banner">{error}</div>}

      <div className="grid cols-2">
        <div className="card">
          {video.status === "needs_vendor_decoder" ? (
            <p style={{ color: "var(--warn)" }}>
              This file is in a proprietary vendor format (CME/G64x) and needs a vendor SDK to decode
              before it can be played. It has been safely stored and catalogued in the meantime.
            </p>
          ) : (
            // key forces the <video> element to reload when the version changes
            <video key={streamUrl} className="player" src={streamUrl} controls />
          )}

          <div className="toolbar" style={{ marginTop: 10 }}>
            <label>Version:</label>
            <select value={selectedVersionId ?? ""} onChange={(e) => setSelectedVersionId(e.target.value)}>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.kind} — {new Date(v.created_at).toLocaleString()}
                  {v.watermark_applied ? " (watermarked)" : ""}
                </option>
              ))}
            </select>
          </div>

          <div className="toolbar">
            <Link to={`/videos/${video.id}/redact`}>
              <button>Open Redaction Studio</button>
            </Link>
            <button className="secondary" onClick={publishDisclosure} disabled={busy}>
              Publish disclosure copy
            </button>
            <Link to={`/sharing?video_id=${video.id}`}>
              <button className="secondary">Share…</button>
            </Link>
          </div>
        </div>

        <div className="card">
          <h3>Evidence details</h3>
          <table>
            <tbody>
              <tr><td>Status</td><td><Badge value={video.status} /></td></tr>
              <tr><td>Storage tier</td><td><Badge value={video.storage_tier} /></td></tr>
              <tr><td>Source</td><td>{video.source_connector}{video.camera_id ? ` (${video.camera_id})` : ""}</td></tr>
              <tr><td>Format</td><td>{video.format}</td></tr>
              <tr><td>Size</td><td>{video.size_bytes ? `${(video.size_bytes / 1e6).toFixed(2)} MB` : "—"}</td></tr>
              <tr><td>Checksum (SHA-256)</td><td style={{ fontSize: 11, wordBreak: "break-all" }}>{video.checksum_sha256}</td></tr>
              <tr><td>Captured at</td><td>{video.captured_at ? new Date(video.captured_at).toLocaleString() : "—"}</td></tr>
              <tr><td>Metadata</td><td><code style={{ fontSize: 11 }}>{JSON.stringify(video.metadata_fields)}</code></td></tr>
            </tbody>
          </table>

          <h3 style={{ marginTop: 16 }}>Retention</h3>
          {retention && (
            <table>
              <tbody>
                <tr><td>Category</td><td>{retention.category}</td></tr>
                <tr><td>Expires</td><td>{new Date(retention.expires_at).toLocaleDateString()}</td></tr>
                <tr><td>Legal hold</td><td>{retention.legal_hold ? "Yes" : "No"}</td></tr>
              </tbody>
            </table>
          )}
          <div className="toolbar">
            <button className="secondary" onClick={toggleLegalHold} disabled={busy}>
              {video.legal_hold ? "Lift legal hold" : "Place legal hold"}
            </button>
            {video.storage_tier === "hot" ? (
              <button className="secondary" onClick={archive} disabled={busy}>Archive to cold storage</button>
            ) : (
              <button className="secondary" onClick={restore} disabled={busy}>Restore from archive</button>
            )}
          </div>

          {tierEvents.length > 0 && (
            <>
              <h4>Storage tier history</h4>
              <ul style={{ fontSize: 12, color: "var(--muted)" }}>
                {tierEvents.map((e) => (
                  <li key={e.id}>
                    {new Date(e.moved_at).toLocaleString()} → {e.tier}
                    {e.restore_eta ? ` (SLA: ready by ${new Date(e.restore_eta).toLocaleString()})` : ""}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
