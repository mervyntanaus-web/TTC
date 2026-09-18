import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { apiGet, apiPost, apiStreamUrl, API_BASE, ApiError } from "../api/client";
import type { RecipientType, ShareLink, ShareScope } from "../api/types";

export default function SharingPage() {
  const [params] = useSearchParams();
  const videoId = params.get("video_id") ?? "";

  const [links, setLinks] = useState<ShareLink[]>([]);
  const [resourceId, setResourceId] = useState(videoId);
  const [scope, setScope] = useState<ShareScope>("view_only");
  const [recipientType, setRecipientType] = useState<RecipientType>("police");
  const [recipientLabel, setRecipientLabel] = useState("");
  const [expiresInDays, setExpiresInDays] = useState(7);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (resourceId) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resourceId]);

  async function refresh() {
    if (!resourceId) return;
    setLinks(await apiGet<ShareLink[]>("/share-links", { resource_id: resourceId }));
  }

  async function createLink(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await apiPost<ShareLink>("/share-links", {
        resource_type: "video",
        resource_id: resourceId,
        scope,
        recipient_type: recipientType,
        recipient_label: recipientLabel || undefined,
        expires_in_days: expiresInDays,
      });
      setRecipientLabel("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create share link");
    }
  }

  async function revoke(id: string) {
    await apiPost(`/share-links/${id}/revoke`);
    await refresh();
  }

  function shareUrl(token: string, download: boolean) {
    const path = apiStreamUrl(`/share/${token}/${download ? "download" : "stream"}`);
    return API_BASE.startsWith("http") ? path : `${window.location.origin}${path}`;
  }

  return (
    <div>
      <h2>Share evidence</h2>
      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <h3>Create a share link</h3>
        <form onSubmit={createLink} className="grid cols-3">
          <div className="field">
            <label>Video ID</label>
            <input value={resourceId} onChange={(e) => setResourceId(e.target.value)} required />
          </div>
          <div className="field">
            <label>Recipient type</label>
            <select value={recipientType} onChange={(e) => setRecipientType(e.target.value as RecipientType)}>
              <option value="internal_staff">TTC staff</option>
              <option value="legal_team">Legal team</option>
              <option value="police">Police</option>
              <option value="insurance">Insurance investigator</option>
              <option value="court">Court</option>
              <option value="foi">FOI recipient</option>
              <option value="guest">Guest</option>
            </select>
          </div>
          <div className="field">
            <label>Access</label>
            <select value={scope} onChange={(e) => setScope(e.target.value as ShareScope)}>
              <option value="view_only">View only</option>
              <option value="download">Allow download</option>
            </select>
          </div>
          <div className="field">
            <label>Recipient label (optional)</label>
            <input value={recipientLabel} onChange={(e) => setRecipientLabel(e.target.value)} placeholder="Det. Smith" />
          </div>
          <div className="field">
            <label>Expires in (days, 0 = immediately)</label>
            <input type="number" min={0} value={expiresInDays} onChange={(e) => setExpiresInDays(Number(e.target.value))} />
          </div>
          <button type="submit">Create link</button>
        </form>
      </div>

      <div className="card">
        <h3>Existing links</h3>
        <table>
          <thead>
            <tr><th>Recipient</th><th>Scope</th><th>Expires</th><th>Accesses</th><th>Link</th><th></th></tr>
          </thead>
          <tbody>
            {links.map((l) => (
              <tr key={l.id} style={{ opacity: l.revoked ? 0.5 : 1 }}>
                <td>{l.recipient_type}{l.recipient_label ? ` — ${l.recipient_label}` : ""}</td>
                <td>{l.scope}</td>
                <td>{l.expires_at ? new Date(l.expires_at).toLocaleString() : "never"}</td>
                <td>{l.access_count}</td>
                <td style={{ fontSize: 11, wordBreak: "break-all" }}>
                  {l.revoked ? "revoked" : shareUrl(l.token, l.scope === "download")}
                </td>
                <td>
                  {!l.revoked && <button className="danger" onClick={() => revoke(l.id)}>Revoke</button>}
                </td>
              </tr>
            ))}
            {links.length === 0 && (
              <tr><td colSpan={6} style={{ color: "var(--muted)" }}>No share links for this video yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
