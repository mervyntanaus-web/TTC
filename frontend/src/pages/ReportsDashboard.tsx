import { useEffect, useState } from "react";
import { apiGet } from "../api/client";

interface Inventory {
  total_videos: number;
  total_size_bytes: number;
  by_status: Record<string, number>;
  by_format: Record<string, number>;
}
interface StorageUtil { [tier: string]: { count: number; size_bytes: number } }
interface RedactionWorkload { by_type: Record<string, number>; by_status: Record<string, number>; by_user: Record<string, number> }
interface UserActivityRow { actor: string; action: string; count: number }
interface InvestigationRow { case_id: string; case_name: string; video_count: number }

function BreakdownTable({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = Object.entries(data);
  return (
    <div>
      <h4>{title}</h4>
      {entries.length === 0 ? (
        <p style={{ color: "var(--muted)", fontSize: 12 }}>No data yet.</p>
      ) : (
        <table>
          <tbody>
            {entries.map(([k, v]) => (
              <tr key={k}><td>{k}</td><td>{v}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function ReportsDashboard() {
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [storage, setStorage] = useState<StorageUtil | null>(null);
  const [redaction, setRedaction] = useState<RedactionWorkload | null>(null);
  const [activity, setActivity] = useState<UserActivityRow[]>([]);
  const [investigations, setInvestigations] = useState<InvestigationRow[]>([]);

  useEffect(() => {
    apiGet<Inventory>("/reports/inventory").then(setInventory);
    apiGet<StorageUtil>("/reports/storage-utilization").then(setStorage);
    apiGet<RedactionWorkload>("/reports/redaction-workload").then(setRedaction);
    apiGet<UserActivityRow[]>("/reports/user-activity").then(setActivity);
    apiGet<InvestigationRow[]>("/reports/investigation-workload").then(setInvestigations);
  }, []);

  return (
    <div>
      <h2>Reports</h2>

      <div className="grid cols-4">
        <div className="stat-tile">
          <div className="value">{inventory?.total_videos ?? "—"}</div>
          <div className="label">Total videos</div>
        </div>
        <div className="stat-tile">
          <div className="value">{inventory ? `${(inventory.total_size_bytes / 1e9).toFixed(2)} GB` : "—"}</div>
          <div className="label">Total storage</div>
        </div>
        <div className="stat-tile">
          <div className="value">{storage?.hot?.count ?? 0}</div>
          <div className="label">Hot tier videos</div>
        </div>
        <div className="stat-tile">
          <div className="value">{storage?.cold?.count ?? 0}</div>
          <div className="label">Archived (cold) videos</div>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginTop: 18 }}>
        <div className="card">
          <h3>Video inventory</h3>
          {inventory && (
            <>
              <BreakdownTable title="By status" data={inventory.by_status} />
              <BreakdownTable title="By format" data={inventory.by_format} />
            </>
          )}
        </div>

        <div className="card">
          <h3>Redaction workload</h3>
          {redaction && (
            <>
              <BreakdownTable title="By type" data={redaction.by_type} />
              <BreakdownTable title="By status" data={redaction.by_status} />
            </>
          )}
        </div>

        <div className="card">
          <h3>User activity</h3>
          <table>
            <thead><tr><th>Actor</th><th>Action</th><th>Count</th></tr></thead>
            <tbody>
              {activity.slice(0, 15).map((r, i) => (
                <tr key={i}><td>{r.actor}</td><td>{r.action}</td><td>{r.count}</td></tr>
              ))}
              {activity.length === 0 && <tr><td colSpan={3} style={{ color: "var(--muted)" }}>No activity yet.</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h3>Investigation workload</h3>
          <table>
            <thead><tr><th>Case</th><th>Videos</th></tr></thead>
            <tbody>
              {investigations.map((r) => (
                <tr key={r.case_id}><td>{r.case_name}</td><td>{r.video_count}</td></tr>
              ))}
              {investigations.length === 0 && <tr><td colSpan={2} style={{ color: "var(--muted)" }}>No cases yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 8 }}>
        These aggregates are the Power BI integration point: connect Power BI's Web connector to these
        JSON endpoints, or point it directly at the Postgres database for richer modeling.
      </p>
    </div>
  );
}
