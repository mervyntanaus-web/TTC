export type UserRole = "admin" | "staff" | "legal" | "investigator" | "external";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  organisation?: string | null;
}

export interface Case {
  id: string;
  name: string;
  description?: string | null;
  retention_category: string;
  metadata_fields: Record<string, unknown>;
  created_at: string;
}

export interface Folder {
  id: string;
  case_id: string;
  parent_id: string | null;
  name: string;
  metadata_fields: Record<string, unknown>;
  linked_folder_ids: string[];
  created_at: string;
}

export type VideoStatus = "ingested" | "processing" | "ready" | "needs_vendor_decoder" | "failed" | "deleted";
export type StorageTier = "hot" | "cold" | "restoring";

export interface Video {
  id: string;
  folder_id: string;
  filename: string;
  format: string;
  source_connector: string;
  camera_id?: string | null;
  status: VideoStatus;
  storage_tier: StorageTier;
  checksum_sha256?: string | null;
  size_bytes?: number | null;
  duration_seconds?: number | null;
  captured_at?: string | null;
  uploaded_at: string;
  metadata_fields: Record<string, unknown>;
  retention_category: string;
  legal_hold: boolean;
}

export type VideoVersionKind = "original" | "redacted" | "disclosure";

export interface VideoVersion {
  id: string;
  video_id: string;
  parent_version_id: string | null;
  kind: VideoVersionKind;
  storage_tier: StorageTier;
  redaction_job_id: string | null;
  watermark_applied: boolean;
  created_at: string;
  notes?: string | null;
}

export interface RegionFrame { t: number; x: number; y: number; w: number; h: number }
export interface RegionTrack { track_id: string; label?: string | null; frames: RegionFrame[] }
export interface AudioSegment { start: number; end: number; reason?: string | null }

export type RedactionType = "face_auto" | "face_tracked" | "manual_region" | "audio_mute" | "transcript_based_audio";
export type RedactionJobStatus = "pending" | "running" | "complete" | "failed";

export interface RedactionJob {
  id: string;
  video_id: string;
  source_version_id: string;
  type: RedactionType;
  status: RedactionJobStatus;
  regions: RegionTrack[];
  audio_segments: AudioSegment[];
  result_version_id: string | null;
  error_message?: string | null;
}

export interface TranscriptSegment {
  id: string;
  start: number;
  end: number;
  text: string;
  speaker?: string | null;
  redacted: boolean;
}

export interface Transcript {
  id: string;
  video_id: string;
  segments: TranscriptSegment[];
  language?: string | null;
  edited: boolean;
  generated_at: string;
  updated_at: string;
}

export type ShareResourceType = "video" | "folder";
export type ShareScope = "view_only" | "download";
export type RecipientType = "internal_staff" | "legal_team" | "police" | "insurance" | "court" | "foi" | "guest";

export interface ShareLink {
  id: string;
  resource_type: ShareResourceType;
  resource_id: string;
  token: string;
  scope: ShareScope;
  recipient_type: RecipientType;
  recipient_label?: string | null;
  created_at: string;
  expires_at?: string | null;
  revoked: boolean;
  access_count: number;
  last_accessed_at?: string | null;
}

export interface AuditLog {
  id: string;
  actor_id?: string | null;
  actor_label?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  details: Record<string, unknown>;
  timestamp: string;
}

export interface RetentionPolicy {
  id: string;
  category: string;
  retention_days: number;
  auto_delete: boolean;
  auto_archive_after_days?: number | null;
  description?: string | null;
}

export interface RetentionStatus {
  category: string;
  expires_at: string;
  archive_at?: string | null;
  legal_hold: boolean;
  eligible_for_deletion: boolean;
  eligible_for_archive: boolean;
}

export interface StorageTierEvent {
  id: string;
  video_id: string;
  tier: StorageTier;
  moved_at: string;
  restore_eta?: string | null;
}

export interface CameraInfo {
  camera_id: string;
  name: string;
  location?: string | null;
}
