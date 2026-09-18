import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, apiUpload, ApiError } from "../api/client";
import type { Case, Folder, Video } from "../api/types";
import FolderTree from "../components/FolderTree";
import Badge from "../components/Badge";

export default function CaseBrowser() {
  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<Folder | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [newCaseName, setNewCaseName] = useState("");
  const [newFolderName, setNewFolderName] = useState("");
  const [uploadFiles, setUploadFiles] = useState<FileList | null>(null);
  const [uploadMetadata, setUploadMetadata] = useState("{}");

  useEffect(() => {
    apiGet<Case[]>("/cases").then(setCases).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!selectedCase) return;
    apiGet<Folder[]>(`/cases/${selectedCase.id}/folders`).then(setFolders);
    setSelectedFolder(null);
    setVideos([]);
  }, [selectedCase]);

  useEffect(() => {
    if (!selectedFolder) return;
    apiGet<Video[]>("/search/videos", { folder_id: selectedFolder.id }).then(setVideos);
  }, [selectedFolder]);

  async function createCase(e: FormEvent) {
    e.preventDefault();
    if (!newCaseName.trim()) return;
    const created = await apiPost<Case>("/cases", { name: newCaseName, retention_category: "standard" });
    setCases((prev) => [created, ...prev]);
    setNewCaseName("");
    setSelectedCase(created);
  }

  async function createFolder(e: FormEvent) {
    e.preventDefault();
    if (!selectedCase || !newFolderName.trim()) return;
    const created = await apiPost<Folder>("/folders", {
      case_id: selectedCase.id,
      parent_id: selectedFolder?.id ?? null,
      name: newFolderName,
    });
    setFolders((prev) => [...prev, created]);
    setNewFolderName("");
  }

  async function refreshVideos() {
    if (!selectedFolder) return;
    setVideos(await apiGet<Video[]>("/search/videos", { folder_id: selectedFolder.id }));
  }

  async function onUpload(e: FormEvent) {
    e.preventDefault();
    if (!selectedFolder || !uploadFiles || uploadFiles.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("folder_id", selectedFolder.id);
      form.append("metadata_fields", uploadMetadata || "{}");
      const path = uploadFiles.length > 1 ? "/videos/bulk-upload" : "/videos/upload";
      if (uploadFiles.length > 1) {
        for (const file of Array.from(uploadFiles)) form.append("files", file);
      } else {
        form.append("file", uploadFiles[0]);
      }
      await apiUpload(path, form);
      setUploadFiles(null);
      await refreshVideos();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2>Cases &amp; Evidence</h2>
      {error && <div className="error-banner">{error}</div>}

      <div className="grid cols-3">
        <div className="card">
          <h3>Cases</h3>
          <form onSubmit={createCase} className="toolbar">
            <input placeholder="New case name" value={newCaseName} onChange={(e) => setNewCaseName(e.target.value)} />
            <button type="submit">Create</button>
          </form>
          <div className="folder-tree">
            {cases.map((c) => (
              <div
                key={c.id}
                className={`node ${selectedCase?.id === c.id ? "selected" : ""}`}
                onClick={() => setSelectedCase(c)}
              >
                🗂 {c.name}
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h3>Folders {selectedCase ? `— ${selectedCase.name}` : ""}</h3>
          {selectedCase ? (
            <>
              <form onSubmit={createFolder} className="toolbar">
                <input
                  placeholder={selectedFolder ? `New subfolder of ${selectedFolder.name}` : "New root folder"}
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                />
                <button type="submit">Add</button>
              </form>
              <FolderTree folders={folders} selectedId={selectedFolder?.id ?? null} onSelect={setSelectedFolder} />
            </>
          ) : (
            <p style={{ color: "var(--muted)" }}>Select a case to view its folders.</p>
          )}
        </div>

        <div className="card">
          <h3>Upload evidence</h3>
          {selectedFolder ? (
            <form onSubmit={onUpload}>
              <div className="field">
                <label>Video file(s) — MP4, AVI, MKV, MPEG-4, or vendor CME/G64x</label>
                <input type="file" multiple onChange={(e) => setUploadFiles(e.target.files)} />
              </div>
              <div className="field">
                <label>Metadata (JSON)</label>
                <textarea
                  rows={3}
                  value={uploadMetadata}
                  onChange={(e) => setUploadMetadata(e.target.value)}
                  placeholder='{"suspect_description": "red jacket"}'
                />
              </div>
              <button type="submit" disabled={busy}>
                {busy ? "Uploading…" : "Upload to " + selectedFolder.name}
              </button>
            </form>
          ) : (
            <p style={{ color: "var(--muted)" }}>Select a folder to upload video into.</p>
          )}
        </div>
      </div>

      {selectedFolder && (
        <div className="card">
          <h3>Videos in {selectedFolder.name}</h3>
          <table>
            <thead>
              <tr>
                <th>Filename</th>
                <th>Format</th>
                <th>Status</th>
                <th>Tier</th>
                <th>Duration</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {videos.map((v) => (
                <tr key={v.id}>
                  <td>
                    <Link to={`/videos/${v.id}`}>{v.filename}</Link>
                    {v.legal_hold && <span className="badge" style={{ marginLeft: 6 }}>legal hold</span>}
                  </td>
                  <td>{v.format}</td>
                  <td><Badge value={v.status} /></td>
                  <td><Badge value={v.storage_tier} /></td>
                  <td>{v.duration_seconds ? `${v.duration_seconds.toFixed(1)}s` : "—"}</td>
                  <td>{new Date(v.uploaded_at).toLocaleString()}</td>
                </tr>
              ))}
              {videos.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ color: "var(--muted)" }}>
                    No videos in this folder yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
