import { useState, type FormEvent } from "react";
import { apiGet, API_BASE } from "../api/client";
import type { AuditLog } from "../api/types";

export default function AuditPage() {
  const [videoId, setVideoId] = useState("");
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [mode, setMode] = useState<"chain" | "all">("all");

  async function loadChainOfCustody(e: FormEvent) {
    e.preventDefault();
    if (!videoId) return;
    setMode("chain");
    setLogs(await apiGet<AuditLog[]>(`/audit/videos/${videoId}/chain-of-custody`));
  }

  async function loadAll() {
    setMode("all");
    setLogs(await apiGet<AuditLog[]>("/audit/logs", { limit: 200 }));
  }

  function exportUrl() {
    const token = localStorage.getItem("ttc_token") ?? "";
    const params = new URLSearchParams({ token });
    if (mode === "chain" && videoId) {
      params.set("resource_type", "video");
      params.set("resource_id", videoId);
    }
    return `${API_BASE}/audit/export?${params.toString()}`;
  }

  return (
    <div>
      <h2>Chain of Custody &amp; Audit</h2>

      <div className="card">
        <div className="toolbar">
          <form onSubmit={loadChainOfCustody} className="toolbar">
            <input placeholder="Video ID" value={videoId} onChange={(e) => setVideoId(e.target.value)} />
            <button type="submit">Load chain of custody</button>
          </form>
          <button className="secondary" onClick={loadAll}>Show recent activity (all)</button>
          <a href={exportUrl()} target="_blank" rel="noreferrer">
            <button className="secondary">Export CSV</button>
          </a>
        </div>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr><th>Timestamp</th><th>Actor</th><th>Action</th><th>Resource</th><th>Details</th></tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id}>
                <td>{new Date(l.timestamp).toLocaleString()}</td>
                <td>{l.actor_label || "system"}</td>
                <td>{l.action}</td>
                <td>{l.resource_type}{l.resource_id ? ` (${l.resource_id.slice(0, 8)}…)` : ""}</td>
                <td style={{ fontSize: 11 }}>{JSON.stringify(l.details)}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr><td colSpan={5} style={{ color: "var(--muted)" }}>No entries loaded yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
