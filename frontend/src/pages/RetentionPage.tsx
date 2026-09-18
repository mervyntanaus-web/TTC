import { useEffect, useState, type FormEvent } from "react";
import { apiGet, apiPost, apiPut, ApiError } from "../api/client";
import type { RetentionPolicy } from "../api/types";

export default function RetentionPage() {
  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [category, setCategory] = useState("");
  const [retentionDays, setRetentionDays] = useState(365);
  const [autoDelete, setAutoDelete] = useState(false);
  const [autoArchiveAfterDays, setAutoArchiveAfterDays] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);
  const [sweepResult, setSweepResult] = useState<{ archived: string[]; deleted: string[] } | null>(null);

  useEffect(() => {
    refresh();
  }, []);

  function refresh() {
    apiGet<RetentionPolicy[]>("/retention-policies").then(setPolicies);
  }

  async function upsert(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await apiPut("/retention-policies", {
        category,
        retention_days: retentionDays,
        auto_delete: autoDelete,
        auto_archive_after_days: autoArchiveAfterDays === "" ? null : Number(autoArchiveAfterDays),
      });
      setCategory("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save policy (requires admin)");
    }
  }

  async function runSweep() {
    setError(null);
    try {
      setSweepResult(await apiPost("/retention/run-sweep"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sweep failed (requires admin)");
    }
  }

  return (
    <div>
      <h2>Retention &amp; Lifecycle</h2>
      {error && <div className="error-banner">{error}</div>}

      <div className="grid cols-2">
        <div className="card">
          <h3>Retention policies</h3>
          <table>
            <thead>
              <tr><th>Category</th><th>Retain (days)</th><th>Auto-delete</th><th>Auto-archive after</th></tr>
            </thead>
            <tbody>
              {policies.map((p) => (
                <tr key={p.id}>
                  <td>{p.category}</td>
                  <td>{p.retention_days}</td>
                  <td>{p.auto_delete ? "Yes" : "No"}</td>
                  <td>{p.auto_archive_after_days ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h4>Create / update policy (admin only)</h4>
          <form onSubmit={upsert}>
            <div className="field">
              <label>Category</label>
              <input value={category} onChange={(e) => setCategory(e.target.value)} required />
            </div>
            <div className="field">
              <label>Retention days</label>
              <input type="number" value={retentionDays} onChange={(e) => setRetentionDays(Number(e.target.value))} />
            </div>
            <div className="field">
              <label>Auto-archive after (days, optional)</label>
              <input
                type="number"
                value={autoArchiveAfterDays}
                onChange={(e) => setAutoArchiveAfterDays(e.target.value === "" ? "" : Number(e.target.value))}
              />
            </div>
            <div className="field">
              <label>
                <input type="checkbox" checked={autoDelete} onChange={(e) => setAutoDelete(e.target.checked)} /> Auto-delete on
                expiry
              </label>
            </div>
            <button type="submit">Save policy</button>
          </form>
        </div>

        <div className="card">
          <h3>Lifecycle sweep</h3>
          <p style={{ color: "var(--muted)", fontSize: 13 }}>
            Runs automatically every few hours in the background. Trigger it manually here for a demo
            instead of waiting.
          </p>
          <button onClick={runSweep}>Run sweep now (admin only)</button>
          {sweepResult && (
            <div style={{ marginTop: 12, fontSize: 13 }}>
              <div>Archived: {sweepResult.archived.length}</div>
              <div>Deleted: {sweepResult.deleted.length}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
