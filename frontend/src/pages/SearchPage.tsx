import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "../api/client";
import type { Video } from "../api/types";
import Badge from "../components/Badge";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [metadataField, setMetadataField] = useState("");
  const [metadataValue, setMetadataValue] = useState("");
  const [results, setResults] = useState<Video[]>([]);
  const [searched, setSearched] = useState(false);

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    const rows = await apiGet<Video[]>("/search/videos", {
      q: q || undefined,
      metadata_field: metadataField || undefined,
      metadata_value: metadataValue || undefined,
    });
    setResults(rows);
    setSearched(true);
  }

  return (
    <div>
      <h2>Search evidence</h2>
      <div className="card">
        <form onSubmit={onSearch} className="grid cols-3">
          <div className="field">
            <label>Keyword (filename, metadata, transcript text)</label>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. platform incident" />
          </div>
          <div className="field">
            <label>Metadata field</label>
            <input value={metadataField} onChange={(e) => setMetadataField(e.target.value)} placeholder="suspect_description" />
          </div>
          <div className="field">
            <label>Metadata value</label>
            <input value={metadataValue} onChange={(e) => setMetadataValue(e.target.value)} placeholder="red jacket" />
          </div>
          <button type="submit">Search</button>
        </form>
      </div>

      {searched && (
        <div className="card">
          <table>
            <thead>
              <tr><th>Filename</th><th>Format</th><th>Status</th><th>Metadata</th><th>Uploaded</th></tr>
            </thead>
            <tbody>
              {results.map((v) => (
                <tr key={v.id}>
                  <td><Link to={`/videos/${v.id}`}>{v.filename}</Link></td>
                  <td>{v.format}</td>
                  <td><Badge value={v.status} /></td>
                  <td style={{ fontSize: 11 }}>{JSON.stringify(v.metadata_fields)}</td>
                  <td>{new Date(v.uploaded_at).toLocaleString()}</td>
                </tr>
              ))}
              {results.length === 0 && (
                <tr><td colSpan={5} style={{ color: "var(--muted)" }}>No matching videos.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
